import requests
import xml.etree.ElementTree as ET
import json
import time
from rich.console import Console
from rich.progress import track

console = Console()

def build_master_index():
    # Mangakakalot'un ana sitemap adresi
    base_sitemap = "https://www.mangakakalot.gg/sitemap.xml"
    console.print(f"[bold cyan]🗺️  Harita İnşası Başlıyor: {base_sitemap}[/]")
    
    # Bot gibi görünmemek için Header şart
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. Ana Haritayı Çek
        response = requests.get(base_sitemap, headers=headers)
        if response.status_code != 200:
            console.print("[red]❌ Ana haritaya erişilemedi! (Banlanmış olabiliriz)[/]")
            return

        # XML Parsing
        root = ET.fromstring(response.content)
        # XML namespace belası için (sitemaps.org şeması)
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        # Alt haritaları bul (sitemap-comic-1.xml, comic-2.xml ...)
        sub_maps = [loc.text for loc in root.findall('ns:sitemap/ns:loc', ns)]
        
        console.print(f"[green]✅ {len(sub_maps)} adet alt harita bulundu.[/]")
        
        full_database = {}
        total_mangas = 0
        
        # 2. Alt Haritaları Tek Tek Gez (sitemap-comic-1.xml ...)
        for sitemap_url in sub_maps:
            if "comic" not in sitemap_url: 
                continue # comic olmayanları (others, profiles vs) atla
                
            console.print(f"   ⬇️  İndiriliyor: {sitemap_url}...")
            
            try:
                sub_res = requests.get(sitemap_url, headers=headers)
                sub_root = ET.fromstring(sub_res.content)
                
                # İçindeki URL'leri al
                urls = sub_root.findall('ns:url/ns:loc', ns)
                
                local_count = 0
                for url_obj in urls:
                    url = url_obj.text
                    # URL: https://www.mangakakalot.gg/manga/solo-leveling
                    if "/manga/" in url:
                        # Slug'ı (anahtarı) çıkar: 'solo-leveling'
                        slug = url.split("/manga/")[-1].strip().lower()
                        
                        # Veritabanına ekle
                        full_database[slug] = url
                        local_count += 1
                
                total_mangas += local_count
                console.print(f"      -> {local_count} manga eklendi. (Toplam: {total_mangas})")
                
                # Sunucuyu kızdırmamak için 1 saniye bekle
                time.sleep(1) 
                
            except Exception as e:
                console.print(f"[red]      ⚠️  Bu harita okunamadı: {e}[/]")

        # 3. Sonucu Kaydet
        console.print(f"\n[bold green]🎉 İŞLEM TAMAM! Toplam {len(full_database)} manga indekslendi.[/]")
        
        with open("manga_db.json", "w", encoding="utf-8") as f:
            json.dump(full_database, f, indent=2)
            
        console.print("[yellow]💾 Veritabanı 'manga_db.json' olarak kaydedildi. Artık arama yapmak yok![/]")

    except Exception as e:
        console.print(f"[bold red]🔥 Kritik Hata: {e}[/]")

if __name__ == "__main__":
    build_master_index()