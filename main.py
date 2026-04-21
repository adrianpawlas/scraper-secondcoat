#!/usr/bin/env python3
"""
Second Coat Scraper
Fetches products from Second Coat fashion store and uploads to Supabase.
Can run manually or via scheduled automation.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Environment variables with defaults for local development
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://yqawmzggcgpeyaaynrjk.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY', '')
SOURCE = os.getenv('SOURCE', 'scraper-secondcoat')
BRAND = os.getenv('BRAND', 'Second Coat')

# Categories to scrape
CATEGORIES = {
    'tops': 'https://2ndc.ca/collections/tops',
    'bottoms': 'https://2ndc.ca/collections/bottoms',
    'accessories': 'https://2ndc.ca/collections/accessories',
}


def check_env():
    """Verify required environment variables."""
    if not SUPABASE_KEY:
        logger.error('SUPABASE_ANON_KEY not set!')
        logger.info('Get key from: Supabase Dashboard > Settings > API > Project API keys > anon')
        return False
    return True


async def scrape_products():
    """Scrape all products from Second Coat."""
    from scraper import SecondCoatScraper
    
    logger.info('Starting scraper...')
    all_products = []
    
    async with SecondCoatScraper() as scraper:
        for category, url in CATEGORIES.items():
            logger.info(f'Scraping {category}...')
            products = await scraper.get_products_from_category(category, url)
            all_products.extend(products)
            logger.info(f'Found {len(products)} products in {category}')
    
    logger.info(f'Total products scraped: {len(all_products)}')
    return all_products


def generate_embeddings(products):
    """Generate embeddings for all products."""
    from embeddings import get_image_embedding, get_combined_info_embedding
    
    logger.info('Generating embeddings...')
    
    for i, product in enumerate(products):
        title = product.get('title', f'Product {i}')
        logger.info(f'  [{i+1}/{len(products)}] {title[:40]}')
        
        # Image embedding
        image_url = product.get('image_url')
        if image_url:
            emb = get_image_embedding(image_url)
            product['image_embedding'] = emb
            if emb:
                logger.debug(f'    Image embedding: {len(emb)} dims')
        
        # Info embedding
        info_emb = get_combined_info_embedding(product)
        product['info_embedding'] = info_emb
        if info_emb:
            logger.debug(f'    Info embedding: {len(info_emb)} dims')
    
    return products


def upload_to_supabase(products):
    """Upload products to Supabase."""
    import requests
    
    logger.info(f'Uploading {len(products)} products to Supabase...')
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
    
    # Delete existing products from this source
    delete_url = f'{SUPABASE_URL}/rest/v1/products?source=eq.{SOURCE}'
    resp = requests.delete(delete_url, headers=headers)
    logger.info(f'Deleted existing: {resp.status_code}')
    
    # Upload new products
    success = 0
    failed = 0
    
    for product in products:
        # Ensure embeddings are proper lists
        image_emb = product.get('image_embedding', [])
        info_emb = product.get('info_embedding', [])
        
        # Convert to proper Python lists if needed
        if isinstance(image_emb, str):
            image_emb = json.loads(image_emb)
        if isinstance(info_emb, str):
            info_emb = json.loads(info_emb)
        
        record = {
            'id': product.get('_id', product.get('id')),
            'source': SOURCE,
            'brand': BRAND,
            'product_url': product.get('product_url'),
            'image_url': product.get('image_url'),
            'title': product.get('title'),
            'description': product.get('description') or None,
            'category': product.get('category'),
            'gender': 'unisex',
            'second_hand': False,
            'image_embedding': image_emb,
            'info_embedding': info_emb,
        }
        
        resp = requests.post(
            f'{SUPABASE_URL}/rest/v1/products',
            headers=headers,
            json=record
        )
        
        if resp.status_code in [200, 201]:
            success += 1
            logger.debug(f'Uploaded: {record["title"][:40]}')
        else:
            failed += 1
            logger.error(f'Failed: {record["title"][:40]} - {resp.status_code}: {resp.text[:100]}')
    
    logger.info(f'Upload complete: {success} success, {failed} failed')
    return success, failed


def save_products(products, filepath=None):
    """Save products to JSON file."""
    if filepath is None:
        filepath = f'{SOURCE}_products.json'
    
    with open(filepath, 'w') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    logger.info(f'Saved {len(products)} products to {filepath}')
    return filepath


def load_products(filepath=None):
    """Load products from JSON file."""
    if filepath is None:
        filepath = f'{SOURCE}_products.json'
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)


def add_product_ids(products):
    """Add unique IDs to products."""
    import hashlib
    from datetime import datetime
    
    for product in products:
        if not product.get('_id'):
            title = product.get('title', '')
            hash_input = f'{SOURCE}:{title}:{datetime.now().isoformat()}'
            product['_id'] = hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    return products


async def run_scraper(embed=True, upload=True, save=True):
    """Main scraper execution."""
    logger.info('=' * 50)
    logger.info('Second Coat Scraper Starting')
    logger.info('=' * 50)
    
    start_time = datetime.now()
    
    try:
        # Scrape products
        products = await scrape_products()
        
        if not products:
            logger.warning('No products scraped!')
            return False
        
        # Add IDs
        products = add_product_ids(products)
        
        # Generate embeddings
        if embed:
            products = generate_embeddings(products)
        
        # Save locally
        if save:
            save_products(products)
        
        # Upload to Supabase
        if upload and SUPABASE_KEY:
            upload_to_supabase(products)
        elif upload and not SUPABASE_KEY:
            logger.warning('SUPABASE_KEY not set, skipping upload')
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info('=' * 50)
        logger.info(f'Complete in {duration:.1f}s - {len(products)} products')
        logger.info('=' * 50)
        
        return True
    
    except Exception as e:
        logger.exception(f'Scraper failed: {e}')
        return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Second Coat Scraper')
    parser.add_argument('--skip-embed', action='store_true', help='Skip embedding generation')
    parser.add_argument('--skip-upload', action='store_true', help='Skip Supabase upload')
    parser.add_argument('--skip-save', action='store_true', help='Skip saving to file')
    parser.add_argument('--load', metavar='FILE', help='Load from existing JSON file')
    args = parser.parse_args()
    
    # Manual run check
    if args.load:
        logger.info(f'Loading from {args.load}')
        products = load_products(args.load)
        if products:
            if not args.skip_upload and SUPABASE_KEY:
                upload_to_supabase(products)
            return
    
    # Check environment
    if args.upload and not check_env():
        sys.exit(1)
    
    # Run scraper
    result = asyncio.run(run_scraper(
        embed=not args.skip_embed,
        upload=not args.skip_upload,
        save=not args.skip_save
    ))
    
    sys.exit(0 if result else 1)


if __name__ == '__main__':
    import asyncio
    main()