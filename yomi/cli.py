import click
import logging
import json
import os
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from .core import YomiCore

# Setup Fancy Console
console = Console()
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("YomiCLI")

@click.group()
def cli():
    """YOMI - Rabbit Speed Manga Downloader 🐇"""
    pass

@cli.command()
@click.option('-u', '--url', required=True, help='Link to the manga')
@click.option('-o', '--out', default='downloads', help='Output folder')
@click.option('-w', '--workers', default=8, help='Download threads')
@click.option('-f', '--format', default='folder', type=click.Choice(['folder', 'pdf', 'cbz']), help='Output format')
@click.option('-r', '--range', default=None, help='Chapter Range (e.g., "1-100")')
@click.option('-p', '--proxy', default=None, help='Proxy URL (http://user:pass@ip:port)')
@click.option('--debug/--no-debug', default=False, help='Enable developer logs')
def download(url, out, workers, format, range, proxy, debug):
    """Download manga from any supported URL."""
    
    if debug:
        logger.setLevel("DEBUG")
        console.print("[bold red]DEBUG MODE ACTIVE[/bold red]")

    console.print(f"[bold green]STARTING Yomi...[/bold green]")
    
    # Show user what settings are active
    if range:
        console.print(f"🎯 Range: [yellow]{range}[/yellow]")
    if proxy:
        console.print(f"🛡️ Proxy: [yellow]Enabled[/yellow]")
    if format != 'folder':
        console.print(f"📦 Format: [cyan]{format.upper()}[/cyan]")
    
    try:
        # Initialize the Engine
        engine = YomiCore(
            output_dir=out, 
            workers=workers, 
            debug=debug, 
            format=format, 
            proxy=proxy
        )
        
        # Start Downloading
        engine.download_manga(url, chapter_range=range)
        
        console.print("[bold green]✅ ALL DONE! Enjoy your manga.[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")

@cli.command()
def available():
    """List verified sites from sites.json"""
    table = Table(title="Community Verified Sites")
    table.add_column("Site Name", style="cyan")
    table.add_column("URL", style="green")

    # Load sites from the JSON file
    json_path = "sites.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                sites = json.load(f)
                for site in sites:
                    table.add_row(site['name'], site['url'])
        except json.JSONDecodeError:
             table.add_row("Error", "sites.json is corrupted")
    else:
        # Default fallback if no file exists
        table.add_row("Rent-a-Girlfriend (W5)", "https://w5.rentagirlfriendmanga.org/")
        table.add_row("Asura Scans", "https://asuracomic.net/")
        table.add_row("Flame Scans", "https://flamecomics.com/")
        console.print("[dim]Tip: Create a 'sites.json' file to add your own sites![/dim]")
    
    console.print(table)

if __name__ == '__main__':
    cli()