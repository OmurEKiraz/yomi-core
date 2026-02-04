import os
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

from .extractors.common import GenericMangaExtractor
from .converters import convert_to_pdf, convert_to_cbz
from .database import YomiDB

# Quiet down the logs so they don't break the progress bar
logging.basicConfig(level=logging.ERROR) 
logger = logging.getLogger("YomiCore")

class YomiCore:
    def __init__(self, output_dir: str = "downloads", workers: int = 4, debug: bool = False, format: str = "folder", proxy: str = None):
        self.output_dir = output_dir
        self.workers = workers
        self.format = format.lower()
        self.debug = debug
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Pass the proxy here!
        self.extractor = GenericMangaExtractor(proxy=proxy)
        self.db = YomiDB(os.path.join(output_dir, "history.db"))

    def download_manga(self, url: str, chapter_range: str = None):
        try:
            print(f"🔍 Analyzing: {url}...")
            manga_info = self.extractor.get_manga_info(url)
            manga_title = manga_info['title']
            
            safe_title = "".join([c for c in manga_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            manga_path = os.path.join(self.output_dir, safe_title)
            os.makedirs(manga_path, exist_ok=True)
            
            print(f"📘 Target: {manga_title}")
            
            all_chapters = self.extractor.get_chapters(url)
            chapters = self._filter_chapters(all_chapters, chapter_range)
            
            if not chapters:
                print("❌ No chapters found matching criteria.")
                return

            print(f"🚀 Queued {len(chapters)} chapters...")

            # --- FANCY PROGRESS BAR ---
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
            ) as progress:
                
                # Create a task for the Total Manga
                manga_task = progress.add_task(f"[green]Downloading {manga_title}", total=len(chapters))

                for chapter in chapters:
                    # Check DB first
                    if self.db.is_completed(manga_title, chapter['title']):
                        progress.console.print(f"[dim]Skipping {chapter['title']} (Done)[/dim]")
                        progress.advance(manga_task)
                        continue

                    # Process Chapter
                    self._download_single_chapter(chapter, manga_path, manga_title, progress)
                    progress.advance(manga_task)

        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.db.close()

    def _filter_chapters(self, chapters: list, range_str: str):
        if not range_str: return chapters
        try:
            start, end = map(float, range_str.split('-'))
            filtered = []
            for chap in chapters:
                import re
                match = re.search(r'(\d+(\.\d+)?)', chap['title'])
                if match and start <= float(match.group(1)) <= end:
                    filtered.append(chap)
            return filtered
        except:
            return chapters

    def _download_single_chapter(self, chapter: dict, parent_path: str, manga_title: str, progress):
        chapter_title = chapter['title']
        clean_title = chapter_title.replace('.', '-')
        safe_name = "".join([c for c in clean_title if c.isalnum() or c in (' ', '-', '_')]).strip()
        chapter_folder = os.path.join(parent_path, safe_name)
        os.makedirs(chapter_folder, exist_ok=True)

        try:
            pages = self.extractor.get_pages(chapter['url'])
            if not pages: return

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = []
                for idx, img_url in enumerate(pages):
                    ext = "jpg"
                    fname = f"{idx + 1:03d}.{ext}"
                    save_path = os.path.join(chapter_folder, fname)
                    futures.append(executor.submit(self.extractor.download_image, img_url, save_path, chapter['url']))

                for future in as_completed(futures):
                    future.result()

            # Conversion
            if self.format == "pdf":
                pdf_path = os.path.join(parent_path, f"{safe_name}.pdf")
                if convert_to_pdf(chapter_folder, pdf_path):
                    shutil.rmtree(chapter_folder)
                    self.db.mark_completed(manga_title, chapter_title)
                    progress.console.print(f"[green]✅ Finished: {safe_name}[/green]")
            
            elif self.format == "cbz":
                cbz_path = os.path.join(parent_path, f"{safe_name}.cbz")
                if convert_to_cbz(chapter_folder, cbz_path):
                    shutil.rmtree(chapter_folder)
                    self.db.mark_completed(manga_title, chapter_title)
                    progress.console.print(f"[green]✅ Finished: {safe_name}[/green]")
            else:
                 # If just folder mode, mark complete after download
                 self.db.mark_completed(manga_title, chapter_title)
                 progress.console.print(f"[green]✅ Finished: {safe_name}[/green]")

        except Exception as e:
            progress.console.print(f"[red]Failed {chapter_title}: {e}[/red]")