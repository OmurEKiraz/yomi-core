import sqlite3
import os

class YomiDB:
    def __init__(self, db_path="yomi_history.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_table()

    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga_title TEXT,
            chapter_title TEXT,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(manga_title, chapter_title)
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def is_completed(self, manga_title, chapter_title):
        """Check if a chapter is already marked as done."""
        cursor = self.conn.execute(
            "SELECT 1 FROM downloads WHERE manga_title = ? AND chapter_title = ? AND status = 'completed'",
            (manga_title, chapter_title)
        )
        return cursor.fetchone() is not None

    def mark_completed(self, manga_title, chapter_title):
        """Mark a chapter as finished."""
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO downloads (manga_title, chapter_title, status) VALUES (?, ?, 'completed')",
                (manga_title, chapter_title)
            )
            self.conn.commit()
        except Exception as e:
            print(f"DB Error: {e}")

    def close(self):
        self.conn.close()