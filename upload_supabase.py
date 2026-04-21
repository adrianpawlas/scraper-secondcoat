import requests
import json
import hashlib
from datetime import datetime
from typing import List
import uuid

SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBiYXNlIiwicmVmIjoieXFhd216Z2djZ3BleWFhW25ya2siLCJyb2xlIjoic2VydmljZV9yb2xlIiwiaWF0IjoxNzU1MDEwOTI2IiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4"


def generate_id(title: str) -> str:
    hash_input = f"scraper-secondcoat:{title}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


def parse_price(price_str: str) -> dict:
    import re
    prices = {}
    if not price_str:
        return {"CZK": ""}
    
    czk_match = re.search(r"([\d\s,]+)\s*K[čČ]", price_str)
    if czk_match:
        czk_val = czk_match.group(1).replace(" ", "").replace(",", ".")
        prices["CZK"] = int(float(czk_val))
    
    return prices


def upload_to_supabase(products: List[dict]) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    for product in products:
        try:
            product_id = generate_id(product.get("title", ""))
            
            prices = parse_price(product.get("price", ""))
            czk = prices.get("CZK", 0)
            
            record = {
                "id": product_id,
                "source": "scraper-secondcoat",
                "brand": "Second Coat",
                "product_url": product.get("product_url"),
                "affiliate_url": None,
                "image_url": product.get("image_url"),
                "title": product.get("title"),
                "description": product.get("description") or None,
                "category": product.get("category"),
                "gender": "unisex",
                "price": f"{czk}CZK" if czk else product.get("price", ""),
                "sale": f"{czk}CZK" if czk else None,
                "second_hand": False,
                "size": product.get("sizes") or None,
                "created_at": datetime.utcnow().isoformat(),
                "country": "Czechia",
                "additional_images": ",".join(product.get("additional_images", [])) if product.get("additional_images") else None,
                "image_embedding": product.get("image_embedding"),
                "info_embedding": product.get("info_embedding"),
                "metadata": json.dumps({
                    "details": product.get("details"),
                    "scraped_at": datetime.utcnow().isoformat()
                })
            }
            
            url = f"{SUPABASE_URL}/rest/v1/products"
            response = requests.post(url, headers=headers, json=record)
            
            if response.status_code in [200, 201]:
                results["success"] += 1
                print(f"Uploaded: {record['title'][:40]}")
            else:
                results["failed"] += 1
                results["errors"].append(f"{record['title']}: {response.text}")
                print(f"Error: {record['title'][:40]} - {response.status_code}")
                
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))
            print(f"Exception: {product.get('title', 'unknown')}: {e}")
    
    return results


def main():
    with open("scraper_secondcoat_products.json", "r") as f:
        products = json.load(f)
    
    print(f"Uploading {len(products)} products to Supabase...")
    results = upload_to_supabase(products)
    
    print(f"\n=== DONE ===")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    
    if results['errors']:
        print("\nErrors:")
        for e in results['errors'][:5]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()