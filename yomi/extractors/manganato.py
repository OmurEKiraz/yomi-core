from .base import BaseExtractor
from typing import List, Dict
from urllib.parse import quote

class ManganatoExtractor(BaseExtractor):
    """
    Extractor for Manganato/Manganelo (The 'Main Base').
    """
    def __init__(self, proxy: str = None):
        super().__init__(proxy)
        self.search_url = "https://manganato.com/search/story/"

    @property
    def base_url(self) -> str:
        return "manganato.com"

    def get_manga_info(self, url: str) -> Dict[str, str]:
        soup = self.get_soup(url)
        
        # Manganato Title Selector
        title_box = soup.select_one("div.story-info-right h1")
        if not title_box:
            title_box = soup.select_one("ul.manga-info-text li h1")
            
        title = title_box.get_text(strip=True) if title_box else "Unknown Manga"
        return {"title": title, "url": url}

    def get_chapters(self, manga_url: str) -> List[Dict]:
        soup = self.get_soup(manga_url)
        chapters = []
        
        links = soup.select("a.chapter-name")
        
        for link in reversed(links): 
            chapters.append({
                "title": link.get_text(strip=True),
                "url": link.get("href")
            })
            
        return chapters

    def get_pages(self, chapter_url: str) -> List[str]:
        soup = self.get_soup(chapter_url)
        images = []
        
        for img in soup.select("div.container-chapter-reader img"):
            src = img.get("src")
            if src:
                images.append(src)
                
        return images

    def search(self, query: str) -> List[Dict]:
        clean_query = query.lower().replace(" ", "_")
        target = f"{self.search_url}{clean_query}"
        
        try:
            soup = self.get_soup(target)
            results = []
            
            items = soup.select("div.search-story-item")
            for item in items[:15]: 
                title_tag = item.select_one("a.item-title")
                if title_tag:
                    results.append({
                        "title": title_tag.get_text(strip=True),
                        "url": title_tag.get("href")
                    })
            return results
        except Exception as e:
            print(f"Search Error: {e}")
            return []