import re
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Optional

BASE_URL = "https://2ndc.ca"

CATEGORIES = {
    "tops": "https://2ndc.ca/collections/tops",
    "bottoms": "https://2ndc.ca/collections/bottoms",
    "accessories": "https://2ndc.ca/collections/accessories",
}


class SecondCoatScraper:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch(self, url: str) -> str:
        async with self.session.get(url) as response:
            return await response.text()
    
    async def get_products_from_collection(self, category: str, collection_url: str) -> list:
        html = await self.fetch(collection_url)
        soup = BeautifulSoup(html, "html.parser")
        products = []
        
        product_links = soup.select('a[href*="/products/"]')
        seen_urls = set()
        
        for link in product_links:
            href = link.get("href", "")
            if "/products/" in href and href not in seen_urls:
                full_url = urljoin(BASE_URL, href)
                seen_urls.add(full_url)
                products.append({
                    "url": full_url,
                    "category": category,
                    "title": link.get_text(strip=True) or self._extract_title_from_url(href)
                })
        
        print(f"[{category}] Found {len(products)} products")
        return products
    
    def _extract_title_from_url(self, url: str) -> str:
        match = re.search(r"/products/(-?[^-]+)", url)
        if match:
            title = match.group(1).replace("-", " ").title()
            return title
        return "Unknown Product"
    
    async def get_product_details(self, product_url: str, category: str) -> dict:
        html = await self.fetch(product_url)
        soup = BeautifulSoup(html, "html.parser")
        
        title = self._get_title(soup)
        price = self._get_price(soup)
        images = self._get_images(soup)
        description = self._get_description(soup)
        details = self._get_details(soup)
        sizes = self._get_sizes(soup)
        
        return {
            "product_url": product_url,
            "title": title,
            "price": price,
            "image_url": images[0] if images else None,
            "additional_images": images[1:] if len(images) > 1 else [],
            "description": description,
            "details": details,
            "sizes": sizes,
            "category": category
        }
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        title_elem = soup.select_one('h1[class*="product"], h1')
        if title_elem:
            return title_elem.get_text(strip=True)
        return "Unknown"
    
    def _get_price(self, soup: BeautifulSoup) -> str:
        price_elem = soup.select_one('[class*="price"], [class*="Sale"]')
        if price_elem:
            text = price_elem.get_text(strip=True)
            match = re.search(r"[\d\s,]+[KČKč]", text)
            if match:
                return match.group().strip()
        return ""
    
    def _get_images(self, soup: BeautifulSoup) -> list:
        images = []
        img_elements = soup.select('[class*="gallery"] img, [class*="product"] img, .product-page img')
        
        for img in img_elements:
            src = img.get("src") or img.get("data-src") or img.get("data-srcset", "").split()[0]
            if src and "shopify" in src and src not in images:
                full_url = urljoin("https://2ndc.ca", src)
                if full_url.startswith("https"):
                    images.append(full_url)
        
        if not images:
            meta_img = soup.find("meta", property="og:image")
            if meta_img:
                images.append(meta_img.get("content", ""))
        
        return images[:10]
    
    def _get_description(self, soup: BeautifulSoup) -> str:
        desc_elem = soup.select_one('[class*="description"], [class*="Detail"]')
        if desc_elem:
            return desc_elem.get_text(strip=True)
        return ""
    
    def _get_details(self, soup: BeautifulSoup) -> str:
        details_elems = soup.select('[class*="Detail"], [class*="details"]')
        details = []
        for elem in details_elems:
            text = elem.get_text(strip=True)
            if text and len(text) < 500:
                details.append(text)
        return " | ".join(details[:5])
    
    def _get_sizes(self, soup: BeautifulSoup) -> str:
        size_elems = soup.select('[class*="size"], .variant-dropdown, option')
        sizes = []
        for elem in size_elems:
            text = elem.get_text(strip=True)
            if re.match(r"^[a-zA-Z]+$", text) and len(text) <= 4:
                sizes.append(text.upper())
        return ",".join(sizes) if sizes else ""
    
    async def scrape_all(self) -> list:
        all_products = []
        
        async with self:
            for category, url in CATEGORIES.items():
                products = await self.get_products_from_category(category, url)
                all_products.extend(products)
        
        return all_products
    
    async def get_products_from_category(self, category: str, collection_url: str) -> list:
        html = await self.fetch(collection_url)
        soup = BeautifulSoup(html, "html.parser")
        
        products = []
        product_cards = soup.select('a[href*="/products/"]')
        seen = set()
        
        for card in product_cards:
            href = card.get("href", "")
            if "/products/" in href and href not in seen:
                seen.add(href)
                full_url = urljoin(BASE_URL, href)
                details = await self.get_product_details(full_url, category)
                products.append(details)
                print(f"  Scraped: {details['title'][:40]}")
        
        return products


async def main():
    scraper = SecondCoatScraper()
    
    all_products = []
    
    async with scraper:
        for category, url in CATEGORIES.items():
            print(f"\n=== Scraping {category} ===")
            products = await scraper.get_products_from_category(category, url)
            all_products.extend(products)
            print(f"Got {len(products)} products from {category}")
    
    print(f"\n=== Total: {len(all_products)} products ===")
    return all_products


if __name__ == "__main__":
    asyncio.run(main())