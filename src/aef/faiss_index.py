"""FAISS index for embedding similarity search."""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from aef.config import AEF_DIM


class EmbeddingIndex:
    """FAISS index wrapper for AEF embeddings with coordinate tracking."""

    def __init__(self, dim: int = AEF_DIM):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)  # Inner product = cosine for unit vectors
        self.coords: np.ndarray | None = None
        self.metadata: dict = {}

    @property
    def ntotal(self) -> int:
        return self.index.ntotal

    def add(self, embeddings: np.ndarray, coords: np.ndarray) -> None:
        """Add embeddings and their coordinates to the index.

        Args:
            embeddings: N×64 float32 array.
            coords: N×2 array of [lon, lat].
        """
        assert embeddings.ndim == 2 and embeddings.shape[1] == self.dim
        assert coords.shape == (embeddings.shape[0], 2)

        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        self.index.add(embeddings)

        if self.coords is None:
            self.coords = coords.astype(np.float64)
        else:
            self.coords = np.concatenate(
                [self.coords, coords.astype(np.float64)], axis=0
            )

    def search(
        self, query: np.ndarray, k: int = 10
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Search for k nearest neighbors.

        Args:
            query: 1×64 or 64-dimensional query vector.
            k: Number of neighbors to return.

        Returns:
            Tuple of (similarities: k, indices: k, coords: k×2).
        """
        if query.ndim == 1:
            query = query.reshape(1, -1)
        query = np.ascontiguousarray(query, dtype=np.float32)

        k = min(k, self.ntotal)
        similarities, indices = self.index.search(query, k)

        similarities = similarities[0]
        indices = indices[0]
        result_coords = self.coords[indices] if self.coords is not None else None

        return similarities, indices, result_coords

    def save(self, path: str | Path) -> None:
        """Save index to disk as .faiss + .coords.npy + .meta.json."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(path.with_suffix(".faiss")))

        if self.coords is not None:
            np.save(str(path.with_suffix(".coords.npy")), self.coords)

        meta = {
            "dim": self.dim,
            "ntotal": self.ntotal,
            **self.metadata,
        }
        with open(path.with_suffix(".meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> EmbeddingIndex:
        """Load index from disk."""
        path = Path(path)

        idx = cls()
        idx.index = faiss.read_index(str(path.with_suffix(".faiss")))
        idx.dim = idx.index.d

        coords_path = path.with_suffix(".coords.npy")
        if coords_path.exists():
            idx.coords = np.load(str(coords_path))

        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            with open(meta_path) as f:
                idx.metadata = json.load(f)

        return idx
