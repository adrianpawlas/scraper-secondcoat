#!/usr/bin/env python3

import asyncio
import json
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import SecondCoatScraper
from embeddings import get_image_embedding, get_text_embedding, get_combined_info_embedding
from config import SOURCE, BRAND, CATEGORIES, BASE_URL


async def main():
    print("=" * 50)
    print("Second Coat Scraper - Save to JSON")
    print("=" * 50)
    
    scraper = SecondCoatScraper()
    all_products = []
    
    print("\n[1] Scraping products...")
    
    async with scraper:
        for category, url in CATEGORIES.items():
            print(f"\n--- {category.upper()} ---")
            products = await scraper.get_products_from_category(category, url)
            all_products.extend(products)
            print(f"Found {len(products)} products")
    
    print(f"\n[2] Total: {len(all_products)} products")
    
    print("\n[3] Generating embeddings...")
    for i, product in enumerate(all_products):
        print(f"  [{i+1}/{len(all_products)}] {product.get('title', '')[:40]}")
        
        image_url = product.get("image_url")
        if image_url:
            emb = get_image_embedding(image_url)
            product["image_embedding"] = emb
            if emb:
                print(f"    Image embedding: {len(emb)} dims")
        
        info_emb = get_combined_info_embedding(product)
        product["info_embedding"] = info_emb
        if info_emb:
            print(f"    Info embedding: {len(info_emb)} dims")
        
        product["_id"] = str(uuid.uuid4())[:16]
        product["source"] = SOURCE
        product["brand"] = BRAND
        product["second_hand"] = False
    
    output_file = "scraper_secondcoat_products.json"
    with open(output_file, "w") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    
    print(f"\n[4] Saved to {output_file}")
    
    print("\n" + "=" * 50)
    print("Products Summary:")
    print("=" * 50)
    for p in all_products:
        print(f"\nTitle: {p.get('title', 'N/A')}")
        print(f"  Product URL: {p.get('product_url', 'N/A')}")
        print(f"  Image URL: {str(p.get('image_url', ''))[:60]}...")
        print(f"  Price: {p.get('price', 'N/A')}")
        print(f"  Category: {p.get('category', 'N/A')}")
        print(f"  Sizes: {p.get('sizes', 'N/A')}")
        print(f"  Image Embedding: {len(p.get('image_embedding', [])) if p.get('image_embedding') else 'N/A'} dims")
        print(f"  Info Embedding: {len(p.get('info_embedding', [])) if p.get('info_embedding') else 'N/A'} dims")
    
    return all_products


if __name__ == "__main__":
    products = asyncio.run(main())
    print(f"\n\nTotal products: {len(products)}")