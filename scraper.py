import re
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional

BASE_URL = "https://2ndc.ca"

CATEGORIES = {
    "tops": "https://2ndc.ca/collections/tops",
    "bottoms": "https://2ndc.ca/collections/bottoms",
    "accessories": "https://2ndc.ca/collections/accessories",
}

# Exchange rate: 1 EUR ≈ 25 CZK
CZK_TO_EUR = 25.0


class SecondCoatScraper:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
    
    async def get_products_from_category(self, category: str, collection_url: str) -> list:
        html = await self.fetch(collection_url)
        soup = BeautifulSoup(html, "html.parser")
        
        products = []
        product_links = soup.select('a[href*="/products/"]')
        seen = set()
        
        for link in product_links:
            href = link.get("href", "")
            if "/products/" in href and href not in seen:
                seen.add(href)
                full_url = urljoin(BASE_URL, href)
                details = await self.get_product_details(full_url, category)
                products.append(details)
                print(f"  Scraped: {details['title'][:40]}")
        
        print(f"[{category}] Found {len(products)} products")
        return products
    
    async def get_product_details(self, product_url: str, category: str) -> dict:
        html = await self.fetch(product_url)
        soup = BeautifulSoup(html, "html.parser")
        
        title = self._get_title(soup)
        czk_price = self._get_price(soup)
        images = self._get_images(soup)
        description = self._get_description(soup)
        details = self._get_details(soup)
        sizes = self._get_sizes(soup)
        material = self._get_material(soup)
        color = self._extract_color(title)
        
        # Convert price to EUR
        eur_price = self._convert_to_eur(czk_price)
        
        return {
            "product_url": product_url,
            "title": title,
            "price": eur_price,
            "price_czk": czk_price,
            "image_url": images[0] if images else None,
            "additional_images": images[1:] if len(images) > 1 else [],
            "description": description,
            "details": details,
            "sizes": sizes,
            "color": color,
            "material": material,
            "category": category,
            "metadata": json.dumps({
                "title": title,
                "description": description[:500] if description else "",
                "details": details,
                "sizes": sizes,
                "color": color,
                "material": material,
                "price_czk": czk_price,
                "price_eur": eur_price,
                "category": category,
                "gender": "unisex"
            }, ensure_ascii=False)
        }
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        # Find the product title in h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        return "Unknown"
    
    def _get_price(self, soup: BeautifulSoup) -> str:
        """Get price in CZK format (handles both , and . decimal formats)"""
        # Look for price in format like "1.057,00 Kč" or "515,00 Kč"
        text = soup.get_text()
        
        # Match with period for thousands, comma for decimals
        match = re.search(r'([\d]{1,3}(?:[.][\d]{3})*,[\d]{2})\s*K[čČ]', text)
        if match:
            return match.group(1).strip() + " Kč"
        
        # Try simpler format: just number with comma
        match = re.search(r'([\d]+,[\d]{2})\s*K[čČ]', text)
        if match:
            return match.group(1).strip() + " Kč"
        
        # Last resort: any number near Kč
        match = re.search(r'([\d\s,\xA0]+)\s*K[čČ]', text)
        if match:
            price = match.group(1).strip().replace('\xa0', '').replace(' ', '')
            return price + " Kč"
        
        return ""
    
    def _convert_to_eur(self, czk_price: str) -> str:
        """Convert CZK price to EUR"""
        if not czk_price:
            return ""
        
        # Extract number
        match = re.search(r'([\d\s,\xA0]+)', czk_price)
        if not match:
            return ""
        
        czk_str = match.group(1).replace(' ', '').replace('\xa0', '').replace(',', '.')
        try:
            czk_val = float(czk_str)
            eur_val = round(czk_val / CZK_TO_EUR, 2)
            return f"{eur_val}EUR"
        except:
            return ""
    
    def _get_images(self, soup: BeautifulSoup) -> list:
        images = []
        
        # Find all images in gallery/class that contain shopify
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'shopify' in src and src not in images:
                # Make sure it's a product image
                if any(x in src.lower() for x in ['files', 'products', 'cdn']):
                    full_url = urljoin("https://2ndc.ca", src)
                    # Normalize URL (remove params)
                    if '?' in full_url:
                        full_url = full_url.split('?')[0]
                    # Normalize http to https
                    full_url = full_url.replace('http://', 'https://')
                    if full_url.startswith('https') and full_url not in images:
                        images.append(full_url)
        
        # Try meta og:image
        if not images:
            meta = soup.find('meta', property='og:image')
            if meta:
                images.append(meta.get('content', ''))
        
        return list(dict.fromkeys(images))[:10]
    
    def _get_description(self, soup: BeautifulSoup) -> str:
        # Find description in product Details sections
        for elem in soup.find_all(['div', 'section'], class_=re.compile(r'description|detail', re.I)):
            text = elem.get_text(strip=True)
            if text and len(text) > 20 and len(text) < 2000:
                return text[:2000]
        
        return ""
    
    def _get_details(self, soup: BeautifulSoup) -> str:
        """Get product details like material, fit"""
        details = []
        
        # Look for Detail sections
        for elem in soup.find_all(['div', 'ul'], class_=re.compile(r'detail', re.I)):
            text = elem.get_text(strip=True)
            if text and len(text) > 5 and len(text) < 200:
                details.append(text)
        
        return " | ".join(details[:3])
    
    def _get_sizes(self, soup: BeautifulSoup) -> str:
        """Get available sizes from option elements"""
        sizes = []
        
        # Find size options in selects
        for select in soup.find_all('select'):
            options = select.find_all('option')
            for opt in options:
                text = opt.get_text(strip=True).upper()
                # Look for size codes
                if re.match(r'^(XS|S|M|L|XL|XXL|3XL)$', text):
                    sizes.append(text)
        
        return ",".join(sorted(set(sizes))) if sizes else ""
    
    def _get_material(self, soup: BeautifulSoup) -> str:
        text = self._get_description(soup).lower()
        
        materials = ['cotton', 'wool', 'silk', 'linen', 'polyester', 'cashmere', 'acrylic', 'nylon']
        for mat in materials:
            if mat in text:
                return mat.capitalize()
        
        return ""
    
    def _extract_color(self, title: str) -> str:
        # Extract color from title (e.g., "Barback Shirt • Espresso" -> Espresso)
        # Also handle " • " separated names
        if '•' in title:
            color = title.split('•')[-1].strip()
            # Clean up any extra characters
            color = re.sub(r'[•\[\]]+', '', color).strip()
            return color
        # Try other separators
        for sep in [' - ', ' · ', ' / ']:
            if sep in title:
                return title.split(sep)[-1].strip()
        return ""


async def main():
    scraper = SecondCoatScraper()
    
    all_products = []
    
    async with scraper:
        for category, url in CATEGORIES.items():
            print(f"\n=== Scraping {category} ===")
            products = await scraper.get_products_from_category(category, url)
            all_products.extend(products)
    
    print(f"\n=== Total: {len(all_products)} products ===")
    
    for p in all_products:
        print(f"\n{p.get('title')}")
        print(f"  Price: {p.get('price')} (was {p.get('price_czk')})")
        print(f"  Sizes: {p.get('sizes')}")
        print(f"  Color: {p.get('color')}")
        print(f"  Material: {p.get('material')}")
        m = json.loads(p.get('metadata', '{}'))
        print(f"  Metadata: has material={bool(m.get('material'))}")
    
    return all_products


if __name__ == "__main__":
    asyncio.run(main())