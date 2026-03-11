"""FastAPI backend for AEF similarity search."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aef.config import INDEX_DIR
from aef.faiss_index import EmbeddingIndex

app = FastAPI(title="AEF Similarity Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global index store
_index: EmbeddingIndex | None = None


def _get_index() -> EmbeddingIndex:
    global _index
    if _index is None:
        # Try to load default index
        default_path = INDEX_DIR / "default"
        if default_path.with_suffix(".faiss").exists():
            _index = EmbeddingIndex.load(default_path)
        else:
            raise HTTPException(
                status_code=503,
                detail="No index loaded. Build an index first using the notebooks.",
            )
    return _index


class SearchRequest(BaseModel):
    bbox: list[float]  # [west, south, east, north]
    year: int = 2023
    k: int = 10
    exclude_query: bool = False
    min_distance_km: float = 0


class SearchResult(BaseModel):
    rank: int
    similarity: float
    lon: float
    lat: float


class SearchResponse(BaseModel):
    query_center: list[float]  # [lon, lat]
    results: list[SearchResult]


class StatusResponse(BaseModel):
    loaded: bool
    ntotal: int = 0
    metadata: dict = {}


class EmbeddingResponse(BaseModel):
    lon: float
    lat: float
    embedding: list[float]


@app.get("/api/status", response_model=StatusResponse)
def get_status():
    """Return info about the loaded index."""
    try:
        index = _get_index()
        return StatusResponse(
            loaded=True,
            ntotal=index.ntotal,
            metadata=index.metadata,
        )
    except HTTPException:
        return StatusResponse(loaded=False)


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """Similarity search: average embeddings in bbox, then kNN."""
    index = _get_index()

    west, south, east, north = req.bbox
    center_lon = (west + east) / 2
    center_lat = (south + north) / 2

    # Find all indexed cells within the query bbox
    coords = index.coords
    mask = (
        (coords[:, 0] >= west)
        & (coords[:, 0] <= east)
        & (coords[:, 1] >= south)
        & (coords[:, 1] <= north)
    )

    if not np.any(mask):
        raise HTTPException(
            status_code=404,
            detail="No indexed cells found within the specified bbox. "
            "Try a larger area or check that the bbox overlaps the indexed region.",
        )

    # Get embeddings for cells in bbox and compute mean
    matched_indices = np.where(mask)[0]
    matched_embeddings = np.array(
        [index.index.reconstruct(int(i)) for i in matched_indices], dtype=np.float32
    )
    query_emb = matched_embeddings.mean(axis=0)

    # Normalize to unit vector for cosine similarity
    norm = np.linalg.norm(query_emb)
    if norm > 1e-8:
        query_emb /= norm

    # Search (fetch extra candidates when filtering)
    # At 100m grid, 3km radius contains ~2800 cells, so we need many candidates
    needs_filter = req.exclude_query or req.min_distance_km > 0
    if needs_filter:
        # Rough estimate: cells in exclusion circle + k margin
        # 0.1 = grid cell size in km (100m), 3.15 ≈ pi (circle area estimate)
        r_cells = int((req.min_distance_km / 0.1) ** 2 * 3.15) if req.min_distance_km > 0 else 0
        fetch_k = max(req.k * 5, r_cells + req.k * 3)
    else:
        fetch_k = req.k
    fetch_k = min(fetch_k, index.ntotal)
    similarities, indices, result_coords = index.search(query_emb, k=fetch_k)

    # Precompute min distance in degrees (approximate)
    min_dist_deg = req.min_distance_km / 111.0 if req.min_distance_km > 0 else 0

    results = []
    for i in range(len(similarities)):
        rlon, rlat = float(result_coords[i, 0]), float(result_coords[i, 1])
        if req.exclude_query and west <= rlon <= east and south <= rlat <= north:
            continue
        if min_dist_deg > 0:
            dlat = rlat - center_lat
            dlon = (rlon - center_lon) * np.cos(np.radians(center_lat))
            if np.sqrt(dlat**2 + dlon**2) * 111.0 < req.min_distance_km:
                continue
        if len(results) >= req.k:
            break
        results.append(
            SearchResult(
                rank=len(results) + 1,
                similarity=float(similarities[i]),
                lon=rlon,
                lat=rlat,
            )
        )

    return SearchResponse(
        query_center=[center_lon, center_lat],
        results=results,
    )


@app.get("/api/embedding", response_model=EmbeddingResponse)
def get_embedding(lon: float, lat: float):
    """Get the embedding vector for the nearest indexed cell."""
    index = _get_index()

    # Find nearest cell by coordinate distance
    coords = index.coords
    dists = np.sqrt((coords[:, 0] - lon) ** 2 + (coords[:, 1] - lat) ** 2)
    nearest_idx = int(np.argmin(dists))

    emb = index.index.reconstruct(nearest_idx)

    return EmbeddingResponse(
        lon=float(coords[nearest_idx, 0]),
        lat=float(coords[nearest_idx, 1]),
        embedding=emb.tolist(),
    )
