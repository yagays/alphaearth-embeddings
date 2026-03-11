"""Build a FAISS index from AEF embeddings for the web UI.

Extracts embeddings at a coarser scale (100m), then aggregates to ~1km grid cells.
This creates a manageable index for interactive search.

Usage:
    uv run python scripts/build_index.py
"""

from __future__ import annotations

import numpy as np

from aef.config import EMBEDDINGS_DIR, INDEX_DIR
from aef.ee_client import get_embeddings_tiled, init_ee
from aef.faiss_index import EmbeddingIndex
from aef.similarity import aggregate_to_grid

# Hokkaido full extent (including minor islands)
BBOX = (139.3, 41.3, 145.9, 45.6)
YEAR = 2025
EXTRACT_SCALE = 100  # Extract at 100m/pixel to keep sampleRectangle within limits
CELL_SIZE_DEG = 0.01  # ~1km grid cells for aggregation

# Tile size for extraction (in pixels at the extraction scale)
# 100m/pixel × 300px ≈ 30km per tile side → well within sampleRectangle limits
TILE_SIZE_PX = 300


def main():
    init_ee()

    west, south, east, north = BBOX
    print(f"Region: ({west}, {south}) to ({east}, {north})")
    print(f"Year: {YEAR}, Extract scale: {EXTRACT_SCALE}m, Cell size: {CELL_SIZE_DEG}°")

    # Step 1: Extract
    print("\n=== Step 1: Extract embeddings ===")
    embeddings, coords = get_embeddings_tiled(BBOX, YEAR, scale=EXTRACT_SCALE, tile_size=TILE_SIZE_PX)
    print(f"Extracted: {embeddings.shape[0]} pixels")

    # Save raw
    raw_path = EMBEDDINGS_DIR / f"hokkaido_full_{YEAR}_raw.npz"
    np.savez_compressed(
        raw_path, embeddings=embeddings, coords=coords, bbox=np.array(BBOX)
    )
    print(f"Saved raw: {raw_path} ({raw_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Step 2: Aggregate
    print("\n=== Step 2: Aggregate to grid ===")
    agg_emb, agg_coords = aggregate_to_grid(embeddings, coords, CELL_SIZE_DEG)
    print(f"Grid cells: {agg_emb.shape[0]}")

    # Step 3: Build FAISS index
    print("\n=== Step 3: Build FAISS index ===")
    index = EmbeddingIndex()
    index.add(agg_emb, agg_coords)
    index.metadata = {
        "region": "hokkaido",
        "year": YEAR,
        "bbox": list(BBOX),
        "extract_scale": EXTRACT_SCALE,
        "cell_size_deg": CELL_SIZE_DEG,
        "n_raw_pixels": int(embeddings.shape[0]),
    }

    index_path = INDEX_DIR / "default"
    index.save(index_path)
    print(f"Index saved: {index.ntotal} vectors")

    # Verify
    print("\n=== Verify ===")
    loaded = EmbeddingIndex.load(index_path)
    print(f"Loaded: {loaded.ntotal} vectors")

    # Test search
    query = agg_emb[len(agg_emb) // 2]
    sims, idxs, crds = loaded.search(query, k=5)
    print("Top-5 search:")
    for i in range(5):
        print(f"  #{i+1} sim={sims[i]:.4f} at ({crds[i,0]:.4f}, {crds[i,1]:.4f})")

    print("\nDone!")


if __name__ == "__main__":
    main()
