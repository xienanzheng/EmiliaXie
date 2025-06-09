import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app

def test_init_db(tmp_path):
    db_path = tmp_path / "baby_tracker.db"
    # Temporarily change working directory to use tmp db
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        app.init_db()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
        assert cursor.fetchone() is not None
    finally:
        conn.close()
        os.chdir(cwd)
