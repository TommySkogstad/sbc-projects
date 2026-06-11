"""Print-server web-UI: last opp PDF, print via CUPS.

Portet fra tommytv-infra/printer-service for native systemd-deploy på Rock 3C.
LAN-only by default — auth utsatt til evt. Cloudflare Tunnel.
"""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "50"))
LOG_FILE = Path(os.environ.get("LOG_FILE", "/var/log/printer-web.log"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("printer-web")

app = FastAPI(title="print-server")

HOSTNAME = socket.gethostname()


def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def default_printer() -> str:
    """Hent default printer-navn fra CUPS. Returnerer 'auto-USB-Printer' som fallback."""
    override = os.environ.get("DEFAULT_PRINTER", "").strip()
    if override:
        return override
    result = run(["lpstat", "-d"])
    if result.returncode == 0 and ":" in result.stdout:
        name = result.stdout.split(":", 1)[1].strip()
        if name and name != "no system default destination":
            return name
    # Fallback: ta første printer fra lpstat -p
    result = run(["lpstat", "-p"])
    for line in result.stdout.splitlines():
        if line.startswith("printer "):
            return line.split()[1]
    return "auto-USB-Printer"


def page_count(pdf_path: Path) -> int:
    result = run(["pdfinfo", str(pdf_path)])
    if result.returncode != 0:
        raise HTTPException(400, f"Klarte ikke lese PDF: {result.stderr.strip()}")
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise HTTPException(400, "Fant ikke sidetall i PDF")


def printer_state(name: str) -> dict[str, str]:
    result = run(["lpstat", "-p", name, "-l"])
    return {
        "ok": str(result.returncode == 0).lower(),
        "raw": result.stdout.strip() or result.stderr.strip(),
    }


def active_jobs() -> list[str]:
    result = run(["lpstat", "-W", "not-completed", "-o"])
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def list_printers() -> list[str]:
    result = run(["lpstat", "-p"])
    return [
        line.split()[1]
        for line in result.stdout.splitlines()
        if line.startswith("printer ")
    ]


PAGE_STYLE = """
  :root { color-scheme: light dark; }
  body {
    font-family: system-ui, -apple-system, sans-serif;
    max-width: 540px; margin: 4rem auto; padding: 0 1.5rem;
    background: #0d1b2a; color: #f4f4f5;
  }
  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  p.sub { color: #94a3b8; margin-top: 0; font-size: 0.9rem; }
  .card {
    border: 1px solid #1e293b; border-radius: 12px;
    padding: 1.5rem; background: #111827; margin-top: 1.5rem;
  }
  .card.ok { border-color: #15803d; }
  .card.err { border-color: #b91c1c; }
  .badge {
    display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px;
    font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    vertical-align: middle; margin-left: 0.4rem;
  }
  .badge.ok { background: #15803d; color: white; }
  .badge.err { background: #b91c1c; color: white; }
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.4rem 1rem; margin: 1.25rem 0 0; }
  dt { color: #94a3b8; font-size: 0.85rem; }
  dd { margin: 0; font-size: 0.95rem; word-break: break-word; }
  .actions { display: flex; gap: 0.75rem; margin-top: 1.5rem; }
  .btn {
    flex: 1; padding: 0.75rem; border-radius: 8px; text-align: center;
    text-decoration: none; font-weight: 600; font-size: 0.95rem;
    background: #2563eb; color: white; border: 0; cursor: pointer;
  }
  .btn:hover { background: #1d4ed8; }
  .btn.secondary { background: transparent; border: 1px solid #334155; color: #e2e8f0; }
  .btn.secondary:hover { background: #1e293b; }
  input[type=file] {
    width: 100%; padding: 1rem;
    background: #0d1b2a; border: 1px dashed #334155;
    border-radius: 8px; color: #f4f4f5; margin-bottom: 1rem;
  }
  label.opt { display: block; font-size: 0.85rem; color: #94a3b8; margin: 0.5rem 0 0.25rem; }
  select, input[type=number] {
    width: 100%; padding: 0.5rem; background: #0d1b2a;
    border: 1px solid #334155; border-radius: 6px; color: #f4f4f5;
  }
  button.primary {
    width: 100%; padding: 0.85rem; margin-top: 1rem;
    background: #2563eb; color: white; border: 0;
    border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer;
  }
  button.primary:hover { background: #1d4ed8; }
  .meta { margin-top: 1.5rem; font-size: 0.85rem; color: #64748b; }
  .meta a { color: #94a3b8; }
  pre { background: #0d1b2a; padding: 0.75rem; border-radius: 6px; overflow-x: auto; font-size: 0.8rem; white-space: pre-wrap; }
"""


INDEX_HTML = """<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<title>__HOSTNAME__ — print-server</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>__STYLE__</style>
</head>
<body>
  <h1>__HOSTNAME__</h1>
  <p class="sub">Last opp en PDF — den printer på __PRINTER__.</p>
  <form class="card" action="/print" method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept="application/pdf" required>
    <label class="opt" for="copies">Antall kopier</label>
    <input type="number" id="copies" name="copies" value="1" min="1" max="10">
    <label class="opt" for="sides">Tosidig</label>
    <select id="sides" name="sides">
      <option value="one-sided">Enkeltsidig</option>
      <option value="two-sided-long-edge">Tosidig (lang kant)</option>
      <option value="two-sided-short-edge">Tosidig (kort kant)</option>
    </select>
    <button class="primary" type="submit">Print</button>
  </form>
  <div class="meta">
    Maks __MAX_MB__ MB · maks __MAX_PAGES__ sider · <a href="/queue">kø</a> · <a href="/healthz">helse</a>
  </div>
</body>
</html>
"""


SUCCESS_HTML = """<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<title>Print sendt</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>__STYLE__</style>
</head>
<body>
  <h1>Print sendt <span class="badge ok">OK</span></h1>
  <p class="sub">Jobben er lagt i køen til __PRINTER__.</p>
  <div class="card ok">
    <dl>
      <dt>Fil</dt><dd>__FILE__</dd>
      <dt>Sider</dt><dd>__PAGES__</dd>
      <dt>Kopier</dt><dd>__COPIES__</dd>
      <dt>Sider/ark</dt><dd>__SIDES_LABEL__</dd>
      <dt>Jobb-ID</dt><dd><code>__JOB__</code></dd>
      <dt>Tidspunkt</dt><dd>__AT__</dd>
    </dl>
    <div class="actions">
      <a class="btn" href="/">Print en til</a>
      <a class="btn secondary" href="/queue">Se kø</a>
    </div>
  </div>
</body>
</html>
"""


ERROR_HTML = """<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<title>Print feilet</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>__STYLE__</style>
</head>
<body>
  <h1>Print feilet <span class="badge err">__STATUS__</span></h1>
  <p class="sub">Forespørselen ble ikke akseptert.</p>
  <div class="card err">
    <pre>__DETAIL__</pre>
    <div class="actions">
      <a class="btn" href="/">Tilbake</a>
      <a class="btn secondary" href="/queue">Se kø</a>
    </div>
  </div>
</body>
</html>
"""


SIDES_LABEL = {
    "one-sided": "Enkeltsidig",
    "two-sided-long-edge": "Tosidig (lang kant)",
    "two-sided-short-edge": "Tosidig (kort kant)",
}


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render(template: str, **values: Any) -> str:
    out = template.replace("__STYLE__", PAGE_STYLE)
    for key, val in values.items():
        out = out.replace(f"__{key.upper()}__", html_escape(str(val)))
    return out


def wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if not accept:
        return False
    first = accept.split(",")[0].strip().lower()
    if first.startswith("application/json"):
        return False
    return "text/html" in accept.lower() or first == "*/*"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return render(
        INDEX_HTML,
        hostname=HOSTNAME,
        printer=default_printer(),
        max_mb=MAX_UPLOAD_MB,
        max_pages=MAX_PAGES,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if wants_html(request) and request.url.path == "/print":
        body = render(
            ERROR_HTML,
            status=exc.status_code,
            detail=str(exc.detail),
        )
        return HTMLResponse(body, status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if wants_html(request) and request.url.path == "/print":
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}"
            for e in exc.errors()
        ) or "Ugyldig forespørsel"
        body = render(ERROR_HTML, status=422, detail=detail)
        return HTMLResponse(body, status_code=422)
    return JSONResponse({"detail": exc.errors()}, status_code=422)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    printer = default_printer()
    state = printer_state(printer)
    healthy = state["ok"] == "true"
    return {
        "status": "ok" if healthy else "degraded",
        "hostname": HOSTNAME,
        "printer": printer,
        "available_printers": list_printers(),
        **state,
    }


@app.get("/queue")
def queue() -> dict[str, Any]:
    printer = default_printer()
    return {
        "hostname": HOSTNAME,
        "printer": printer,
        "jobs": active_jobs(),
        "state": printer_state(printer),
    }


@app.post("/print")
async def print_pdf(
    request: Request,
    file: UploadFile = File(...),
    copies: int = 1,
    sides: str = "one-sided",
):
    client_ip = request.client.host if request.client else "unknown"
    printer = default_printer()

    if not (1 <= copies <= 10):
        raise HTTPException(400, "copies må være 1–10")
    if sides not in {"one-sided", "two-sided-long-edge", "two-sided-short-edge"}:
        raise HTTPException(400, "ugyldig sides-verdi")

    body = await file.read()
    size_mb = len(body) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(413, f"For stor fil: {size_mb:.1f} MB (maks {MAX_UPLOAD_MB})")
    if not body.startswith(b"%PDF-"):
        raise HTTPException(400, "Fila er ikke en gyldig PDF")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir="/tmp") as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        pages = page_count(tmp_path)
        if pages > MAX_PAGES:
            raise HTTPException(413, f"For mange sider: {pages} (maks {MAX_PAGES})")

        safe_name = (file.filename or "upload.pdf").replace("\n", "_")[:120]
        cmd = [
            "lp",
            "-d", printer,
            "-n", str(copies),
            "-o", f"sides={sides}",
            "-o", "media=A4",
            "-t", safe_name,
            str(tmp_path),
        ]
        result = run(cmd)
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            log.error("lp feilet for %s (ip=%s): %s", safe_name, client_ip, err)
            raise HTTPException(500, f"Print feilet: {err}")

        job_id = result.stdout.strip()
        at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        log.info(
            "PRINT ip=%s file=%s size=%.1fMB pages=%d copies=%d sides=%s job=%s",
            client_ip, safe_name, size_mb, pages, copies, sides, job_id,
        )
        if wants_html(request):
            body_html = render(
                SUCCESS_HTML,
                printer=printer,
                file=safe_name,
                pages=pages,
                copies=copies,
                sides_label=SIDES_LABEL.get(sides, sides),
                job=job_id or "(ukjent)",
                at=at,
            )
            return HTMLResponse(body_html)
        return JSONResponse({
            "ok": True,
            "job": job_id,
            "file": safe_name,
            "pages": pages,
            "copies": copies,
            "sides": sides,
            "at": at,
        })
    finally:
        tmp_path.unlink(missing_ok=True)
