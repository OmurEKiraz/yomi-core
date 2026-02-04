import abc
from curl_cffi import requests as curl_requests # Use for Scraping
import requests # Use for Downloading
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import quote, urlparse, urlunparse
import os

class BaseExtractor(abc.ABC):
    """
    Hybrid Extractor:
    - curl_cffi: Bypasses Cloudflare to find chapters.
    - requests: Reliably downloads images.
    - Proxy Support: Can tunnel traffic if provided.
    """

    def __init__(self, proxy: str = None):
        # 1. Scraper Session (High Tech)
        self.scraper = curl_requests.Session(impersonate="chrome120")
        self.scraper.headers.update({
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        # 2. Downloader Session (Reliable Tech)
        self.downloader = requests.Session()
        self.downloader.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        })

        # 3. Apply Proxy if exists
        if proxy:
            proxies = {"http": proxy, "https": proxy}
            self.scraper.proxies = proxies
            self.downloader.proxies = proxies

    @property
    @abc.abstractmethod
    def base_url(self) -> str:
        pass

    @abc.abstractmethod
    def get_manga_info(self, url: str) -> Dict[str, str]:
        pass

    @abc.abstractmethod
    def get_chapters(self, manga_url: str) -> List[Dict]:
        pass

    @abc.abstractmethod
    def get_pages(self, chapter_url: str) -> List[str]:
        pass

    def _sanitize_url(self, url: str) -> str:
        if not url: return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        parts = list(urlparse(url))
        parts[2] = quote(parts[2]) 
        return urlunparse(parts)

    def get_soup(self, url: str) -> BeautifulSoup:
        clean_url = self._sanitize_url(url)
        # Use Scraper for HTML
        self.scraper.headers["Referer"] = clean_url
        response = self.scraper.get(clean_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"HTTP Error {response.status_code} for {url}")
        return BeautifulSoup(response.content, "html.parser")

    def download_image(self, url: str, save_path: str, source_chapter_url: str = None) -> bool:
        """
        Downloads image using standard requests with 3-way retry strategy.
        """
        clean_url = self._sanitize_url(url)
        
        # Strategies to trick the server
        strategies = [
            # 1. Referer = Chapter URL (Best for hotlink protection)
            {"Referer": source_chapter_url if source_chapter_url else ""},
            # 2. Referer = None (Best for CDNs)
            {"Referer": ""},
            # 3. Referer = Root Domain (Fallback)
            {"Referer": f"{urlparse(clean_url).scheme}://{urlparse(clean_url).netloc}/"}
        ]

        for headers in strategies:
            try:
                # Merge strategy headers
                self.downloader.headers.update(headers)
                
                # Download with standard requests
                response = self.downloader.get(clean_url, stream=True, timeout=20)
                
                if response.status_code == 200:
                    # CHECK: Is it a ghost file (0 bytes)?
                    if len(response.content) == 0:
                        continue 
                        
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Verify on disk
                    if os.path.getsize(save_path) > 0:
                        return True # Success! We got real data.
                    
            except Exception:
                continue # Try next strategy

        return False # All failed