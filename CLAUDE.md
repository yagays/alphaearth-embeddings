# CLAUDE.md

## Project Overview

AlphaEarth Foundations Satellite Embeddings (AEF) を使った FAISS kNN 類似度検索ツール + Web UI。ブログ記事執筆のための検証基盤。

## Tech Stack

- **Python**: uv, hatchling, Earth Engine API, FAISS, FastAPI
- **Frontend**: React 19, Vite, TypeScript, react-leaflet, leaflet-draw
- **Data**: Google Earth Engine (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`)

## Project Structure

- `src/aef/` - Python パッケージ (config, ee_client, faiss_index, similarity, api)
- `scripts/build_index.py` - FAISS インデックス構築スクリプト
- `notebooks/` - Jupyter ノートブック (01: 抽出, 02: 検索)
- `web/` - React フロントエンド
- `data/` - gitignore 対象。embeddings/ と index/ を含む

## Commands

```bash
# Python 環境
uv sync

# インデックス構築 (EE 認証必要)
uv run python scripts/build_index.py

# バックエンド起動
uv run uvicorn aef.api:app --reload

# フロントエンド起動
cd web && npm run dev

# フロントエンドビルド
cd web && npx vite build

# TypeScript 型チェック
cd web && npx tsc --noEmit

# ノートブック起動
uv run --group notebook jupyter lab
```

## Architecture Decisions

### EE データ抽出の注意点

- AEF コレクションはタイル化 ImageCollection (97,155 images)。単純な `.first()` ではなく `filterBounds(region).mosaic()` が必要。
- `sampleRectangle` を使うには `setDefaultProjection(crs='EPSG:4326', scale=scale)` を mosaic 後に呼ぶこと。省略すると 1x1 pixel になる。
- `sampleRectangle` 上限: 262,144 pixels/request。大きな AOI はタイル分割で対応 (`get_embeddings_tiled`)。

### インデックス構築の粒度

- 10m 生ピクセルは Web UI 検索には密すぎる
- 100m/pixel で EE から抽出 → 0.01 度 (~1km) グリッドセルに平均化 → 再正規化 → FAISS インデックス
- 現在のインデックス: 北海道 1x0.5 度、5,000 セル
- 日本全域に拡張する場合: ~378,000 セル、~100MB、抽出に ~4時間の見込み

### FAISS

- `IndexFlatIP(64)` を使用。内積 = コサイン類似度 (単位ベクトル前提)
- 64次元 × 数十万セルなら flat で十分。近似インデックスは不要。

### Web API 検索フロー

1. フロントが bbox を POST
2. バックエンドが bbox 内のインデックス済みセルの embedding を平均化
3. 平均 embedding を再正規化
4. FAISS で kNN 検索
5. Top-k 結果を返却

## Conventions

- Commit messages: English, Conventional Commits
- Python: type hints, numpy docstring style
- Frontend: functional components, TypeScript strict
