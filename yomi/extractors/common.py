import logging
from typing import List, Dict
from .base import BaseExtractor
from urllib.parse import urljoin

logger = logging.getLogger("YomiCore")

class GenericMangaExtractor(BaseExtractor):
    """
    Universal Extractor for WordPress/PHP Manga Sites.
    """
    @property
    def base_url(self) -> str:
        return "generic"

    def get_manga_info(self, url: str) -> Dict[str, str]:
        # PHASE 1: Check if this is a Chapter URL
        if "chapter-" in url.lower():
            logger.info("📍 Detected Chapter URL. Fetching Series Info from Parent...")
            soup = self.get_soup(url)
            parent_url = self._find_parent_url(soup, url)
            
            if parent_url:
                # RECURSION: Get info from the Parent Page instead!
                return self.get_manga_info(parent_url)

        # PHASE 2: Normal Info Extraction (Series Page)
        soup = self.get_soup(url)
        
        title = "Unknown Manga"
        # Try finding the big H1 title
        for selector in ["h1.entry-title", "h1", "div.post-title h1", "div.big-title h1"]:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break
        
        # Clean up title (remove "Manga", "Manhwa" suffixes if common)
        return {
            "title": title,
            "url": url
        }

    def get_chapters(self, manga_url: str) -> List[Dict]:
        # Force Redirect Logic
        if "chapter-" in manga_url.lower():
            soup = self.get_soup(manga_url)
            parent_url = self._find_parent_url(soup, manga_url)
            if parent_url and parent_url != manga_url:
                logger.info(f"🚀 Redirecting to Series Home: {parent_url}")
                return self.get_chapters(parent_url)

        soup = self.get_soup(manga_url)
        chapters = []
        links = soup.select("a")
        seen_urls = set()
        
        for link in links:
            href = link.get("href")
            text = link.get_text(strip=True)
            if not href: continue
            
            full_url = urljoin(manga_url, href)
            if full_url in seen_urls: continue
            if "facebook" in full_url or "twitter" in full_url: continue
            
            # Logic: Must contain "chapter" digit or "chapter-" in url
            is_chapter = False
            if "chapter" in text.lower() and any(c.isdigit() for c in text):
                is_chapter = True
            elif "chapter-" in href.lower():
                is_chapter = True
            
            if text.strip().lower() in ["next", "prev", "next chapter", "previous"]:
                is_chapter = False

            if is_chapter:
                chapters.append({"title": text, "url": full_url})
                seen_urls.add(full_url)
        
        # Sort Reverse (Chapter 1 first)
        return list(reversed(chapters))

    def get_pages(self, chapter_url: str) -> List[str]:
        soup = self.get_soup(chapter_url)
        images = []
        img_tags = soup.select("img")
        
        for img in img_tags:
            # Smart Lazy Load Check
            candidates = [img.get("data-src"), img.get("data-lazy-src"), img.get("src")]
            final_src = None
            for src in candidates:
                if src and not src.startswith("data:"):
                    final_src = src.strip()
                    break
            
            if not final_src: continue
            full_src = urljoin(chapter_url, final_src)
            
            if any(x in full_src.lower() for x in ["logo", "icon", "ads", "banner"]): continue
            
            images.append(full_src)

        return list(dict.fromkeys(images))

    def _find_parent_url(self, soup, current_url) -> str:
        # 1. Breadcrumbs
        breadcrumbs = soup.select(".breadcrumb a, .yoast-breadcrumbs a")
        if breadcrumbs:
            for link in reversed(breadcrumbs):
                href = link.get("href")
                if href and href != current_url and "home" not in link.get_text().lower():
                    return urljoin(current_url, href)
        # 2. "All Chapters" Link
        for link in soup.select("a"):
            if "all chapters" in link.get_text().lower():
                return urljoin(current_url, link.get("href"))
        # 3. Trim URL
        try:
            parts = current_url.rstrip('/').split('/')
            if "chapter" in parts[-1]:
                return "/".join(parts[:-1])
        except: pass
        return None