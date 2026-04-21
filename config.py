import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yqawmzggcgpeyaaynrjk.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBiYXNlIiwicmVmIjoieXFhd216Z2djZ3BleWFhW25ya2siLCJyb2xlIjoic2VydmljZV9yb2xlIiwiaWF0IjoxNzU1MDEwOTI2IiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4")

BASE_URL = "https://2ndc.ca"
CATEGORIES = {
    "tops": "https://2ndc.ca/collections/tops",
    "bottoms": "https://2ndc.ca/collections/bottoms",
    "accessories": "https://2ndc.ca/collections/accessories",
}

SOURCE = "scraper-secondcoat"
BRAND = "Second Coat"
SECOND_HAND = False

EMBEDDING_MODEL = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768

CURRENCY_CONVERSION = {
    "CZK": {"USD": 0.044, "EUR": 0.040, "PLN": 0.16, "GBP": 0.034},
}