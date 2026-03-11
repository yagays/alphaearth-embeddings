"""Constants and path definitions for AlphaEarth Foundations embeddings."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
INDEX_DIR = DATA_DIR / "index"

# Ensure directories exist
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# AEF dataset constants
AEF_COLLECTION = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
AEF_BANDS = [f"A{i:02d}" for i in range(64)]
AEF_DIM = 64
AEF_SCALE = 10  # meters/pixel

# Example AOIs: (name, lon, lat)
EXAMPLE_AOIS = {
    "hokkaido_farmland": {"lon": 143.2, "lat": 43.3, "description": "北海道農地"},
    "tokyo_center": {"lon": 139.77, "lat": 35.68, "description": "東京都心"},
    "osaka_center": {"lon": 135.50, "lat": 34.69, "description": "大阪都心"},
    "mt_fuji": {"lon": 138.73, "lat": 35.36, "description": "富士山"},
    "kyoto": {"lon": 135.77, "lat": 35.01, "description": "京都"},
}
