"""EmbeddingGemma 2 wrapper. Loads only the text + vision encoders (~440M params)."""

from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    def embed_query(self, text: str) -> np.ndarray: ...
    def embed_images(self, paths: list[Path]) -> np.ndarray: ...


class GemmaEmbedder:
    def __init__(self, model_id: str, dim: int):
        import torch
        from sentence_transformers import SentenceTransformer

        self.dim = dim
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        # fp16 can produce NaNs with this model; use bf16 on CUDA, fp32 elsewhere.
        if device == "cuda" and torch.cuda.is_bf16_supported():
            dtype = torch.bfloat16
        else:
            dtype = torch.float32
        self.model = SentenceTransformer(
            model_id,
            device=device,
            model_kwargs={"torch_dtype": dtype},
            config_kwargs={"audio_config": None},  # text + image only
        )

    def _encode(self, inputs, **kwargs) -> np.ndarray:
        return self.model.encode(
            inputs,
            truncate_dim=self.dim,
            normalize_embeddings=True,
            convert_to_numpy=True,
            **kwargs,
        ).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode(text, prompt_name="SearchQuery")

    def embed_images(self, paths: list[Path]) -> np.ndarray:
        # Images take no task prefix; pass each as a single-image interleaved input.
        inputs = [{"text": "<|image|>", "image": [str(p)]} for p in paths]
        return self._encode(inputs, batch_size=8)
