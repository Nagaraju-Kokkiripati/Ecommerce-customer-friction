import sqlite3
import unittest
from datetime import datetime, timezone, timedelta
import json
from ml.train_captured import samples


class TestCapturedTraining(unittest.TestCase):
    def test_training_excludes_terminal_outcomes(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript("CREATE TABLE journeys(id TEXT,customer_id TEXT,created TEXT); CREATE TABLE events(id INTEGER PRIMARY KEY,session_id TEXT,type TEXT,timestamp TEXT,details TEXT);")
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        db.execute("INSERT INTO journeys VALUES('session','customer',?)", (old,))
        for kind, detail in [("add_to_cart", {"product_id":"p1","quantity":1}), ("payment_attempt",{}), ("payment_success",{}), ("order_placed",{}), ("search",{})]:
            db.execute("INSERT INTO events(session_id,type,timestamp,details) VALUES('session',?,?,?)", (kind, old, json.dumps(detail)))
        records = samples(db, datetime.now(timezone.utc) - timedelta(days=1))
        self.assertEqual(records[0]["label"], 0)
        self.assertEqual(records[0]["features"]["num_events"], 2)
        self.assertEqual(records[0]["features"]["num_searches"], 0)
        self.assertEqual(records[0]["features"]["exited_at_checkout"], 0)
        db.close()
