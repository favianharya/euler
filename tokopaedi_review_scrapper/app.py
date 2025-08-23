from utils.scraper import TokopediaScraper
from utils.file import read_text, clear

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import sys


console = Console()

def description():
    
    title = Text.from_markup(read_text("resource/logo.txt"), style="bright_blue")
    console.print(title)

    # Description
    console.print("Easily collect and analyze customer reviews from Tokopedia with a fast and reliable scraping tool.\n")

    # Features
    console.print("[green]📥[/green] Scrape reviews automatically from Tokopedia product pages")
    console.print("[green]📊[/green] Gather insights from thousands of customer feedback")
    console.print("[cyan]⚡[/cyan] Export data quickly for reporting and research\n")

def main():
    clear()
    description()

    try:
        while True:
            # Get URL
            url = console.input("🦉 [bold green]Enter Tokopedia Merchant URL: [/bold green] ")
            if not url.strip():
                console.print("[red]❌ URL cannot be empty![/red]")
                continue

            # Get start page (validated int)
            while True:
                try:
                    start = int(console.input("🦉 [bold green]Starting Review Page: [/bold green]"))
                    if start > 0:
                        break
                    else:
                        console.print("[red]❌ Must be greater than 0![/red]")
                except ValueError:
                    console.print("[red]❌ Please enter a valid number![/red]")

            # Get number of pages (validated int)
            while True:
                try:
                    pages = int(console.input("🦉 [bold green]How many pages do you want to scrape? [/bold green]"))
                    if pages > 0:
                        break
                    else:
                        console.print("[red]❌ Must be greater than 0![/red]")
                except ValueError:
                    console.print("[red]❌ Please enter a valid number![/red]")

            # Run scraper
            scraper = TokopediaScraper(url, start_page=start, pages=pages)
            scraper.scrape()
            scraper.save_to_csv()

            # Ask to continue
            again = console.input("\n🔁 [yellow]Do you want to scrape another URL? (y/n): [/yellow]").strip().lower()
            if again != "y":
                console.print("[cyan]👋 Exiting...[/cyan]")
                break

    except KeyboardInterrupt:
        console.print("\n[red]⚡ Interrupted by user. Exiting safely...[/red]")
        sys.exit(0)


if __name__ == "__main__":
    main()