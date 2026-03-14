(function () {
    "use strict";

    var POLL_INTERVAL = 30000;
    var pollTimer = null;
    var currentMode = "auto"; // "auto", "on", "off"
    var currentThresholds = {
        ice_temp_min: -3, ice_temp_max: 3,
        critical_temp_min: -1, critical_temp_max: 2
    };

    // -- API helpers --

    function getCsrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)geoloop_csrf=([^;]+)/);
        return match ? match[1] : "";
    }

    function fetchJSON(url, opts) {
        opts = opts || {};
        if (opts.method && opts.method !== "GET") {
            opts.headers = opts.headers || {};
            opts.headers["x-csrf-token"] = getCsrfToken();
        }
        return fetch(url, opts).then(function (r) { return r.json(); });
    }

    function updateModeButtons(mode) {
        currentMode = mode;
        var btnOn = document.getElementById("btn-on");
        var btnOff = document.getElementById("btn-off");
        var btnAuto = document.getElementById("btn-auto");
        btnOn.className = "ctrl-btn" + (mode === "on" ? " active-on" : "");
        btnOff.className = "ctrl-btn" + (mode === "off" ? " active-off" : "");
        btnAuto.className = "ctrl-btn" + (mode === "auto" ? " active-auto" : "");

        var modeEl = document.getElementById("mode-indicator");
        var labels = { auto: "Automatisk styring", on: "Manuelt PÅ", off: "Manuelt AV" };
        modeEl.textContent = labels[mode] || "";
    }

    function updateStatus() {
        fetchJSON("/api/status").then(function (data) {
            // Heating
            var el = document.getElementById("heating-status");
            if (data.heating) {
                var on = data.heating.on;
                el.className = "status-indicator " + (on ? "status-on" : "status-off");
                el.querySelector(".label").textContent = on ? "PÅ" : "AV";
                updateModeButtons(data.heating.mode || "auto");
            }

            // Thresholds
            if (data.thresholds) {
                currentThresholds = data.thresholds;
                syncThresholdSliders(data.thresholds);
            }

            // Weather
            if (data.weather) {
                var w = data.weather;
                setText("w-temp", fmt(w.air_temperature, "\u00b0C"));
                setText("w-precip", fmt(w.precipitation_amount, " mm"));
                setText("w-humidity", fmt(w.relative_humidity, "%"));
                setText("w-wind", fmt(w.wind_speed, " m/s"));
            }

            // Sensors
            if (data.sensors) {
                renderSensors(data.sensors);
            }

            document.getElementById("last-update").textContent =
                "Oppdatert " + new Date().toLocaleTimeString("nb-NO");
        }).catch(function () {
            document.getElementById("last-update").textContent = "Feil ved oppdatering";
        });
    }

    function updateForecast() {
        fetchJSON("/api/weather").then(function (data) {
            if (data.forecast) {
                drawChart(data.forecast);
            }
        }).catch(function () { /* ignore */ });
    }

    function updateLog() {
        fetchJSON("/api/log?limit=20").then(function (data) {
            if (data.events) {
                renderEvents(data.events);
            }
        }).catch(function () { /* ignore */ });
    }

    // -- Rendering --

    function setText(id, text) {
        document.getElementById(id).textContent = text;
    }

    function fmt(val, suffix) {
        if (val === null || val === undefined) return "--";
        return (typeof val === "number" ? val.toFixed(1) : val) + suffix;
    }

    var SENSOR_LABELS = {
        loop_inlet: "Sløyfe inn",
        loop_outlet: "Sløyfe ut",
        hp_inlet: "VP inn",
        hp_outlet: "VP ut",
        tank: "Tank"
    };

    function renderSensors(sensors) {
        var grid = document.getElementById("sensor-grid");
        grid.textContent = "";
        var hasKeys = false;
        for (var key in sensors) {
            hasKeys = true;
            var label = SENSOR_LABELS[key] || key;
            var val = sensors[key];
            var div = document.createElement("div");
            div.className = "stat";
            var spanVal = document.createElement("span");
            spanVal.className = "stat-value";
            spanVal.textContent = fmt(val, "\u00b0C");
            var spanLabel = document.createElement("span");
            spanLabel.className = "stat-label";
            spanLabel.textContent = label;
            div.appendChild(spanVal);
            div.appendChild(spanLabel);
            grid.appendChild(div);
        }
        if (!hasKeys) {
            var p = document.createElement("p");
            p.className = "meta";
            p.textContent = "Ingen sensorer";
            grid.appendChild(p);
        }
    }

    function renderEvents(events) {
        var el = document.getElementById("event-log");
        el.textContent = "";
        if (!events.length) {
            var p = document.createElement("p");
            p.className = "meta";
            p.textContent = "Ingen hendelser";
            el.appendChild(p);
            return;
        }
        for (var i = 0; i < events.length; i++) {
            var e = events[i];
            var ts = e.timestamp ? new Date(e.timestamp).toLocaleString("nb-NO") : "";
            var div = document.createElement("div");
            div.className = "event-item";
            var spanType = document.createElement("span");
            spanType.className = "event-type " + (e.event_type || "");
            spanType.textContent = e.event_type || "";
            var spanMsg = document.createElement("span");
            spanMsg.className = "event-msg";
            spanMsg.textContent = e.message || "";
            var spanTime = document.createElement("span");
            spanTime.className = "event-time";
            spanTime.textContent = ts;
            div.appendChild(spanType);
            div.appendChild(spanMsg);
            div.appendChild(spanTime);
            el.appendChild(div);
        }
    }

    // -- Forecast chart --

    function drawChart(forecast) {
        var canvas = document.getElementById("forecast-chart");
        var ctx = canvas.getContext("2d");
        var dpr = window.devicePixelRatio || 1;

        var w = canvas.offsetWidth  || 600;
        var h = canvas.offsetHeight || 200;

        canvas.width  = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
        var pad = { top: 20, right: 10, bottom: 30, left: 40 };
        var cw = w - pad.left - pad.right;
        var ch = h - pad.top - pad.bottom;

        // Data
        var temps = [];
        var precips = [];
        var labels = [];
        for (var i = 0; i < forecast.length; i++) {
            var s = forecast[i];
            temps.push(s.air_temperature);
            precips.push(s.precipitation_amount || 0);
            labels.push(new Date(s.time).getHours() + ":00");
        }

        if (!temps.length) return;

        var tMin = Math.floor(Math.min.apply(null, temps) - 2);
        var tMax = Math.ceil(Math.max.apply(null, temps) + 2);
        var pMax = Math.max(Math.max.apply(null, precips), 1);

        ctx.clearRect(0, 0, w, h);

        // Ice zone background (dynamic thresholds)
        var iceTop = pad.top + ch * (1 - (currentThresholds.ice_temp_max - tMin) / (tMax - tMin));
        var iceBot = pad.top + ch * (1 - (currentThresholds.ice_temp_min - tMin) / (tMax - tMin));
        iceTop = Math.max(pad.top, Math.min(pad.top + ch, iceTop));
        iceBot = Math.max(pad.top, Math.min(pad.top + ch, iceBot));
        ctx.fillStyle = "rgba(255, 82, 82, 0.08)";
        ctx.fillRect(pad.left, iceTop, cw, iceBot - iceTop);

        // Precip bars
        var barW = cw / temps.length * 0.6;
        ctx.fillStyle = "rgba(33, 150, 243, 0.4)";
        for (var i = 0; i < precips.length; i++) {
            var x = pad.left + (i + 0.5) * cw / temps.length;
            var bh = (precips[i] / pMax) * ch * 0.3;
            ctx.fillRect(x - barW / 2, pad.top + ch - bh, barW, bh);
        }

        // Temperature line
        ctx.beginPath();
        ctx.strokeStyle = "#ff9800";
        ctx.lineWidth = 2;
        for (var i = 0; i < temps.length; i++) {
            var x = pad.left + (i + 0.5) * cw / temps.length;
            var y = pad.top + ch * (1 - (temps[i] - tMin) / (tMax - tMin));
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Zero line
        if (tMin < 0 && tMax > 0) {
            var zeroY = pad.top + ch * (1 - (0 - tMin) / (tMax - tMin));
            ctx.beginPath();
            ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.moveTo(pad.left, zeroY);
            ctx.lineTo(pad.left + cw, zeroY);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Axes labels
        ctx.fillStyle = "#8a8a9a";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";
        var steps = 5;
        for (var i = 0; i <= steps; i++) {
            var v = tMin + (tMax - tMin) * (i / steps);
            var y = pad.top + ch * (1 - i / steps);
            ctx.fillText(v.toFixed(0) + "\u00b0", pad.left - 5, y + 4);
        }

        ctx.textAlign = "center";
        var labelStep = Math.max(1, Math.floor(temps.length / 8));
        for (var i = 0; i < labels.length; i += labelStep) {
            var x = pad.left + (i + 0.5) * cw / temps.length;
            ctx.fillText(labels[i], x, h - 5);
        }
    }

    // -- History chart (canvas, ingen CDN-avhengighet) --

    var historyHours = 24;

    var PERIOD_CFG = {
        1:   { limit: 120, intervalMs: 5 * 60000,   fmt: "HH:MM" },
        6:   { limit: 120, intervalMs: 30 * 60000,  fmt: "HH:MM" },
        24:  { limit: 120, intervalMs: 2 * 3600000, fmt: "HH:00" },
        168: { limit: 70,  intervalMs: 24 * 3600000, fmt: "ddd" }
    };

    var NORSK_DAGER = ["søn", "man", "tir", "ons", "tor", "fre", "lør"];

    var H_KEYS   = ["loop_inlet", "loop_outlet", "hp_inlet", "hp_outlet", "tank"];
    var H_COLORS = ["#42a5f5",    "#66bb6a",     "#ef5350",  "#ff9800",   "#ab47bc"];
    var H_LABELS = ["Sløyfe inn", "Sløyfe ut",   "VP inn",   "VP ut",     "Tank"];

    function updateHistory() {
        var cfg = PERIOD_CFG[historyHours] || PERIOD_CFG[24];
        var url = "/api/history?hours=" + historyHours + "&limit=" + cfg.limit;
        fetchJSON(url).then(function (data) {
            drawHistoryChart(data.sensors || [], data.heating_periods || [], !!data.heating_on);
        }).catch(function () { /* ignore */ });
    }

    function drawHistoryChart(rows, heatingPeriods, heatingOn) {
        var canvas = document.getElementById("history-chart");
        if (!canvas) return;
        var ctx = canvas.getContext("2d");
        var dpr = window.devicePixelRatio || 1;

        var W = canvas.offsetWidth  || 600;
        var H = canvas.offsetHeight || 260;

        canvas.width  = W * dpr;
        canvas.height = H * dpr;
        ctx.scale(dpr, dpr);

        if (W <= 0 || H <= 0) return;

        ctx.clearRect(0, 0, W, H);

        if (!rows.length) {
            ctx.fillStyle = "#8a8a9a";
            ctx.font = "13px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("Ingen historikk ennå — venter på første syklus", W / 2, H / 2);
            return;
        }

        var pad = { top: 16, right: 96, bottom: 28, left: 42 };
        var cw = W - pad.left - pad.right;
        var ch = H - pad.top  - pad.bottom;

        // Samle alle verdier for skalering
        var allVals = [];
        for (var k = 0; k < H_KEYS.length; k++) {
            for (var i = 0; i < rows.length; i++) {
                var v = rows[i][H_KEYS[k]];
                if (v != null) allVals.push(v);
            }
        }
        if (!allVals.length) return;

        var vMin = Math.floor(Math.min.apply(null, allVals) - 2);
        var vMax = Math.ceil(Math.max.apply(null, allVals)  + 2);

        var times = rows.map(function (r) { return new Date(r.timestamp).getTime(); });
        var tMin  = times[0];
        var tMax  = times[times.length - 1];
        if (tMin >= tMax) tMax = tMin + 600000;

        function xP(t) { return pad.left + (t - tMin) / (tMax - tMin) * cw; }
        function yP(v) { return pad.top  + (1 - (v - vMin) / (vMax - vMin)) * ch; }

        // Varme-PÅ overlay (grønt bakgrunnsband)
        var hSpans = [];
        var hStart = null;
        if (heatingPeriods.length === 0) {
            if (heatingOn) hSpans.push([tMin, tMax]);
        } else {
            var firstType = heatingPeriods[0].event_type;
            if (firstType === "heating_off" || firstType === "manual_off") {
                hStart = tMin; // varme var PÅ ved starten av vinduet
            }
            for (var p = 0; p < heatingPeriods.length; p++) {
                var ev = heatingPeriods[p];
                var et = Math.max(tMin, Math.min(tMax, new Date(ev.timestamp).getTime()));
                var evOn = ev.event_type === "heating_on" || ev.event_type === "manual_on";
                if (evOn && hStart === null) { hStart = et; }
                else if (!evOn && hStart !== null) { hSpans.push([hStart, et]); hStart = null; }
            }
            if (hStart !== null) hSpans.push([hStart, tMax]);
        }
        ctx.fillStyle = "rgba(0, 200, 83, 0.13)";
        for (var sp = 0; sp < hSpans.length; sp++) {
            var sx1 = xP(hSpans[sp][0]);
            var sx2 = xP(hSpans[sp][1]);
            ctx.fillRect(sx1, pad.top, sx2 - sx1, ch);
        }

        // Rutenett og y-akse
        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 1;
        ctx.fillStyle = "#8a8a9a";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";
        for (var i = 0; i <= 4; i++) {
            var gy = pad.top + ch * i / 4;
            var gv = vMax - (vMax - vMin) * i / 4;
            ctx.beginPath(); ctx.moveTo(pad.left, gy); ctx.lineTo(pad.left + cw, gy); ctx.stroke();
            ctx.fillText(gv.toFixed(0) + "\u00b0", pad.left - 4, gy + 4);
        }

        // x-akse tidsetiketter — faste tidsintervaller med minimum avstand
        ctx.textAlign = "center";
        var cfg = PERIOD_CFG[historyHours] || PERIOD_CFG[24];
        var interval = cfg.intervalMs;
        // Sørg for minimum 55px mellom labels for å unngå overlapp
        var minLabelPx = 55;
        var pxPerMs = cw / (tMax - tMin);
        while (interval * pxPerMs < minLabelPx) {
            interval *= 2;
        }
        var firstLabel = Math.ceil(tMin / interval) * interval;
        for (var t = firstLabel; t <= tMax; t += interval) {
            // Ikke tegn label for nær kantene
            var lx = xP(t);
            if (lx < pad.left + 15 || lx > pad.left + cw - 15) continue;
            var d = new Date(t);
            var lbl;
            if (cfg.fmt === "ddd") {
                lbl = NORSK_DAGER[d.getDay()] + " " + d.getDate() + "." + (d.getMonth() + 1);
            } else if (cfg.fmt === "HH:00") {
                lbl = String(d.getHours()).padStart(2, "0") + ":00";
            } else {
                lbl = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
            }
            ctx.fillText(lbl, lx, H - 4);
        }

        // Linjer + etiketter på høyre kant
        for (var k = 0; k < H_KEYS.length; k++) {
            var key = H_KEYS[k];
            ctx.beginPath();
            ctx.strokeStyle = H_COLORS[k];
            ctx.lineWidth = 2;
            var started = false;
            var lx, ly, lv;
            for (var i = 0; i < rows.length; i++) {
                var v = rows[i][key];
                if (v == null) continue;
                var x = xP(times[i]), y = yP(v);
                if (!started) { ctx.moveTo(x, y); started = true; }
                else           { ctx.lineTo(x, y); }
                lx = x; ly = y; lv = v;
            }
            ctx.stroke();
            if (started) {
                ctx.beginPath();
                ctx.fillStyle = H_COLORS[k];
                ctx.arc(lx, ly, 3, 0, Math.PI * 2);
                ctx.fill();
                ctx.textAlign = "left";
                ctx.font = "10px sans-serif";
                ctx.fillText(H_LABELS[k] + " " + lv.toFixed(1) + "\u00b0", lx + 7, ly + 4);
            }
        }
    }

    // Period button handlers
    (function () {
        var btns = document.querySelectorAll(".period-btn");
        for (var i = 0; i < btns.length; i++) {
            btns[i].addEventListener("click", function () {
                for (var j = 0; j < btns.length; j++) btns[j].classList.remove("active");
                this.classList.add("active");
                historyHours = parseInt(this.getAttribute("data-hours"), 10);
                updateHistory();
            });
        }
    })();

    // -- Manual controls --

    window.heatingOn = function () {
        fetchJSON("/api/heating/on", { method: "POST" }).then(function (data) {
            if (data.heating) updateModeButtons(data.heating.mode);
            updateStatus();
            updateLog();
        });
    };

    window.heatingOff = function () {
        fetchJSON("/api/heating/off", { method: "POST" }).then(function (data) {
            if (data.heating) updateModeButtons(data.heating.mode);
            updateStatus();
            updateLog();
        });
    };

    window.heatingAuto = function () {
        fetchJSON("/api/heating/auto", { method: "POST" }).then(function (data) {
            if (data.heating) updateModeButtons(data.heating.mode);
            updateStatus();
            updateLog();
        });
    };

    // -- Threshold controls --

    var thresholdDebounce = null;

    function syncThresholdSliders(t) {
        var ids = {
            "th-ice-min": t.ice_temp_min,
            "th-ice-max": t.ice_temp_max,
            "th-crit-min": t.critical_temp_min,
            "th-crit-max": t.critical_temp_max,
        };
        for (var id in ids) {
            var slider = document.getElementById(id);
            var valEl = document.getElementById(id + "-val");
            if (slider && valEl) {
                slider.value = ids[id];
                valEl.textContent = ids[id].toFixed(1) + "\u00b0C";
            }
        }
    }

    function onThresholdChange() {
        var body = {
            ice_temp_min: parseFloat(document.getElementById("th-ice-min").value),
            ice_temp_max: parseFloat(document.getElementById("th-ice-max").value),
            critical_temp_min: parseFloat(document.getElementById("th-crit-min").value),
            critical_temp_max: parseFloat(document.getElementById("th-crit-max").value),
        };

        // Oppdater visning umiddelbart
        document.getElementById("th-ice-min-val").textContent = body.ice_temp_min.toFixed(1) + "\u00b0C";
        document.getElementById("th-ice-max-val").textContent = body.ice_temp_max.toFixed(1) + "\u00b0C";
        document.getElementById("th-crit-min-val").textContent = body.critical_temp_min.toFixed(1) + "\u00b0C";
        document.getElementById("th-crit-max-val").textContent = body.critical_temp_max.toFixed(1) + "\u00b0C";

        currentThresholds = body;

        // Oppdater prognose-graf umiddelbart
        updateForecast();

        // Debounce API-kall
        clearTimeout(thresholdDebounce);
        thresholdDebounce = setTimeout(function () {
            fetch("/api/thresholds", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-csrf-token": getCsrfToken(),
                },
                body: JSON.stringify(body),
            });
        }, 500);
    }

    (function () {
        var sliders = ["th-ice-min", "th-ice-max", "th-crit-min", "th-crit-max"];
        for (var i = 0; i < sliders.length; i++) {
            var el = document.getElementById(sliders[i]);
            if (el) el.addEventListener("input", onThresholdChange);
        }
    })();

    // -- System info (lokal IP for feilsøking) --

    function updateSystemInfo() {
        fetchJSON("/api/system").then(function (data) {
            if (data.network) {
                var hostEl = document.getElementById("sys-host");
                var ipEl = document.getElementById("sys-ip");
                var verEl = document.getElementById("sys-version");
                if (hostEl) hostEl.textContent = data.network.hostname;
                if (ipEl) ipEl.textContent = data.network.local_ip;
                if (verEl && data.version) verEl.textContent = "v" + data.version;
            }
        }).catch(function () { /* ignore */ });
    }

    // -- Init --

    function poll() {
        updateStatus();
        updateForecast();
        updateHistory();
        updateLog();
    }

    // History chart needs the canvas to be painted before offsetWidth is valid
    updateStatus();
    updateForecast();
    updateLog();
    updateSystemInfo();
    setTimeout(updateHistory, 100);
    pollTimer = setInterval(poll, POLL_INTERVAL);

    // Redraw history chart on resize
    window.addEventListener("resize", updateHistory);
})();
