"""Similarity search workflows."""

from __future__ import annotations

import numpy as np
import pandas as pd
from tqdm import tqdm

from aef.faiss_index import EmbeddingIndex


def aggregate_to_grid(
    embeddings: np.ndarray,
    coords: np.ndarray,
    cell_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Aggregate pixel embeddings into grid cells by averaging.

    Uses integer keys and vectorized bincount for fast grouping.

    Args:
        embeddings: N×D array of embedding vectors.
        coords: N×2 array of [lon, lat] coordinates.
        cell_size: Grid cell size in degrees.

    Returns:
        Tuple of (agg_embeddings: M×D, agg_coords: M×2).
    """
    cell_lon_idx = np.floor(coords[:, 0] / cell_size).astype(np.int64)
    cell_lat_idx = np.floor(coords[:, 1] / cell_size).astype(np.int64)

    # Pack into single int64 key: lon_idx * large_prime + lat_idx
    keys = cell_lon_idx * 1_000_000 + cell_lat_idx

    unique_keys, inverse = np.unique(keys, return_inverse=True)
    n_cells = len(unique_keys)
    print(f"Aggregating {len(embeddings)} pixels into {n_cells} grid cells")

    agg_embeddings = np.zeros((n_cells, embeddings.shape[1]), dtype=np.float64)

    # Accumulate using vectorized bincount-like approach
    for dim in tqdm(range(embeddings.shape[1]), desc="Aggregating dims"):
        agg_embeddings[:, dim] = np.bincount(
            inverse, weights=embeddings[:, dim], minlength=n_cells
        )
    counts = np.bincount(inverse, minlength=n_cells)
    agg_embeddings /= counts[:, None]

    # Normalize to unit vectors
    norms = np.linalg.norm(agg_embeddings, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    agg_embeddings /= norms

    # Compute cell center coordinates
    agg_coords = np.column_stack([
        (unique_keys // 1_000_000) * cell_size + cell_size / 2,
        (unique_keys % 1_000_000) * cell_size + cell_size / 2,
    ])

    return agg_embeddings.astype(np.float32), agg_coords


def query_similar_regions(
    index: EmbeddingIndex, query_emb: np.ndarray, k: int = 10
) -> pd.DataFrame:
    """Run kNN search and return results as a DataFrame.

    Args:
        index: FAISS embedding index.
        query_emb: 64-dimensional query vector.
        k: Number of results.

    Returns:
        DataFrame with columns: rank, similarity, lon, lat.
    """
    similarities, indices, coords = index.search(query_emb, k=k)

    df = pd.DataFrame(
        {
            "rank": range(1, len(similarities) + 1),
            "similarity": similarities,
            "index": indices,
            "lon": coords[:, 0],
            "lat": coords[:, 1],
        }
    )
    return df


def compute_similarity_map(
    embeddings: np.ndarray, query_emb: np.ndarray, shape: tuple[int, int]
) -> np.ndarray:
    """Compute dot-product similarity map between all embeddings and a query.

    Args:
        embeddings: N×64 array (where N = H*W).
        query_emb: 64-dimensional query vector.
        shape: (H, W) to reshape result.

    Returns:
        H×W similarity map.
    """
    if query_emb.ndim == 2:
        query_emb = query_emb.squeeze(0)

    # Dot product (= cosine similarity for unit vectors)
    sim = embeddings @ query_emb
    return sim.reshape(shape)
