"""Rebuild FAISS index from existing raw embeddings at a different cell size.

Loads the previously extracted raw .npz file and re-aggregates.
For cell sizes close to the extraction scale (~0.001 deg for 100m),
skips aggregation and indexes raw pixels directly.

Usage:
    uv run python scripts/rebuild_index.py                    # 100m (no aggregation)
    uv run python scripts/rebuild_index.py --cell-size 0.01   # 1km aggregation
"""

from __future__ import annotations

import argparse

import numpy as np

from aef.config import AEF_DIM, EMBEDDINGS_DIR, INDEX_DIR
from aef.faiss_index import EmbeddingIndex
from aef.similarity import aggregate_to_grid


def main():
    parser = argparse.ArgumentParser(description="Rebuild FAISS index from raw embeddings")
    parser.add_argument(
        "--cell-size",
        type=float,
        default=None,
        help="Grid cell size in degrees. Omit for raw pixel indexing (no aggregation).",
    )
    parser.add_argument(
        "--raw-file",
        type=str,
        default="hokkaido_full_2025_raw.npz",
        help="Raw embeddings filename in data/embeddings/",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year for metadata. Inferred from filename if omitted.",
    )
    args = parser.parse_args()

    # Load raw data
    raw_path = EMBEDDINGS_DIR / args.raw_file
    print(f"Loading: {raw_path}")
    data = np.load(str(raw_path))
    embeddings = data["embeddings"]
    coords = data["coords"]
    bbox = data["bbox"].tolist()
    print(f"Loaded: {len(embeddings):,} pixels, bbox={bbox}")

    if args.cell_size is not None:
        # Aggregate to grid
        print(f"\n=== Aggregating to {args.cell_size}° grid ===")
        emb, crd = aggregate_to_grid(embeddings, coords, args.cell_size)
        cell_size_deg = args.cell_size
    else:
        # No aggregation: normalize raw pixels directly
        print("\n=== No aggregation (raw pixel indexing) ===")
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-8)
        emb = (embeddings / norms).astype(np.float32)
        crd = coords
        # Infer cell size from median spacing
        lon_unique = np.unique(np.round(coords[:, 0], 5))
        cell_size_deg = float(np.median(np.diff(lon_unique)))

    print(f"Vectors: {len(emb):,}")
    print(f"Cell size: {cell_size_deg:.5f}°")
    print(f"Index size estimate: {len(emb) * AEF_DIM * 4 / 1024 / 1024:.0f} MB")

    # Build FAISS index
    print("\n=== Building FAISS index ===")
    index = EmbeddingIndex()
    index.add(emb, crd)
    # Infer year from filename if not specified
    if args.year is not None:
        year = args.year
    else:
        import re
        m = re.search(r"(\d{4})", args.raw_file)
        year = int(m.group(1)) if m else 2025

    index.metadata = {
        "region": "hokkaido",
        "year": year,
        "bbox": bbox,
        "extract_scale": 100,
        "cell_size_deg": cell_size_deg,
        "n_vectors": int(len(emb)),
    }

    index_path = INDEX_DIR / "default"
    index.save(index_path)
    print(f"Index saved: {index.ntotal:,} vectors")

    # Verify
    print("\n=== Verify ===")
    loaded = EmbeddingIndex.load(index_path)
    print(f"Loaded: {loaded.ntotal:,} vectors")

    query = emb[len(emb) // 2]
    sims, idxs, crds = loaded.search(query, k=5)
    print("Top-5 search:")
    for i in range(5):
        print(f"  #{i+1} sim={sims[i]:.4f} at ({crds[i,0]:.4f}, {crds[i,1]:.4f})")

    print("\nDone!")


if __name__ == "__main__":
    main()
