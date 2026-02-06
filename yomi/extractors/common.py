import logging
import re
import aiohttp
import aiofiles
from typing import List, Dict
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger("YomiCore")

class AsyncGenericMangaExtractor:
    """
    Async Extractor v2.0 - Powered by Aiohttp & LXML
    """
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://google.com"
        }

    async def get_soup(self, url):
        """
        Fetches URL asynchronously and parses with LXML (C-based parser).
        """
        logger.debug(f"🌐 GET: {url}")
        async with self.session.get(url, headers=self.headers, allow_redirects=True, timeout=30) as response:
            text = await response.text()
            # 'lxml' is 10x faster than 'html.parser'
            return BeautifulSoup(text, 'lxml'), text

    async def get_manga_info(self, url: str) -> Dict[str, str]:
        # Handle redirects or chapter links to series links recursively
        if "chapter-" in url.lower() or "/chapter/" in url.lower():
            soup, _ = await self.get_soup(url)
            parent_url = await self._find_parent_url(soup, url)
            if parent_url: return await self.get_manga_info(parent_url)

        soup, _ = await self.get_soup(url)
        title = "Unknown Manga"
        
        # Fast selector matching
        selectors = ["div.post-title h1", "h1.entry-title", "div.big-title h1", "h1", "title"]
        for selector in selectors:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break
        
        clean_title = title.replace("Manga", "").replace("Read", "").replace("Online", "").strip()
        clean_title = clean_title.strip("-").strip()
        return {"title": clean_title, "url": url}

    async def get_chapters(self, manga_url: str) -> List[Dict]:
        # If user gave a chapter link, find the parent first
        if "chapter-" in manga_url.lower():
            soup, _ = await self.get_soup(manga_url)
            parent_url = await self._find_parent_url(soup, manga_url)
            if parent_url and parent_url != manga_url:
                return await self.get_chapters(parent_url)

        soup, _ = await self.get_soup(manga_url)
        manga_info = await self.get_manga_info(manga_url)
        series_title = manga_info['title'].lower()
        
        chapters = []
        seen_urls = set()

        # Try specific selector first, fall back to all links
        madara_chapters = soup.select('li.wp-manga-chapter a')
        target_links = madara_chapters if madara_chapters else soup.select("a")

        for link in target_links:
            href = link.get('href')
            text = link.get_text(strip=True)
            if not href: continue
            
            full_url = urljoin(manga_url, href)
            
            # --- FILTERS ---
            if full_url.strip('/') == manga_url.strip('/'): continue
            if full_url in seen_urls: continue
            if any(x in text.lower() for x in ["enjoy reading", "start reading", "read now"]): continue
            if "ragnarok" in text.lower() and "ragnarok" not in series_title: continue
            if any(x in full_url for x in ["#", "comment", "reply", "login", "facebook", "twitter"]): continue

            is_chapter = False
            if madara_chapters and link in madara_chapters: is_chapter = True
            elif "chapter" in text.lower() and any(c.isdigit() for c in text): is_chapter = True
            elif "/chapter-" in href.lower() or "/ch-" in href.lower(): is_chapter = True

            if is_chapter:
                chapters.append({"title": text, "url": full_url})
                seen_urls.add(full_url)
        
        return list(reversed(chapters))

    async def get_pages(self, chapter_url: str) -> List[str]:
        # 1. Direct Image Check
        if chapter_url.endswith(('.webp', '.jpg', '.png')):
             return [chapter_url]

        soup, html_content = await self.get_soup(chapter_url)
        images = []
        
        # --- STRATEGY 1: Attribute Harvesting ---
        img_tags = soup.find_all("img")
        for img in img_tags:
            for attr_name, attr_val in img.attrs.items():
                if isinstance(attr_val, list): attr_val = " ".join(attr_val)
                if not attr_val: continue
                
                val_lower = attr_val.lower().strip()
                if ".jpg" in val_lower or ".png" in val_lower or ".webp" in val_lower:
                    if "data:" in val_lower or "logo" in val_lower or "icon" in val_lower: continue
                    full_src = urljoin(chapter_url, attr_val.strip())
                    images.append(full_src)
                    break 

        # --- STRATEGY 2: Sherlock Scan (Regex) ---
        if not images:
            regex = r'["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']'
            matches = re.findall(regex, html_content)
            
            for raw_url in matches:
                clean_url = raw_url.replace(r'\/', '/').replace('\\', '').strip()
                
                if any(x in clean_url.lower() for x in ["logo", "icon", "ads", "banner", "loader", "pixel", "100x", "300x"]): 
                    continue

                # NANGCA Patch
                if "nangca.com" in clean_url:
                    if not clean_url.startswith("http"):
                        clean_url = "https:" + clean_url if clean_url.startswith("//") else "https://" + clean_url
                    images.append(clean_url)
                    continue

                final_url = urljoin(chapter_url, clean_url)
                if final_url.startswith("http"):
                    images.append(final_url)

        return list(dict.fromkeys(images)) # Remove duplicates

    async def _find_parent_url(self, soup, current_url) -> str:
        back_link = soup.select_one("a.btn.back") or soup.select_one("a.all-chapters")
        if back_link: return urljoin(current_url, back_link.get("href"))
        return None

    async def download_image(self, url, path):
        try:
            async with self.session.get(url, headers=self.headers, timeout=60) as response:
                if response.status == 200:
                    # 'aiofiles' writes to disk without blocking the event loop
                    async with aiofiles.open(path, 'wb') as f:
                        await f.write(await response.read())
                    return True
        except Exception as e:
            logger.debug(f"Download failed for {url}: {e}")
        return False