#!/usr/bin/env python3
"""
Upload products to Supabase.
Usage: python3 upload_supabase.py <api_key>
"""

import sys
import requests

if len(sys.argv) < 2:
    print("Usage: python3 upload_supabase.py <your_supabase_anon_key>")
    sys.exit(1)

KEY = sys.argv[1]
SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_REF = "yqawmzggcgpeyaaynrjk"

# First verify the key works
print(f"Testing API key...")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/products?select=id&limit=1",
    headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"}
)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    print(f"API key valid!")
    print(f"Running upload...")
    
    # Now upload
    import json
    with open("scraper_secondcoat_products.json") as f:
        products = json.load(f)
    
    for p in products:
        record = {
            "id": p.get("_id", "unknown"),
            "source": "scraper-secondcoat",
            "brand": "Second Coat",
            "product_url": p.get("product_url"),
            "image_url": p.get("image_url"),
            "title": p.get("title"),
            "category": p.get("category"),
            "gender": "unisex",
            "second_hand": False,
            "image_embedding": p.get("image_embedding"),
            "info_embedding": p.get("info_embedding"),
        }
        
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/products",
            headers={
                "apikey": KEY, 
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=record
        )
        
        if resp.status_code in [200, 201]:
            print(f"✓ {p.get('title', '')[:40]}")
        else:
            print(f"✗ {p.get('title', '')}: {resp.status_code}")
    
    print(f"\nDone!")
else:
    print(f"Error: {resp.text[:200]}")
    print(f"\nThe API key is invalid. Please get a fresh key from:")
    print(f"Supabase Dashboard > Settings > API > Project API keys > anon")