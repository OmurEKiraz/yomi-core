import sqlite3
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("YomiDB")

class YomiDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # check_same_thread=False, FastAPI (async) ortamında şarttır.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        # slug kolonları ve indexleme performansı artırır
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manga_title TEXT,
                manga_slug TEXT,
                chapter_title TEXT,
                chapter_slug TEXT,
                path TEXT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Hızlı arama için indexler
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_manga_slug ON downloads(manga_slug)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapter_slug ON downloads(chapter_slug)')
        self.conn.commit()

    def _normalize(self, text: str) -> str:
        """Metni standart slug formatına çevirir (küçük harf, boşluksuz)."""
        if not text: return ""
        return "".join(c for c in text.lower() if c.isalnum())

    def is_completed(self, manga_title: str, chapter_title: str) -> bool:
        """
        Bir bölümün indirilip indirilmediğini milisaniyeler içinde kontrol eder.
        """
        m_slug = self._normalize(manga_title)
        c_slug = self._normalize(chapter_title)
        
        # Sadece 1 satır çekmek yeterli (EXISTS mantığı)
        self.cursor.execute(
            'SELECT 1 FROM downloads WHERE manga_slug = ? AND chapter_slug = ? LIMIT 1', 
            (m_slug, c_slug)
        )
        return self.cursor.fetchone() is not None

    def mark_completed(self, manga_title: str, chapter_title: str, path: str = ""):
        """Başarılı indirmeyi kaydeder."""
        try:
            m_slug = self._normalize(manga_title)
            c_slug = self._normalize(chapter_title)
            
            # Tekrarı önlemek için önce kontrol et (veya UNIQUE constraint eklenebilir)
            if not self.is_completed(manga_title, chapter_title):
                self.cursor.execute(
                    '''INSERT INTO downloads (manga_title, manga_slug, chapter_title, chapter_slug, path) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (manga_title, m_slug, chapter_title, c_slug, path)
                )
                self.conn.commit()
        except Exception as e:
            logger.error(f"DB Insert Error: {e}")

    def get_library(self) -> List[Dict]:
        """
        Kütüphane görünümü için indirilmiş serileri gruplar.
        """
        query = '''
            SELECT manga_title, manga_slug, COUNT(chapter_slug) as count, MAX(downloaded_at) as last_update
            FROM downloads 
            GROUP BY manga_slug
            ORDER BY last_update DESC
        '''
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return [
            {
                "title": r[0],
                "slug": r[1],
                "chapter_count": r[2],
                "last_updated": r[3]
            } for r in rows
        ]
    
    def get_manga_chapters(self, manga_slug: str) -> List[str]:
        """Spesifik bir manganın inmiş bölümlerini getirir."""
        # Frontend'de hangi bölümler indi diye göstermek için (renklendirme vb.)
        normalized_slug = self._normalize(manga_slug) # Gelen slug farklı formatta olabilir
        # Ancak DB'de manga_slug zaten normalize kayıtlı olmalı. 
        # Güvenlik için LIKE veya tam eşleşme:
        
        self.cursor.execute(
            'SELECT chapter_title FROM downloads WHERE manga_slug = ?', 
            (normalized_slug,)
        )
        return [r[0] for r in self.cursor.fetchall()]

    def close(self):
        self.conn.close()