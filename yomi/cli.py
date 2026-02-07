import os
import json
import logging
import rich_click as click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich import box
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text

# --- Core Module ---
try:
    from .core import YomiCore
except ImportError:
    # Geliştirme ortamında çalışırken path hatası almamak için
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from yomi.core import YomiCore

# --- 1. Console & Logging Setup ---
console = Console()
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)]
)
logger = logging.getLogger("YomiCLI")

# --- 2. Rich Click Configuration ---
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = "Did you mean this?"
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True

# --- VIP LISTESI (Vitrin) ---
# Kullanıcı hiçbir şey aramzsa varsayılan olarak bunlar gözükecek.
FEATURED_MANGAS = {
    "one-piece", "bleach", "naruto", "jujutsu-kaisen", "chainsaw-man",
    "attack-on-titan", "demon-slayer-kimetsu-no-yaiba", "berserk",
    "one-punch-man", "vinland-saga", "vagabond", "tokyo-ghoul",
    "solo-leveling", "spy-x-family", "hunter-x-hunter", "black-clover",
    "my-hero-academia", "blue-lock", "dandadan", "sakamoto-days",
    "kingdom", "20th-century-boys", "oyasumi-punpun", "monster",
    "death-note", "fullmetal-alchemist", "dragon-ball", "gto",
    "kaguya-sama-love-is-war", "made-in-abyss"
}

# --- 3. CLI Group ---
@click.group()
def cli():
    """
    [bold cyan]🐇 YOMI CLI v0.3[/] - [italic white]The Rabbit Hole of Manga[/]

    [green]Yomi[/] is an intelligent archiver that bypasses protections,
    auto-discovers mirrors, and builds a metadata-rich library.
    """
    pass

# --- 4. Download Command ---
@cli.command()
@click.option('-u', '--url', required=True, help="[bold yellow]Target URL[/] or Manga Name (slug). [dim]Ex: 'bleach'[/]")
@click.option('-o', '--out', default='downloads', show_default=True, help="Output Directory.")
@click.option('-w', '--workers', default=8, show_default=True, help="Concurrent Download Limit.")
@click.option('-f', '--format', default='folder', show_default=True, type=click.Choice(['folder', 'pdf', 'cbz'], case_sensitive=False), help="Output Format.")
@click.option('-r', '--range', 'chapter_range', default=None, help="Chapter Range. [dim]Ex: '1-10'[/]")
@click.option('-p', '--proxy', default=None, help="Proxy URL.")
@click.option('--debug/--no-debug', default=False, help="Enable verbose logs.")
def download(url, out, workers, format, chapter_range, proxy, debug):
    """
    📥 [bold]Download Manga[/]
    
    Downloads chapters from a URL or a verified name from the database.
    """
    if debug:
        logger.setLevel("DEBUG")
        console.print("[bold red]🐛 DEBUG MODE ACTIVE[/bold red]")

    console.print(f"[bold green]🐇 STARTING Yomi...[/bold green]")
    
    try:
        # Eğer URL değil de isim girildiyse (örn: "bleach"), veritabanından bul
        if not url.startswith("http"):
            json_path = os.path.join(os.path.dirname(__file__), "sites.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    sites = json.load(f)
                    if url in sites:
                        # URL Pattern'ı oluştur
                        base_domain = sites[url].get('base_domain')
                        # Basit bir mantıkla ana sayfayı oluşturuyoruz, 
                        # Core modülü bunu zaten yönetiyor ama burası CLI tarafı.
                        # En temizi direkt Core'a slug'ı vermek olabilir ama 
                        # şimdilik Core url beklediği için pattern'dan türetelim.
                        # NOT: YomiCore slug desteği varsa direkt slug ver.
                        pass 
            
        engine = YomiCore(output_dir=out, workers=workers, debug=debug, format=format, proxy=proxy)
        engine.download_manga(url, chapter_range=chapter_range)
        console.print("[bold green]✅ ALL DONE! Enjoy your manga.[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        if debug:
            logger.exception("Traceback:")

# --- 5. Available / Search Command ---
@cli.command()
@click.option('-s', '--search', help="Search for a manga. [dim]Ex: 'hero', 'leveling'[/]")
@click.option('--all', 'show_all', is_flag=True, help="Show entire database (Heavy!)")
def available(search, show_all):
    """
    🌍 [bold]Library & Search[/]
    
    Browses the 'sites.json' database.
    Default: Shows VIP/Trending manga.
    Use --search to find specific titles.
    Use --all to see everything (Warning: Big list).
    """
    json_path = os.path.join(os.path.dirname(__file__), "sites.json")
    
    if not os.path.exists(json_path):
        console.print("[bold red]❌ Error:[/bold red] sites.json not found! Run aggregator first.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            sites = json.load(f)
    except json.JSONDecodeError:
        console.print("[bold red]❌ Error:[/bold red] sites.json is corrupted!")
        return

    # --- ARAMA MODU (Tablo Görünümü) ---
    if search:
        search = search.lower().strip()
        results = []
        
        # Akıllı Puanlama Sistemi
        for key, data in sites.items():
            score = 0
            name = data.get('name', key).lower()
            key_clean = key.replace("-", " ")
            
            if key == search: score = 100          # Tam Eşleşme (Slug)
            elif name == search: score = 100       # Tam Eşleşme (İsim)
            elif key.startswith(search): score = 80 # Başlangıç
            elif name.startswith(search): score = 80
            elif f" {search}" in key_clean: score = 60 # Kelime Başı
            elif search in key: score = 20         # İçinde geçiyor
            elif search in name: score = 20
            
            if score > 0:
                results.append((score, key, data))
        
        # Puanına göre sırala (Yüksekten düşüğe)
        results.sort(key=lambda x: x[0], reverse=True)
        
        if not results:
            console.print(f"[red]No results found for '{search}'.[/]")
            return

        # Sonuçları Tabloya Bas
        table = Table(title=f"Search Results: '{search}'", box=box.ROUNDED, border_style="blue")
        table.add_column("Key (Use this to download)", style="cyan bold")
        table.add_column("Name", style="white")
        table.add_column("Domain", style="dim green")
        
        for score, key, data in results:
            domain = data.get('base_domain', 'Unknown')
            name = data.get('name', key.title())
            table.add_row(key, name, domain)
            
        console.print(table)
        return

    # --- VİTRİN MODU (Grid/Izgara Görünümü) ---
    
    # Hangi listeyi göstereceğiz?
    if show_all:
        display_keys = sorted(list(sites.keys()))
        title = f"📚 Full Archive ({len(sites)} Series)"
    else:
        # Sadece VIP listede olanlar VE veritabanında mevcut olanlar
        display_keys = sorted([k for k in sites.keys() if k in FEATURED_MANGAS])
        # Eğer VIP'den hiçbiri yoksa rastgele ilk 24'ü al (Fallback)
        if not display_keys:
            display_keys = sorted(list(sites.keys()))[:24]
        title = f"🔥 Trending & Popular ({len(display_keys)}/{len(sites)})"

    # Kartları Oluştur
    renderables = []
    for key in display_keys:
        data = sites.get(key, {})
        name = data.get('name', key.replace("-", " ").title())
        domain = data.get('base_domain', '')
        
        # Panel İçeriği
        content = f"[bold cyan]{name}[/]\n[dim]{domain}[/]"
        renderables.append(
            Panel(content, expand=True, border_style="dim blue")
        )

    console.rule(f"[bold yellow]{title}[/]")
    console.print(Columns(renderables, equal=True, expand=True))
    
    # Alt Bilgi
    if not show_all and len(sites) > len(display_keys):
        remaining = len(sites) - len(display_keys)
        console.print(f"\n[dim italic]...and [bold white]{remaining}[/] more series hidden.[/]", justify="center")
        console.print("[yellow]Tip:[/yellow] Use [bold green]yomi available --all[/] to see everything.", justify="center")
        console.print("[yellow]Tip:[/yellow] Use [bold green]yomi available -s 'name'[/] to search.", justify="center")
    console.print("")

if __name__ == '__main__':
    cli()