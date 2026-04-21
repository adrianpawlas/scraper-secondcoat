import torch
import numpy as np
from transformers import AutoProcessor, AutoModel
from PIL import Image
import requests
from io import BytesIO
from typing import List, Optional
import warnings

warnings.filterwarnings("ignore")

MODEL_NAME = "google/siglip-base-patch16-384"
embedding_model = None
embedding_processor = None


def get_embedding_model():
    global embedding_model, embedding_processor
    if embedding_model is None:
        print(f"Loading {MODEL_NAME}...")
        embedding_processor = AutoProcessor.from_pretrained(MODEL_NAME)
        embedding_model = AutoModel.from_pretrained(MODEL_NAME)
        embedding_model.eval()
        print(f"Model loaded!")
    return embedding_model, embedding_processor


def download_image(url: str, timeout: int = 30) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content)).convert("RGB")
            return img
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return None


def get_image_embedding(image_url: str) -> Optional[List[float]]:
    if not image_url:
        return None
    
    try:
        model, processor = get_embedding_model()
        img = download_image(image_url)
        
        if img is None:
            return None
        
        inputs = processor(images=img, return_tensors="pt")
        
        with torch.no_grad():
            vision_outputs = model.vision_model(pixel_values=inputs["pixel_values"])
            image_embeds = vision_outputs.pooler_output
        
        embedding = image_embeds[0].detach().numpy()
        
        return normalize_vector(embedding.tolist())
    
    except Exception as e:
        print(f"Error getting image embedding: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_text_embedding(text: str) -> Optional[List[float]]:
    if not text:
        return None
    
    try:
        model, processor = get_embedding_model()
        
        inputs = processor(text=text, return_tensors="pt")
        
        input_ids = inputs["input_ids"]
        attention_mask = inputs.get("attention_mask", torch.ones_like(input_ids))
        
        with torch.no_grad():
            text_outputs = model.text_model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            text_embeds = text_outputs.pooler_output
        
        embedding = text_embeds[0].detach().numpy()
        
        return normalize_vector(embedding.tolist())
    
    except Exception as e:
        print(f"Error getting text embedding: {e}")
        import traceback
        traceback.print_exc()
        return None


def normalize_vector(vec: List[float]) -> List[float]:
    arr = np.array(vec)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def get_combined_info_embedding(product: dict) -> Optional[List[float]]:
    text_parts = []
    weights = []
    
    if product.get("title"):
        text_parts.append(product["title"])
        weights.append(2.0)
    
    if product.get("description"):
        text_parts.append(product["description"])
        weights.append(1.5)
    
    if product.get("category"):
        text_parts.append(product["category"])
        weights.append(1.0)
    
    if product.get("details"):
        text_parts.append(product["details"])
        weights.append(1.0)
    
    if product.get("price"):
        text_parts.append(product["price"])
        weights.append(0.5)
    
    if not text_parts:
        return None
    
    combined = None
    total_weight = 0
    
    for text, weight in zip(text_parts, weights):
        emb = get_text_embedding(text)
        if emb:
            if combined is None:
                combined = np.array(emb) * weight
            else:
                combined += np.array(emb) * weight
            total_weight += weight
    
    if combined is not None and total_weight > 0:
        combined = combined / total_weight
        return normalize_vector(combined.tolist())
    
    return None


def test_embedding():
    print("Testing embedding model...")
    
    test_url = "https://2ndc.ca/cdn/shop/files/espresso_back.webp?v=1774751569"
    print(f"Testing image: {test_url}")
    
    emb = get_image_embedding(test_url)
    
    if emb:
        print(f"Image embedding: {len(emb)} dims")
        print(f"First 5: {emb[:5]}")
    else:
        print("Image embedding FAILED")
    
    print()
    
    test_text = "Second Coat Barback Shirt"
    print(f"Testing text: {test_text}")
    text_emb = get_text_embedding(test_text)
    if text_emb:
        print(f"Text embedding: {len(text_emb)} dims")
        print(f"First 5: {text_emb[:5]}")
    else:
        print("Text embedding FAILED")


if __name__ == "__main__":
    test_embedding()