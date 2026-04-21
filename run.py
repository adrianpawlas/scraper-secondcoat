#!/usr/bin/env python3

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import SecondCoatScraper
from embeddings import get_image_embedding, get_text_embedding, get_combined_info_embedding
from supabase_uploader import SupabaseUploader
from config import SOURCE, BRAND, CATEGORIES, BASE_URL


async def main():
    print("=" * 50)
    print("Second Coat Scraper")
    print("=" * 50)
    
    scraper = SecondCoatScraper()
    all_products = []
    
    print("\n[1] Scraping products from all categories...")
    
    async with scraper:
        for category, url in CATEGORIES.items():
            print(f"\n--- {category.upper()} ---")
            products = await scraper.get_products_from_category(category, url)
            all_products.extend(products)
            print(f"Found {len(products)} products")
    
    print(f"\n[2] Total products scraped: {len(all_products)}")
    
    print("\n[3] Generating embeddings...")
    uploader = SupabaseUploader()
    
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
        
        print()
    
    print("\n[4] Uploading to Supabase...")
    
    results = uploader.upload_products(all_products)
    
    print(f"\n=== DONE ===")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    
    return all_products


if __name__ == "__main__":
    products = asyncio.run(main())
    print(f"\nScraped {len(products)} products total")