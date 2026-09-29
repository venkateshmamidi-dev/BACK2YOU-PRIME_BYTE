import os
import io
import numpy as np
from typing import List, Optional, Union
from PIL import Image
from backend.config import settings

def preprocess_image(image_input: Union[str, bytes, Image.Image]) -> Optional[Image.Image]:
    """Helper to convert path, bytes, or PIL Image into RGB PIL Image."""
    try:
        if isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        elif isinstance(image_input, (bytes, bytearray)):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, str):
            if os.path.exists(image_input):
                return Image.open(image_input).convert("RGB")
            # If path points to uploads relative to base
            upload_full = os.path.join(settings.BASE_DIR, image_input.lstrip("/\\"))
            if os.path.exists(upload_full):
                return Image.open(upload_full).convert("RGB")
    except Exception as e:
        print(f"[Vision] Error loading image: {e}")
    return None

def generate_image_embedding(image_input: Union[str, bytes, Image.Image]) -> Optional[List[float]]:
    """
    Generates a normalized visual perceptual feature embedding (384 dimensions)
    using RGB color distribution histograms and spatial downsampled grid features.
    Lightweight, fast, and does not require PyTorch or GPU.
    """
    img = preprocess_image(image_input)
    if img is None:
        return None

    try:
        resized = img.resize((32, 32))
        arr = np.array(resized, dtype=np.float32) / 255.0
        # Color distribution (RGB channels, 32 bins each = 96 features)
        hist_r, _ = np.histogram(arr[:, :, 0], bins=32, range=(0, 1))
        hist_g, _ = np.histogram(arr[:, :, 1], bins=32, range=(0, 1))
        hist_b, _ = np.histogram(arr[:, :, 2], bins=32, range=(0, 1))
        # Spatial thumbnail features (288 dimensions)
        spatial = arr.mean(axis=2).flatten()[:288]
        full_vec = np.concatenate([hist_r, hist_g, hist_b, spatial])  # Exactly 384 dimensions
        norm = np.linalg.norm(full_vec)
        if norm > 0:
            full_vec = full_vec / norm
        return full_vec.tolist()
    except Exception as e:
        print(f"[Vision] Perceptual feature extraction error: {e}")
        return [0.0] * 384

def calculate_image_similarity(
    embedding1: Optional[Union[List[float], np.ndarray]],
    embedding2: Optional[Union[List[float], np.ndarray]]
) -> float:
    """
    Calculates cosine similarity between two visual embeddings.
    Returns float score in range [0.0, 1.0].
    """
    if embedding1 is None or embedding2 is None:
        return 0.0

    v1 = np.asarray(embedding1, dtype=np.float32).flatten()
    v2 = np.asarray(embedding2, dtype=np.float32).flatten()

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    sim = float(np.dot(v1, v2) / (norm1 * norm2))
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0 else sim))

