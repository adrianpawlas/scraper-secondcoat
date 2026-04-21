#!/usr/bin/env python3
"""
Second Coat Scraper - Smart Product Management
Features:
- Batch inserts (50 products per batch)
- Smart upsert (compare and only update if changed)
- Skip unchanged products
- Only regenerate embeddings when needed
- Staggered embedding generation
- Error handling with retry
- Stale product removal
- Run summary
"""

import os
import sys
import json
import logging
import asyncio
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

import requests

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

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Environment
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://yqawmzggcgpeyaaynrjk.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY', '')
SOURCE = os.getenv('SOURCE', 'scraper-secondcoat')
BRAND = os.getenv('BRAND', 'Second Coat')

# Config
BATCH_SIZE = 50
EMBEDDING_DELAY = 0.5  # seconds
MAX_RETRIES = 3
STALE_THRESHOLD_RUNS = 2  # Delete after 2 consecutive runs not seen

CATEGORIES = {
    'tops': 'https://2ndc.ca/collections/tops',
    'bottoms': 'https://2ndc.ca/collections/bottoms',
    'accessories': 'https://2ndc.ca/collections/accessories',
}


@dataclass
class RunStats:
    """Statistics for a scraper run."""
    new_added: int = 0
    products_updated: int = 0
    products_unchanged: int = 0
    stale_deleted: int = 0
    embeddings_generated: int = 0
    errors: int = 0
    
    def print_summary(self):
        """Print run summary."""
        logger.info('=' * 50)
        logger.info('RUN SUMMARY')
        logger.info('=' * 50)
        logger.info(f'  New products added:      {self.new_added}')
        logger.info(f'  Products updated:       {self.products_updated}')
        logger.info(f'  Products unchanged:      {self.products_unchanged}')
        logger.info(f'  Stale products deleted:  {self.stale_deleted}')
        logger.info(f'  Embeddings generated:  {self.embeddings_generated}')
        logger.info(f'  Errors:                 {self.errors}')
        logger.info('=' * 50)


def check_env() -> bool:
    """Verify required environment variables."""
    if not SUPABASE_KEY:
        logger.error('SUPABASE_ANON_KEY not set!')
        return False
    return True


def get_headers() -> Dict[str, str]:
    """Get Supabase API headers."""
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }


async def scrape_products() -> List[Dict[str, Any]]:
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


def fetch_existing_products() -> Dict[str, Dict[str, Any]]:
    """Fetch all existing products from this source."""
    logger.info('Fetching existing products from database...')
    
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/products?source=eq.{SOURCE}&select=*',
        headers=get_headers()
    )
    
    if resp.status_code != 200:
        logger.error(f'Failed to fetch products: {resp.status_code}')
        return {}
    
    products = resp.json()
    existing = {}
    
    for p in products:
        key = p.get('product_url', '')
        if key:
            existing[key] = p
    
    logger.info(f'Found {len(existing)} existing products')
    return existing


def generate_product_id(title: str) -> str:
    """Generate unique product ID."""
    hash_input = f'{SOURCE}:{title}'
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


def get_product_key(product: Dict) -> str:
    """Get unique key for product."""
    return product.get('product_url', '')


def compare_product_data(scraped: Dict, existing: Dict) -> Tuple[bool, List[str]]:
    """Compare scraped product with existing to determine if update needed.
    
    Returns: (needs_update, changed_fields)
    """
    changed = []
    
    # Compare fields that matter
    fields_to_check = [
        ('title', 'title'),
        ('description', 'description'),
        ('price', 'price'),
        ('category', 'category'),
        ('image_url', 'image_url'),
    ]
    
    for scraped_key, existing_key in fields_to_check:
        scraped_val = scraped.get(scraped_key, '')
        existing_val = existing.get(existing_key, '')
        
        if str(scraped_val) != str(existing_val):
            changed.append(scraped_key)
    
    return len(changed) > 0, changed


def needs_embedding_regeneration(scraped: Dict, existing: Dict) -> bool:
    """Check if embeddings need to be regenerated.
    
    Only regenerate if:
    - Product is new, OR
    - Image URL has changed
    """
    if not existing:
        return True
    
    scraped_url = scraped.get('image_url', '')
    existing_url = existing.get('image_url', '')
    
    return scraped_url != existing_url


def generate_embeddings_staggered(products: List[Dict], existing: Dict) -> List[Dict]:
    """Generate embeddings with staggered API calls."""
    from embeddings import get_image_embedding, get_combined_info_embedding
    
    logger.info('Generating embeddings...')
    
    for i, product in enumerate(products):
        title = product.get('title', f'Product {i}')
        product_key = get_product_key(product)
        existing_product = existing.get(product_key, {})
        
        # Check if we need new embeddings
        if needs_embedding_regeneration(product, existing_product):
            logger.info(f'  [{i+1}/{len(products)}] {title[:40]} (generating embeddings)')
            
            # Staggered API calls
            time.sleep(EMBEDDING_DELAY)
            
            # Image embedding
            image_url = product.get('image_url')
            if image_url:
                emb = get_image_embedding(image_url)
                product['image_embedding'] = emb
            
            # Info embedding
            info_emb = get_combined_info_embedding(product)
            product['info_embedding'] = info_emb
        else:
            # Use existing embeddings
            product['image_embedding'] = existing_product.get('image_embedding', [])
            product['info_embedding'] = existing_product.get('info_embedding', [])
            logger.info(f'  [{i+1}/{len(products)}] {title[:40]} (using existing)')
    
    return products


def batch_insert(records: List[Dict]) -> Tuple[int, int]:
    """Insert batch of products with retry logic.
    
    Returns: (success_count, failure_count)
    """
    if not records:
        return 0, 0
    
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                f'{SUPABASE_URL}/rest/v1/products',
                headers=get_headers(),
                json=records
            )
            
            if resp.status_code in [200, 201]:
                return len(records), 0
            
            if attempt < MAX_RETRIES - 1:
                logger.warning(f'Batch insert failed (attempt {attempt + 1}), retrying...')
                time.sleep(1)
                
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f'Batch insert error: {e}, retrying...')
                time.sleep(1)
    
    # Failed after all retries
    logger.error(f'Batch insert failed after {MAX_RETRIES} attempts')
    
    # Log failed products
    with open('failed_products.log', 'a') as f:
        for record in records:
            f.write(f"{datetime.now().isoformat()} - {record.get('title', 'unknown')}\n")
    
    return 0, len(records)


def insert_products_batch(products: List[Dict], existing: Dict) -> Tuple[int, int, int]:
    """Insert products - new via POST, updated via PATCH.
    
    Returns: (new_count, update_count, unchanged_count)
    """
    logger.info(f'Processing {len(products)} products...')
    
    new_count = 0
    update_count = 0
    unchanged_count = 0
    
    for product in products:
        product_key = get_product_key(product)
        existing_product = existing.get(product_key)
        
        # Add ID
        if not product.get('id'):
            product['id'] = generate_product_id(product.get('title', ''))
        
        # Check if changed
        if existing_product:
            needs_update, changed = compare_product_data(product, existing_product)
            
            if not needs_update:
                # Skip unchanged - use existing embeddings
                product['image_embedding'] = existing_product.get('image_embedding', [])
                product['info_embedding'] = existing_product.get('info_embedding', [])
                unchanged_count += 1
                continue
            
            # Update via PATCH - only include fields that exist
            update_record = {}
            if product.get('title'):
                update_record['title'] = product.get('title')
            if product.get('description') is not None:
                update_record['description'] = product.get('description')
            if product.get('price'):
                update_record['price'] = product.get('price')
            if product.get('category'):
                update_record['category'] = product.get('category')
            
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/products?id=eq.{existing_product.get('id')}",
                headers=get_headers(),
                json=update_record
            )
            
            if resp.status_code in [200, 204]:
                update_count += 1
                logger.info(f'  Updated: {product.get("title", "")[:40]} changed: {changed}')
            else:
                logger.error(f'  Update failed: {product.get("title", "")} - {resp.status_code}')
        
        else:
            # New product - insert via POST
            record = {
                'id': product.get('id'),
                'source': SOURCE,
                'brand': BRAND,
                'product_url': product.get('product_url'),
                'image_url': product.get('image_url'),
                'title': product.get('title'),
                'description': product.get('description') or None,
                'category': product.get('category'),
                'gender': 'unisex',
                'second_hand': False,
                'image_embedding': product.get('image_embedding', []),
                'info_embedding': product.get('info_embedding', []),
            }
            
            resp = requests.post(
                f'{SUPABASE_URL}/rest/v1/products',
                headers=get_headers(),
                json=record
            )
            
            if resp.status_code in [200, 201]:
                new_count += 1
                logger.info(f'  New: {product.get("title", "")[:40]}')
            else:
                logger.error(f'  Insert failed: {product.get("title", "")} - {resp.status_code}')
    
    logger.info(f'Processed: {new_count} new, {update_count} updated, {unchanged_count} unchanged')
    
    return new_count, update_count, unchanged_count


def remove_stale_products(scraped_products: List[Dict], existing: Dict) -> int:
    """Remove products not seen in current run.
    
    A product is stale if it wasn't seen in current scrape.
    For now, just set skip_count and check on next run.
    """
    logger.info('Checking for stale products...')
    
    current_keys = set(get_product_key(p) for p in scraped_products)
    
    # Find products not in current scrape
    stale_count = 0
    for key, product in existing.items():
        if key not in current_keys:
            # Increment skip_count instead of immediate delete
            product_id = product.get('id')
            if product_id:
                current_skip = product.get('skip_count', 0)
                new_skip = current_skip + 1
                
                if new_skip >= STALE_THRESHOLD_RUNS:
                    # Delete after 2 missed runs
                    resp = requests.delete(
                        f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                        headers=get_headers()
                    )
                    if resp.status_code in [200, 204]:
                        stale_count += 1
                else:
                    # Just update skip_count
                    requests.patch(
                        f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                        headers=get_headers(),
                        json={'skip_count': new_skip}
                    )
    
    logger.info(f'Deleted {stale_count} stale products')
    return stale_count


def update_last_seen(scraped_products: List[Dict], existing: Dict):
    """Update last_seen_at timestamp for all products."""
    logger.info('Updating timestamps...')
    
    for product in scraped_products:
        product_key = get_product_key(product)
        existing_product = existing.get(product_key)
        
        if existing_product:
            product_id = existing_product.get('id')
            if product_id:
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                    headers=get_headers(),
                    json={'last_seen_at': datetime.now().isoformat(), 'skip_count': 0}
                )
        else:
            # New product - add timestamp in next insert
            product['last_seen_at'] = datetime.now().isoformat()


async def run_scraper():
    """Main scraper execution."""
    global SUPABASE_KEY
    
    # Allow API key as argument
    if len(sys.argv) > 1:
        SUPABASE_KEY = sys.argv[1]
    
    logger.info('=' * 50)
    logger.info('Second Coat Scraper - Smart Mode')
    logger.info('=' * 50)
    
    if not check_env():
        sys.exit(1)
    
    start_time = datetime.now()
    stats = RunStats()
    
    try:
        # 1. Fetch existing products
        existing = fetch_existing_products()
        
        # 2. Scrape products
        products = await scrape_products()
        
        if not products:
            logger.warning('No products scraped!')
            return False
        
        # 3. Add IDs
        for product in products:
            if not product.get('_id'):
                product['_id'] = generate_product_id(product.get('title', ''))
            if not product.get('source'):
                product['source'] = SOURCE
            if not product.get('brand'):
                product['brand'] = BRAND
            if not product.get('gender'):
                product['gender'] = 'unisex'
            if not product.get('second_hand'):
                product['second_hand'] = False
        
        # 4. Generate embeddings (staggered, only when needed)
        products = generate_embeddings_staggered(products, existing)
        
        # 5. Insert/update in batches
        new_count, update_count, unchanged_count = insert_products_batch(products, existing)
        stats.new_added = new_count
        stats.products_updated = update_count
        stats.products_unchanged = unchanged_count
        stats.embeddings_generated = new_count + update_count
        
        # 6. Update timestamps
        update_last_seen(products, existing)
        
        # 7. Remove stale products
        stale_deleted = remove_stale_products(products, existing)
        stats.stale_deleted = stale_deleted
        
        # Save to file
        filepath = f'{SOURCE}_products.json'
        with open(filepath, 'w') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f'Completed in {duration:.1f}s')
        
        # Print summary
        stats.print_summary()
        
        return True
    
    except Exception as e:
        logger.exception(f'Scraper failed: {e}')
        stats.errors += 1
        stats.print_summary()
        return False


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Second Coat Scraper - Smart')
    parser.add_argument('api_key', nargs='?', help='Supabase API key (optional, uses ENV)')
    args = parser.parse_args()
    
    if args.api_key:
        SUPABASE_KEY = args.api_key
    
    result = asyncio.run(run_scraper())
    sys.exit(0 if result else 1)


if __name__ == '__main__':
    main()