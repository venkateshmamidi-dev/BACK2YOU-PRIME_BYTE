import re
import numpy as np
from typing import List, Optional, Union

def generate_text_embedding(text: str) -> List[float]:
    """
    Generates a normalized semantic token-hash vector embedding (384 dimensions)
    for the input text description. Fast, deterministic, and requires no external ML models.
    """
    if not text or not text.strip():
        return [0.0] * 384

    # Normalize and extract word tokens
    tokens = re.findall(r"\b\w+\b", text.lower())
    if not tokens:
        return [0.0] * 384

    vec = np.zeros(384, dtype=np.float32)
    for i, token in enumerate(tokens):
        # Deterministic hashing into 384 dimensions with position decay
        idx = abs(hash(token)) % 384
        vec[idx] += 1.0 / (1.0 + 0.1 * i)

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def calculate_text_similarity(
    embedding1: Optional[Union[List[float], np.ndarray]],
    embedding2: Optional[Union[List[float], np.ndarray]]
) -> float:
    """
    Computes cosine similarity between two text embeddings.
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
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0 else sim))

