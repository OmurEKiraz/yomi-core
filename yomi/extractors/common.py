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
    Asynchronous Generic Extractor v2.0
    
    Uses aiohttp for non-blocking I/O and lxml for high-performance HTML parsing.
    Designed to work with most static manga sites using standard HTML structures.
    """
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://google.com"
        }

    async def get_soup(self, url: str):
        """
        Fetches the URL asynchronously and parses the response with LXML.
        LXML is chosen for being significantly faster than html.parser.
        """
        logger.debug(f"🌐 GET: {url}")
        async with self.session.get(url, headers=self.headers, allow_redirects=True, timeout=30) as response:
            text = await response.text()
            return BeautifulSoup(text, 'lxml'), text

    async def get_manga_info(self, url: str) -> Dict[str, str]:
        """
        Extracts basic manga information (Title) from the page.
        Includes Advanced SEO Cleaning to fix AniList matching errors.
        """
        try:
            soup, _ = await self.get_soup(url)
            
            # Common selectors for Manga Titles
            title_tag = (
                soup.select_one("h1") or 
                soup.select_one(".story-info-right h1") or 
                soup.select_one(".post-title h1") or
                soup.select_one("#chapter-heading")
            )
            
            if title_tag:
                raw_title = title_tag.text.strip()
            else:
                # Fallback: URL'den slug al ve temizle
                raw_title = url.split("/")[-1].replace("-", " ").title()

            # --- ADVANCED CLEANING (SEO Çöpü Temizliği) ---
            # 1. Parantez içindekileri sil (örn: "One Piece (Official)")
            clean_title = re.sub(r'\s*\(.*?\)', '', raw_title)
            
            # 2. Yaygın SEO kelimelerini sil (Case insensitive)
            seo_junk = [
                r'(?i)\s+manga\s+online', r'(?i)\s+manga\s+read', 
                r'(?i)\s+read\s+online', r'(?i)\s+free\s+online',
                r'(?i)\s+english', r'(?i)\s+chapter.*', 
                r'(?i)\s+manga$', r'(?i)\s+manhwa$', r'(?i)\s+manhua$',
                r'(?i)\s+online$', r'(?i)\s+read$'
            ]
            
            for junk in seo_junk:
                clean_title = re.sub(junk, '', clean_title)
            
            clean_title = clean_title.strip()
            
            # Eğer temizlik sonucu boş kaldıysa (örn: başlık sadece "Manga" ise) orjinale dön
            if not clean_title or len(clean_title) < 2:
                clean_title = raw_title

            return {"title": clean_title, "url": url}

        except Exception as e:
            logger.error(f"Failed to extract manga info: {e}")
            slug = url.split("/")[-1].replace("-", " ").title()
            return {"title": slug, "url": url}

    async def get_chapters(self, url: str) -> List[Dict[str, str]]:
        """
        Scrapes chapter links from the manga details page.
        Smartly filters out non-chapter links.
        """
        soup, _ = await self.get_soup(url)
        chapters = []
        
        # Generic selector that covers 80% of manga sites
        # Looks for links containing typical chapter patterns
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip().lower()
            
            # Filter Logic: Must look like a chapter link
            is_chapter = (
                "chapter" in href or "ch-" in href or 
                "chapter" in text or re.search(r'\b\d+\b', text)
            )
            
            if is_chapter:
                full_url = urljoin(url, href)
                # Avoid duplicates and self-references
                if full_url not in [c['url'] for c in chapters] and full_url != url:
                    chapters.append({
                        "title": a.text.strip() or f"Chapter {len(chapters)+1}",
                        "url": full_url
                    })

        # Reverse to have Chapter 1 first (standard reading order)
        return chapters[::-1]

    async def get_pages(self, chapter_url: str) -> List[str]:
        """
        Extracts image URLs from a chapter page.
        Includes heuristics to filter out ads, logos, and banners.
        """
        soup, _ = await self.get_soup(chapter_url)
        images = []
        
        # Identify the container that holds the images
        # Priority order for common reader containers
        reader_area = (
            soup.select_one(".reader-area") or 
            soup.select_one(".reading-content") or 
            soup.select_one("#readerarea") or
            soup.select_one(".container-chapter-reader") or
            soup
        )
        
        for img in reader_area.find_all('img'):
            # Some sites use 'data-src' for lazy loading
            src = img.get('data-src') or img.get('src')
            
            if src:
                clean_url = src.strip()
                
                # --- Filter: Ad & Junk Removal ---
                if any(x in clean_url.lower() for x in ["logo", "icon", "ads", "banner", "loader", "pixel", "100x", "300x", "facebook", "twitter"]): 
                    continue

                # --- Patch: NANGCA Protocol Fix ---
                # Some sites like nangca use protocol-relative URLs or broken schemas
                if "nangca.com" in clean_url:
                    if not clean_url.startswith("http"):
                        clean_url = "https:" + clean_url if clean_url.startswith("//") else "https://" + clean_url
                    images.append(clean_url)
                    continue

                final_url = urljoin(chapter_url, clean_url)
                if final_url.startswith("http"):
                    images.append(final_url)

        return list(dict.fromkeys(images)) # Remove duplicates while preserving order

    async def download_image(self, url: str, path: str):
        """
        Asynchronously downloads an image to the specified path.
        """
        try:
            async with self.session.get(url, headers=self.headers, timeout=60) as response:
                if response.status == 200:
                    async with aiofiles.open(path, 'wb') as f:
                        await f.write(await response.read())
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")