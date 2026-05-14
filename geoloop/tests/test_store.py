from datetime import datetime, timedelta, timezone

from geoloop.db.store import Store


class TestStore:
    def setup_method(self):
        self.store = Store(":memory:")

    def teardown_method(self):
        self.store.close()

    def test_should_insert_weather_log_when_called(self):
        self.store.log_weather(temperature=-3.0, precipitation=0.5)
        rows = self.store.get_weather_log()
        assert len(rows) == 1
        assert rows[0]["temperature"] == -3.0
        assert rows[0]["precipitation"] == 0.5

    def test_should_store_timestamp_when_provided(self):
        ts = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        self.store.log_weather(temperature=1.0, timestamp=ts)
        rows = self.store.get_weather_log()
        assert rows[0]["timestamp"] == ts.isoformat()

    def test_should_insert_sensor_log_when_called(self):
        self.store.log_sensor("temp_bakke_1", 5.2)
        rows = self.store.get_sensor_log()
        assert len(rows) == 1
        assert rows[0]["sensor_id"] == "temp_bakke_1"
        assert rows[0]["value"] == 5.2

    def test_should_filter_sensor_log_when_sensor_id_provided(self):
        self.store.log_sensor("sensor_a", 1.0)
        self.store.log_sensor("sensor_b", 2.0)
        rows = self.store.get_sensor_log(sensor_id="sensor_a")
        assert len(rows) == 1
        assert rows[0]["sensor_id"] == "sensor_a"

    def test_should_insert_event_when_called(self):
        self.store.log_event("startup", "System startet")
        rows = self.store.get_events()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "startup"
        assert rows[0]["message"] == "System startet"

    def test_should_respect_limit_when_querying_weather(self):
        for i in range(10):
            self.store.log_weather(temperature=float(i))
        rows = self.store.get_weather_log(limit=3)
        assert len(rows) == 3

    def test_should_return_newest_first_when_querying(self):
        self.store.log_weather(temperature=1.0)
        self.store.log_weather(temperature=2.0)
        rows = self.store.get_weather_log()
        assert rows[0]["temperature"] == 2.0


class TestCompaction:
    def setup_method(self):
        self.store = Store(":memory:")
        self.now = datetime.now(timezone.utc)

    def teardown_method(self):
        self.store.close()

    def _insert_sensor(self, sensor_id, value, minutes_ago):
        ts = self.now - timedelta(minutes=minutes_ago)
        self.store.log_sensor(sensor_id, value, timestamp=ts)

    def _count_rows(self, compacted=None):
        if compacted is not None:
            return self.store._conn.execute(
                "SELECT COUNT(*) FROM sensor_log WHERE compacted = ?", (compacted,)
            ).fetchone()[0]
        return self.store._conn.execute("SELECT COUNT(*) FROM sensor_log").fetchone()[0]

    def test_should_add_compacted_column(self):
        cols = {
            row[1]
            for row in self.store._conn.execute("PRAGMA table_info(sensor_log)").fetchall()
        }
        assert "compacted" in cols

    def test_should_keep_recent_data(self):
        # Data under 1 time gammel skal ikke røres
        for i in range(10):
            self._insert_sensor("loop_inlet", 20.0 + i * 0.1, minutes_ago=i * 5)
        self.store.compact_sensor_data()
        assert self._count_rows(compacted=0) == 10

    def test_should_compact_1h_24h_to_5min(self):
        # Sett inn data hvert minutt mellom 2t og 3t siden
        for i in range(60):
            self._insert_sensor("loop_inlet", 20.0 + i * 0.1, minutes_ago=120 + i)
        before = self._count_rows()
        self.store.compact_sensor_data()
        after_raw = self._count_rows(compacted=0)
        after_compacted = self._count_rows(compacted=1)
        # Originale rå-rader skal være slettet
        assert after_raw == 0
        # Kompakterte rader (5-min bøtter over 60 min) => ~12 bøtter
        assert after_compacted > 0
        assert after_compacted <= 13  # 60/5 + 1

    def test_should_compact_24h_7d_to_30min(self):
        # Sett inn data hvert 5. minutt mellom 25t og 26t siden
        for i in range(12):
            self._insert_sensor("tank", 40.0 + i * 0.5, minutes_ago=25 * 60 + i * 5)
        self.store.compact_sensor_data()
        after_l2 = self._count_rows(compacted=2)
        after_raw = self._count_rows(compacted=0)
        assert after_raw == 0
        # 60 min / 30-min bøtter => ~2 bøtter
        assert after_l2 > 0
        assert after_l2 <= 3

    def test_should_delete_older_than_7d(self):
        # Data eldre enn 7 dager skal slettes
        self._insert_sensor("loop_inlet", 15.0, minutes_ago=7 * 24 * 60 + 60)
        self._insert_sensor("loop_inlet", 16.0, minutes_ago=7 * 24 * 60 + 120)
        assert self._count_rows() == 2
        self.store.compact_sensor_data()
        assert self._count_rows() == 0


class TestSensorHistoryLimit:
    def setup_method(self):
        self.store = Store(":memory:")
        self.now = datetime.now(timezone.utc)

    def teardown_method(self):
        self.store.close()

    def _insert_sensor(self, sensor_id, value, minutes_ago):
        ts = self.now - timedelta(minutes=minutes_ago)
        self.store.log_sensor(sensor_id, value, timestamp=ts)

    def test_should_return_all_when_no_limit(self):
        for i in range(30):
            self._insert_sensor("loop_inlet", 20.0 + i, minutes_ago=i)
        rows = self.store.get_sensor_history(hours=1, limit=0)
        assert len(rows) == 30

    def test_should_downsample_when_limit_exceeded(self):
        # Sett inn 60 rader (1 per minutt) for siste time
        for i in range(60):
            self._insert_sensor("loop_inlet", 20.0 + i * 0.1, minutes_ago=i)
        rows_all = self.store.get_sensor_history(hours=1, limit=0)
        rows_limited = self.store.get_sensor_history(hours=1, limit=10)
        # Nedsampling skal gi færre rader enn totalt
        assert len(rows_limited) < len(rows_all)
        assert len(rows_limited) <= 15  # Noe mer enn limit pga bøtte-avrunding
