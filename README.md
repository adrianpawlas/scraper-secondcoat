# Second Coat Scraper

Fashion product scraper for Second Coat (https://2ndc.ca) - uploads to Supabase with 768-dim embeddings.

## Features

- Scrapes products from tops, bottoms, and accessories categories
- Generates image embeddings using `google/siglip-base-patch16-384` (768-dim)
- Generates info embeddings from title + description + category
- Uploads to Supabase database
- Scheduled automation (weekly) + manual run capability

## Setup

```bash
# Clone and install
git clone https://github.com/adrianpawlas/scraper-secondcoat.git
cd scraper-secondcoat
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your Supabase keys
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| SUPABASE_URL | Supabase project URL | `https://yqawmzggcgpeyaaynrjk.supabase.co` |
| SUPABASE_ANON_KEY | Supabase anon key | (required) |
| SOURCE | Source identifier | `scraper-secondcoat` |
| BRAND | Brand name | `Second Coat` |

## Usage

### Manual Run

```bash
# Full scrape + upload
python main.py

# Options
python main.py --skip-embed    # Skip embedding generation
python main.py --skip-upload    # Skip Supabase upload
python main.py --load file.json # Load from file
```

### GitHub Actions (Automated)

Automatically runs every Wednesday at 3PM UTC. Also can be triggered manually from GitHub UI.

## Output

- Products stored in Supabase `products` table
- Fields: `source`, `brand`, `product_url`, `image_url`, `title`, `category`, `gender`, `image_embedding`, `info_embedding`

## Embedding Model

- Model: `google/siglip-base-patch16-384`
- Dimensions: 768
- Image embedding: from product images
- Info embedding: weighted combination of title (2x), description (1.5x), category (1x), details (1x), price (0.5x)