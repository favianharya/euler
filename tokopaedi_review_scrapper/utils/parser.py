from bs4 import BeautifulSoup

class TokopediaParser:
    """Parses HTML from Tokopedia to extract product reviews."""

    @staticmethod
    def parse(html):
        soup = BeautifulSoup(html, "html.parser")
        products = soup.find_all("p", class_="css-akhxpb-unf-heading")
        reviews = soup.find_all("span", attrs={"data-testid": "lblItemUlasan"})
        stars = soup.find_all("div", attrs={"data-testid": "icnStarRating"})

        data = []
        for p, r, s in zip(products, reviews, stars):
            product_name = p.get_text(strip=True)
            review_text = r.get_text(strip=True)
            star_label = s.get("aria-label")
            star_value = int(star_label.split()[-1]) if star_label else None
            data.append((product_name, review_text, star_value))
        return data