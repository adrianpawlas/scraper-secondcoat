import json
import hashlib
import re
from datetime import datetime
from typing import List, Optional, Any
import requests
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_ANON_KEY, CURRENCY_CONVERSION


class SupabaseUploader:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    def generate_id(self, title: str, source: str = "scraper-secondcoat") -> str:
        hash_input = f"{source}:{title}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def format_price(self, price_str: str, base_currency: str = "CZK") -> str:
        if not price_str:
            return ""
        
        prices = []
        
        czk_match = re.search(r"([\d\s,]+)\s*K[čČ]", price_str)
        if czk_match:
            czk_val = float(czk_match.group(1).replace(" ", "").replace(",", "."))
            prices.append(f"{int(czk_val)}{base_currency}")
            
            for curr, rate in CURRENCY_CONVERSION.get(base_currency, {}).items():
                converted = int(czk_val * rate)
                if converted > 0:
                    prices.append(f"{converted}{curr}")
        
        if not prices:
            match = re.search(r"([\d]+)", price_str)
            if match:
                return f"{match.group(1)}CZK"
        
        return ", ".join(prices)
    
    def parse_size(self, sizes_str: str) -> str:
        if not sizes_str:
            return ""
        return sizes_str.replace(" ", "").upper()
    
    def upload_products(self, products: List[dict]) -> dict:
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for product in products:
            try:
                self.upload_product(product)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
                print(f"Error uploading {product.get('title', 'unknown')}: {e}")
        
        return results
    
    def upload_product(self, product: dict) -> bool:
        product_id = self.generate_id(product.get("title", ""))
        
        additional_images = product.get("additional_images", [])
        additional_str = ", ".join(additional_images) if additional_images else None
        
        sizes = product.get("sizes", "")
        
        metadata = {
            "title": product.get("title"),
            "description": product.get("description"),
            "details": product.get("details"),
            "sizes": sizes,
            "colors": product.get("color", ""),
            "gender": product.get("gender", ""),
            "scraped_at": datetime.utcnow().isoformat()
        }
        
        record = {
            "id": product_id,
            "source": "scraper-secondcoat",
            "brand": "Second Coat",
            "product_url": product.get("product_url"),
            "affiliate_url": None,
            "image_url": product.get("image_url"),
            "title": product.get("title"),
            "description": product.get("description"),
            "category": product.get("category"),
            "gender": product.get("gender") if product.get("gender") else "unisex",
            "price": self.format_price(product.get("price", "")),
            "sale": self.format_price(product.get("price", "")) if product.get("price") else None,
            "second_hand": False,
            "size": sizes if sizes else None,
            "metadata": json.dumps(metadata),
            "created_at": datetime.utcnow().isoformat(),
            "country": "Czechia",
            "additional_images": additional_str,
            "image_embedding": product.get("image_embedding"),
            "info_embedding": product.get("info_embedding")
        }
        
        response = self.client.table("products").upsert(record, on_conflict="id").execute()
        
        print(f"Uploaded: {record['title'][:40]}")
        
        return True


def test_connection():
    print("Testing Supabase connection...")
    try:
        client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        
        response = client.table("products").select("id").limit(1).execute()
        print(f"Connection successful! Found {len(response.data)} records")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()