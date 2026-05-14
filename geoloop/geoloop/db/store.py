from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Store:
    """SQLite-basert logging for GeoLoop."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(
            str(path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate()

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS weather_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                temperature    REAL,
                precipitation  REAL,
                humidity       REAL,
                wind_speed     REAL
            );

            CREATE TABLE IF NOT EXISTS sensor_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                sensor_id TEXT    NOT NULL,
                value     REAL,
                compacted INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_sensor_log_ts
                ON sensor_log (timestamp);

            CREATE TABLE IF NOT EXISTS system_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT    NOT NULL,
                event_type TEXT    NOT NULL,
                message    TEXT
            );
        """)
        self._conn.commit()

    def _migrate(self) -> None:
        """Legg til nye kolonner/indekser for eksisterende databaser."""
        cur = self._conn.cursor()
        columns = {row[1] for row in cur.execute("PRAGMA table_info(sensor_log)").fetchall()}
        if "compacted" not in columns:
            cur.execute("ALTER TABLE sensor_log ADD COLUMN compacted INTEGER DEFAULT 0")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_ts ON sensor_log (timestamp)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_compacted ON sensor_log (compacted, timestamp)")
            self._conn.commit()

    def log_weather(
        self,
        *,
        temperature: float | None = None,
        precipitation: float | None = None,
        humidity: float | None = None,
        wind_speed: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO weather_log (timestamp, temperature, precipitation, humidity, wind_speed) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, temperature, precipitation, humidity, wind_speed),
        )
        self._conn.commit()

    def log_sensor(
        self,
        sensor_id: str,
        value: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO sensor_log (timestamp, sensor_id, value) VALUES (?, ?, ?)",
            (ts, sensor_id, value),
        )
        self._conn.commit()

    def log_event(
        self,
        event_type: str,
        message: str = "",
        *,
        timestamp: datetime | None = None,
    ) -> None:
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO system_events (timestamp, event_type, message) VALUES (?, ?, ?)",
            (ts, event_type, message),
        )
        self._conn.commit()

    def compact_sensor_data(self) -> None:
        """Rullerende kompaktering av sensordata.

        Retensjonspolicy:
          0–1t:   full oppløsning (compacted=0)
          1t–24t: 5-min snitt     (compacted=1)
          24t–7d: 30-min snitt    (compacted=2)
          >7d:    slett
        """
        now = datetime.now(timezone.utc)
        cur = self._conn.cursor()

        # Slett data eldre enn 7 dager
        ts_7d = (now - timedelta(days=7)).isoformat()
        cur.execute("DELETE FROM sensor_log WHERE timestamp < ?", (ts_7d,))

        # Komprimer 24t–7d til 30-min bøtter (level 2)
        ts_24h = (now - timedelta(hours=24)).isoformat()
        self._compact_range(cur, ts_7d, ts_24h, bucket_minutes=30, level=2)

        # Komprimer 1t–24t til 5-min bøtter (level 1)
        ts_1h = (now - timedelta(hours=1)).isoformat()
        self._compact_range(cur, ts_24h, ts_1h, bucket_minutes=5, level=1)

        self._conn.commit()

    def _compact_range(
        self,
        cur: sqlite3.Cursor,
        ts_from: str,
        ts_to: str,
        bucket_minutes: int,
        level: int,
    ) -> None:
        """Komprimer rå-data i et tidsvindu til gjennomsnittsverdier per bøtte."""
        bucket_expr = (
            "strftime('%Y-%m-%dT%H:', timestamp) || "
            f"printf('%02d', (CAST(strftime('%M', timestamp) AS INTEGER) / {bucket_minutes}) * {bucket_minutes})"
        )

        # Sett inn gjennomsnitt per bøtte
        cur.execute(f"""
            INSERT INTO sensor_log (timestamp, sensor_id, value, compacted)
            SELECT {bucket_expr} || ':00Z',
                   sensor_id,
                   AVG(value),
                   ?
            FROM sensor_log
            WHERE timestamp >= ? AND timestamp < ?
              AND compacted < ?
            GROUP BY {bucket_expr}, sensor_id
            HAVING COUNT(*) > 0
        """, (level, ts_from, ts_to, level))

        # Slett originalene som ble kompaktert
        cur.execute("""
            DELETE FROM sensor_log
            WHERE timestamp >= ? AND timestamp < ?
              AND compacted < ?
        """, (ts_from, ts_to, level))

    def get_weather_log(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM weather_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_sensor_log(
        self, sensor_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        if sensor_id:
            rows = self._conn.execute(
                "SELECT * FROM sensor_log WHERE sensor_id = ? ORDER BY id DESC LIMIT ?",
                (sensor_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM sensor_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_events(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM system_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_sensor_history(self, hours: int = 24, limit: int = 0) -> list[dict]:
        """Hent sensordata pivotert per tidsstempel for de siste N timer.

        Når limit > 0 og antall datapunkter overstiger limit, brukes
        tidsbøtte-gruppering for nedsampling.
        """
        since = (
            datetime.now(timezone.utc)
            - timedelta(hours=hours)
        ).isoformat()

        if limit > 0:
            count = self._conn.execute(
                "SELECT COUNT(DISTINCT timestamp) FROM sensor_log WHERE timestamp >= ?",
                (since,),
            ).fetchone()[0]
            if count > limit:
                bucket_seconds = int(hours * 3600 / limit)
                return self._get_sensor_history_bucketed(since, bucket_seconds)

        rows = self._conn.execute(
            """
            SELECT strftime('%Y-%m-%dT%H:%M:%SZ', MIN(timestamp)) AS timestamp,
                   MAX(CASE WHEN sensor_id = 'loop_inlet'  THEN value END) AS loop_inlet,
                   MAX(CASE WHEN sensor_id = 'loop_outlet' THEN value END) AS loop_outlet,
                   MAX(CASE WHEN sensor_id = 'hp_inlet'    THEN value END) AS hp_inlet,
                   MAX(CASE WHEN sensor_id = 'hp_outlet'   THEN value END) AS hp_outlet,
                   MAX(CASE WHEN sensor_id = 'tank'        THEN value END) AS tank
            FROM sensor_log
            WHERE timestamp >= ?
            GROUP BY strftime('%Y-%m-%dT%H:%M:%S', timestamp)
            ORDER BY timestamp ASC
            """,
            (since,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _get_sensor_history_bucketed(self, since: str, bucket_seconds: int) -> list[dict]:
        """Nedsampling med tidsbøtter for store tidsperioder."""
        bucket_expr = (
            f"(CAST(strftime('%s', timestamp) AS INTEGER) / {bucket_seconds}) * {bucket_seconds}"
        )
        rows = self._conn.execute(
            f"""
            SELECT strftime('%Y-%m-%dT%H:%M:%SZ', {bucket_expr}, 'unixepoch') AS timestamp,
                   AVG(CASE WHEN sensor_id = 'loop_inlet'  THEN value END) AS loop_inlet,
                   AVG(CASE WHEN sensor_id = 'loop_outlet' THEN value END) AS loop_outlet,
                   AVG(CASE WHEN sensor_id = 'hp_inlet'    THEN value END) AS hp_inlet,
                   AVG(CASE WHEN sensor_id = 'hp_outlet'   THEN value END) AS hp_outlet,
                   AVG(CASE WHEN sensor_id = 'tank'        THEN value END) AS tank
            FROM sensor_log
            WHERE timestamp >= ?
            GROUP BY {bucket_expr}
            ORDER BY 1 ASC
            """,
            (since,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_heating_periods(self, hours: int = 24) -> list[dict]:
        """Hent VP av/på-hendelser for de siste N timer."""
        since = (
            datetime.now(timezone.utc)
            - timedelta(hours=hours)
        ).isoformat()
        rows = self._conn.execute(
            """
            SELECT timestamp, event_type
            FROM system_events
            WHERE event_type IN ('heating_on', 'heating_off', 'manual_on', 'manual_off')
              AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (since,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
