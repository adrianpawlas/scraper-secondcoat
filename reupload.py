#!/usr/bin/env python3
"""Re-upload products with proper embedding arrays."""

import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python3 reupload.py <api_key>")
    sys.exit(1)

KEY = sys.argv[1]
SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"

# First delete old products
print("Deleting old products...")
resp = requests.delete(
    f"{SUPABASE_URL}/rest/v1/products?source=eq.scraper-secondcoat",
    headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"}
)
print(f"Deleted: {resp.status_code}")

# Load fresh data
with open("scraper_secondcoat_products.json") as f:
    products = json.load(f)

print(f"Re-uploading {len(products)} products...")

for p in products:
    # Ensure embeddings are lists, not converted to strings
    image_emb = p.get("image_embedding")
    info_emb = p.get("info_embedding")
    
    # Make sure they're actual Python lists
    if isinstance(image_emb, str):
        image_emb = json.loads(image_emb)
    if isinstance(info_emb, str):
        info_emb = json.loads(info_emb)
    
    record = {
        "id": p.get("_id"),
        "source": "scraper-secondcoat",
        "brand": "Second Coat",
        "product_url": p.get("product_url"),
        "image_url": p.get("image_url"),
        "title": p.get("title"),
        "description": p.get("description") or None,
        "category": p.get("category"),
        "gender": "unisex",
        "second_hand": False,
        "size": p.get("sizes") or None,
        "price": p.get("price", ""),
        "image_embedding": image_emb,
        "info_embedding": info_emb,
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
        print(f"✗ {p.get('title', '')}: {resp.status_code} - {resp.text[:100]}")

print("Done!")