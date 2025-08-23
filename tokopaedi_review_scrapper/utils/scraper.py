from utils.driver import TokopediaDriver
from utils.parser import TokopediaParser

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
import os

class TokopediaScraper:
    """Main class to orchestrate scraping flow."""

    def __init__(self, url, start_page=1, pages=3):
        self.url = url
        self.start_page = start_page
        self.pages = pages
        self.data = []

    def scrape(self):
        driver = TokopediaDriver(self.url)
        driver.open()

        # 📌 Skip to start_page
        current_page = 1
        while current_page < self.start_page:
            if not driver.wait_and_click("button[aria-label^='Laman berikutnya']"):
                print("Cannot skip further, reached last page.")
                break
            current_page += 1

        # 📌 Scrape for `pages`
        for i in range(self.pages):
            WebDriverWait(driver.driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span[data-testid='lblItemUlasan']"))
            )

            html = driver.get_page_source()
            page_data = TokopediaParser.parse(html)
            self.data.extend(page_data)

            if not driver.wait_and_click("button[aria-label^='Laman berikutnya']"):
                print("No more pages.")
                break
            current_page += 1

        driver.quit()

    def save_to_csv(self):
        # Create folder if not exists
        folder_name = "tokopaedi_scrap_results"
        os.makedirs(folder_name, exist_ok=True)

        # Build filename with path inside folder
        end_page = self.start_page + self.pages - 1
        filename = os.path.join(folder_name, f"tokopedia_{self.start_page}-{end_page}.csv")

        # Save DataFrame to CSV
        df = pd.DataFrame(self.data, columns=["Produk", "Ulasan", "Bintang"])
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"Selesai! Data disimpan di {filename}")
