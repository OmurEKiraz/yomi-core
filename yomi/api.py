import os
import asyncio
import aiohttp
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Yomi Core Imports
from .core import YomiCore
from .database import YomiDB
from .utils.anilist import AniListProvider

# --- 1. DATA MODELS (Pydantic) ---
# Frontend'in ne beklemesi gerektiğini netleştiren şemalar
class SearchResult(BaseModel):
    slug: str
    name: str
    confidence: int
    base_domain: str

class ChapterInfo(BaseModel):
    title: str
    url: str
    is_downloaded: bool = False

class MangaDetails(BaseModel):
    slug: str
    title: str
    metadata: Optional[Dict]
    chapters: List[ChapterInfo]

class TaskStatus(BaseModel):
    slug: str
    status: str  # pending, downloading, completed, failed
    progress: int
    message: str
    timestamp: str

class DownloadRequest(BaseModel):
    slug: str
    chapters: Optional[str] = None # "1-10" or None (All)

# --- 2. GLOBAL STATE MANAGERS ---

class TaskManager:
    """
    Arka planda çalışan indirmeleri takip eder ve API'ye sunar.
    Flutter uygulaması burayı 'poll' ederek progress bar çizecek.
    """
    def __init__(self):
        self.active_tasks: Dict[str, dict] = {}
    
    def update(self, slug, status, progress=0, message=""):
        self.active_tasks[slug] = {
            "slug": slug,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    
    def get(self, slug):
        return self.active_tasks.get(slug)
    
    def get_all(self):
        return list(self.active_tasks.values())

task_manager = TaskManager()

# --- 3. LIFESPAN & APP SETUP ---

# Global services
yomi_engine: Optional[YomiCore] = None
shared_session: Optional[aiohttp.ClientSession] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama başladığında veritabanını ve oturumları açar,
    kapandığında temizler. Memory leak önler.
    """
    global yomi_engine, shared_session
    
    # Init Engine
    yomi_engine = YomiCore(output_dir="downloads", workers=8)
    # Init Shared Session (Tek bir havuz)
    connector = aiohttp.TCPConnector(limit=100)
    shared_session = aiohttp.ClientSession(connector=connector)
    
    print("✅ Yomi API v0.1.1 Services Started")
    yield
    
    # Cleanup
    if shared_session: await shared_session.close()
    if yomi_engine and yomi_engine.db: yomi_engine.db.close()
    print("🛑 Services Stopped")

app = FastAPI(
    title="Yomi Core API",
    version="0.1.1",
    description="Backend for YomiApp (Flutter)",
    lifespan=lifespan
)

# CORS: Flutter (Mobil/Web) erişimi için açık kapı
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. ENDPOINTS ---

@app.get("/", tags=["System"])
async def health_check():
    return {
        "status": "online",
        "version": "0.1.1",
        "core_engine": "Yomi-Hybrid",
        "active_downloads": len(task_manager.get_all())
    }

@app.get("/search", response_model=List[SearchResult], tags=["Discovery"])
async def search(q: str = Query(..., min_length=2)):
    """Fuzzy search algoritması ile manga arar."""
    # YomiCore içindeki mevcut search mantığını kullanır
    # Ancak burada logic tekrarı yapmamak için YomiCore'a bir 'search_only' metodu eklenebilir
    # Şimdilik mevcut mantığı buraya taşıyoruz:
    
    query = q.lower().strip()
    matches = []
    
    from difflib import SequenceMatcher
    
    for key, data in yomi_engine.sites_config.items():
        name = data.get('name', key).lower()
        score = SequenceMatcher(None, query, key).ratio() * 100
        if query in key or query in name: score += 25
        
        if score > 40:
            matches.append({
                "slug": key,
                "name": data.get('name', key.title()),
                "confidence": int(min(score, 100)),
                "base_domain": data.get('base_domain', 'unknown')
            })
            
    return sorted(matches, key=lambda x: x['confidence'], reverse=True)[:20]

@app.get("/manga/{slug}", response_model=MangaDetails, tags=["Discovery"])
async def get_manga_details(slug: str):
    """Bölümleri ve Anilist detaylarını getirir."""
    # 1. URL Çözümle
    url = await yomi_engine._resolve_target(slug)
    if not url:
        raise HTTPException(status_code=404, detail="Manga not found in local DB")

    # 2. Bölümleri ve Metadatayı Çek (Session paylaşarak)
    from .extractors.common import AsyncGenericMangaExtractor
    extractor = AsyncGenericMangaExtractor(shared_session)
    
    try:
        # Paralel istek atalım (Hız için)
        chapters_task = extractor.get_chapters(url)
        info_task = extractor.get_manga_info(url)
        
        chapters, info = await asyncio.gather(chapters_task, info_task)
        
        # 3. İndirilmişleri İşaretle
        # DB'den inmiş bölümleri çekip karşılaştıralım
        downloaded_titles = yomi_engine.db.get_manga_chapters(slug)
        # Basit bir set ile O(1) kontrol
        # Not: Başlık normalizasyonu gerekebilir, şimdilik direct match
        
        final_chapters = []
        for ch in chapters:
            is_down = yomi_engine.db.is_completed(info['title'], ch['title'])
            final_chapters.append({
                "title": ch['title'],
                "url": ch['url'],
                "is_downloaded": is_down
            })

        # 4. Anilist (Opsiyonel)
        meta = await yomi_engine.anilist.fetch_metadata(info['title'])
        
        return {
            "slug": slug,
            "title": info['title'],
            "metadata": meta,
            "chapters": final_chapters
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download", tags=["Action"])
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    """İndirme işlemini arka plana atar."""
    
    # Zaten iniyorsa engelle
    if task_manager.get(req.slug) and task_manager.get(req.slug)['status'] in ['pending', 'downloading']:
         return {"status": "ignored", "message": "Already in queue"}

    task_manager.update(req.slug, "pending", 0, "Queued")
    
    # Background Task Wrapper
    background_tasks.add_task(run_download_process, req.slug, req.chapters)
    
    return {"status": "queued", "slug": req.slug}

async def run_download_process(slug: str, chapters: str):
    """
    Bu fonksiyon thread-blocking işlemleri yönetir ve durumu günceller.
    Normalde YomiCore senkron çalışıyorsa 'to_thread' kullanılmalı.
    """
    task_manager.update(slug, "downloading", 0, "Initializing...")
    try:
        # Not: YomiCore.download_manga şu an async değilse, asenkron wrapper lazım.
        # Senin core.py'de download_manga bir wrapper methoddu, asıl iş _download_manga_async'deydi.
        # Doğrudan async metodu çağırmak daha iyi.
        
        await yomi_engine._download_manga_async(slug, chapters)
        
        # Başarılı
        task_manager.update(slug, "completed", 100, "Finished")
    except Exception as e:
        task_manager.update(slug, "failed", 0, str(e))
        logging.error(f"Download Task Failed: {e}")

@app.get("/queue", response_model=List[TaskStatus], tags=["Action"])
async def get_queue():
    """Aktif indirmelerin durumunu döndürür."""
    return task_manager.get_all()

@app.get("/library", tags=["Library"])
async def get_library():
    """İndirilmiş arşiv."""
    return yomi_engine.db.get_library()