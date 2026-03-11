"""Earth Engine client for extracting AlphaEarth Foundations embeddings."""

from __future__ import annotations

import ee
import numpy as np
from tqdm import tqdm

from aef.config import AEF_BANDS, AEF_COLLECTION, AEF_DIM, AEF_SCALE


def init_ee(project: str | None = None) -> None:
    """Initialize Earth Engine API."""
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)


def _get_image(
    year: int, region: ee.Geometry | None = None, scale: int = AEF_SCALE
) -> ee.Image:
    """Get the AEF mosaic image for a given year and region.

    The AEF collection is tiled, so we filter spatially and mosaic.
    setDefaultProjection is needed so that sampleRectangle uses the
    correct pixel grid instead of collapsing to 1×1.
    """
    col = ee.ImageCollection(AEF_COLLECTION).filter(
        ee.Filter.calendarRange(year, year, "year")
    )
    if region is not None:
        col = col.filterBounds(region)
    return col.mosaic().select(AEF_BANDS).setDefaultProjection(
        crs="EPSG:4326", scale=scale
    )


def get_embedding_at_point(
    lon: float, lat: float, year: int, buffer_m: int = 0
) -> np.ndarray:
    """Get embedding vector at a single point.

    Args:
        lon: Longitude.
        lat: Latitude.
        year: Year (2017-2025).
        buffer_m: Buffer around point in meters. If >0, returns mean embedding.

    Returns:
        64-dimensional embedding vector.
    """
    point = ee.Geometry.Point([lon, lat])

    if buffer_m > 0:
        region = point.buffer(buffer_m)
        image = _get_image(year, region)
        result = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=AEF_SCALE,
            maxPixels=1e6,
        )
    else:
        image = _get_image(year, point)
        result = image.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=AEF_SCALE,
        )

    values = result.getInfo()
    embedding = np.array([values[b] for b in AEF_BANDS], dtype=np.float32)
    return embedding


def get_embeddings_for_aoi(
    bbox: tuple[float, float, float, float],
    year: int,
    scale: int = AEF_SCALE,
) -> tuple[np.ndarray, np.ndarray]:
    """Get embeddings for an AOI using sampleRectangle.

    Args:
        bbox: (west, south, east, north) in degrees.
        year: Year (2017-2025).
        scale: Resolution in meters/pixel.

    Returns:
        Tuple of (embeddings: N×64, coords: N×2 as [lon, lat]).
    """
    west, south, east, north = bbox
    region = ee.Geometry.Rectangle([west, south, east, north])
    image = _get_image(year, region, scale)

    sample = image.sampleRectangle(region=region, defaultValue=0)
    info = sample.getInfo()

    properties = info["properties"]
    bands_data = []
    for band in AEF_BANDS:
        bands_data.append(np.array(properties[band], dtype=np.float32))

    # Stack: (H, W, 64)
    data_3d = np.stack(bands_data, axis=-1)
    h, w = data_3d.shape[:2]

    # Build coordinate grid
    lons = np.linspace(west, east, w, endpoint=False) + (east - west) / w / 2
    lats = np.linspace(north, south, h, endpoint=False) + (south - north) / h / 2
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # Flatten
    embeddings = data_3d.reshape(-1, AEF_DIM)
    coords = np.stack([lon_grid.ravel(), lat_grid.ravel()], axis=-1)

    # Filter out zero vectors
    norms = np.linalg.norm(embeddings, axis=1)
    mask = norms > 1e-6
    embeddings = embeddings[mask]
    coords = coords[mask]

    return embeddings, coords


def get_embeddings_tiled(
    bbox: tuple[float, float, float, float],
    year: int,
    scale: int = AEF_SCALE,
    tile_size: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """Get embeddings for a large AOI by tiling.

    Splits the AOI into tiles small enough for sampleRectangle (~262,144 pixels).

    Args:
        bbox: (west, south, east, north) in degrees.
        year: Year (2017-2025).
        scale: Resolution in meters/pixel.
        tile_size: Max tile side in pixels.

    Returns:
        Tuple of (embeddings: N×64, coords: N×2 as [lon, lat]).
    """
    west, south, east, north = bbox

    # Approximate degrees per pixel at this latitude
    mid_lat = (south + north) / 2
    deg_per_m_lon = 1 / (111_320 * np.cos(np.radians(mid_lat)))
    deg_per_m_lat = 1 / 110_574
    tile_deg_lon = tile_size * scale * deg_per_m_lon
    tile_deg_lat = tile_size * scale * deg_per_m_lat

    # Generate tile bboxes
    lon_starts = np.arange(west, east, tile_deg_lon)
    lat_starts = np.arange(south, north, tile_deg_lat)

    all_embeddings = []
    all_coords = []
    total_tiles = len(lon_starts) * len(lat_starts)

    with tqdm(total=total_tiles, desc="Extracting tiles") as pbar:
        for lon_start in lon_starts:
            for lat_start in lat_starts:
                tile_bbox = (
                    lon_start,
                    lat_start,
                    min(lon_start + tile_deg_lon, east),
                    min(lat_start + tile_deg_lat, north),
                )
                try:
                    emb, crd = get_embeddings_for_aoi(tile_bbox, year, scale)
                    all_embeddings.append(emb)
                    all_coords.append(crd)
                except Exception as e:
                    print(f"Warning: tile {tile_bbox} failed: {e}")
                pbar.update(1)

    if not all_embeddings:
        return np.empty((0, AEF_DIM), dtype=np.float32), np.empty(
            (0, 2), dtype=np.float64
        )

    return (
        np.concatenate(all_embeddings, axis=0),
        np.concatenate(all_coords, axis=0),
    )
