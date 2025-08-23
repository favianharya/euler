import re
import time, random

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from rich.console import Console

from utils.user_agents import UserAgents

console = Console()

class TokopediaDriver:
    """Handles Selenium WebDriver initialization and navigation."""

    def __init__(self, url):
        if not self.is_valid_url(url):
            console.print("[red]❌ Error: Please enter a valid Tokopedia merchant URL.[/red]")
            self.driver = None
            self.url = None
            return
        
        self.url = url
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument(f"user-agent={UserAgents.from_yaml()}")
        self.driver = webdriver.Chrome(options=options)

    def is_valid_url(self, url: str) -> bool:
        """Check if the URL is valid and belongs to Tokopedia merchant domain."""
        if not url or not isinstance(url, str):
            return False
        pattern = r"^https?://(www\.)?tokopedia\.com/.+"
        return re.match(pattern, url.strip()) is not None

    def open(self):
        if self.driver and self.url:
            self.driver.get(self.url)
        else:
            console.print("[red]❌ Error: Cannot open page because the URL is invalid.[/red]")

    def wait_and_click(self, css_selector, timeout=10):
        """Wait until clickable and then click element."""
        if not self.driver:
            return False
        try:
            btn = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            time.sleep(random.uniform(1.5, 4.0))
            btn.click()
            time.sleep(random.uniform(2.0, 4.0))
            return True
        except:
            return False

    def get_page_source(self):
        if self.driver:
            return self.driver.page_source
        console.print("[red]❌ Error: Cannot get page source. Invalid driver instance.[/red]")
        return None

    def quit(self):
        if self.driver:
            self.driver.quit()