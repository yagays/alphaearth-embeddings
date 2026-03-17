# AlphaEarth Embeddings - FAISS kNN Search + Web UI

Google DeepMind の [AlphaEarth Foundations Satellite Embeddings](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL) を使った類似度検索ツール。全球の衛星画像を64次元ベクトルで表現したこのデータセットに対して、FAISS による kNN 類似度検索を行い、インタラクティブな Web UI で体験できる。

**ブログ記事**: [AlphaEarth Embeddings で衛星画像の構造検索](https://yag.xyz/post/alphaearth-embedding-structure-search/)

## AEF データ仕様

| 項目 | 値 |
|---|---|
| Dataset ID | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` |
| 解像度 | 10m/pixel |
| 次元数 | 64 (bands A00-A63) |
| ベクトル性質 | 単位長ベクトル（内積 = コサイン類似度） |
| 年次データ | 2017-2025 |
| アクセス | Earth Engine API (無料) / GCS COG (requester-pays) |

## セットアップ

### Python 環境

```bash
uv sync
```

### Earth Engine 認証

```bash
uv run earthengine authenticate
```

### Web フロントエンド

```bash
cd web
npm install
```

## 使い方

### 1. データダウンロード

Earth Engine からタイルごとに embedding をダウンロードする。タイルごとにディスクに保存するため、途中中断しても再開できる。

```bash
# 北海道全域 (デフォルト)
uv run python scripts/download_embeddings.py

# カスタム bbox
uv run python scripts/download_embeddings.py --bbox 143.0 43.0 143.5 43.5 --name test

# 途中中断 → 再実行で自動レジューム (既存タイルをスキップ)
uv run python scripts/download_embeddings.py --bbox 143.0 43.0 143.5 43.5 --name test
```

出力: `data/embeddings/{name}_{year}_embeddings.npy`, `*_coords.npy`, `*_meta.json`

### 2. インデックス構築

ダウンロード済みデータから FAISS インデックスを構築する。

```bash
# Exact (FlatIP) インデックス構築
uv run python scripts/build_index.py --name hokkaido_2025

# グリッド集約付き (1km セル)
uv run python scripts/build_index.py --name hokkaido_2025 --cell-size 0.01
```

#### 大規模 ANN インデックス (200M+ vectors)

Global 規模では `IndexFlatIP` がメモリ不足になるため、ANN インデックスを使う。

```bash
# ベンチマーク (北海道データで ANN 候補を評価)
uv run python scripts/benchmark_ann.py

# ANN インデックス構築 (省メモリ chunked pipeline)
uv run python scripts/build_ann_index.py \
    --name hokkaido_2025 \
    --index-type "IVF4096_HNSW32,SQ8" \
    --nprobe-default 128
```

構築パイプラインは mmap + チャンク処理で、200M vectors でもピークメモリ <64GB で動作する。

### 3. Web UI 起動

ターミナルを2つ開き、それぞれ実行する。

**バックエンド (port 8000):**

```bash
uv run uvicorn aef.api:app --reload

# ANN インデックスを使う場合
AEF_INDEX_NAME=hokkaido_ivf4096_sq8 uv run uvicorn aef.api:app --reload
```

**フロントエンド (port 5173):**

```bash
cd web
npm run dev
```

ブラウザで http://localhost:5173 を開く。

### 4. ノートブック

```bash
uv run --group notebook jupyter lab
```

| ノートブック | 内容 |
|---|---|
| `01_extract_embeddings.ipynb` | EE 認証 → AOI の embedding 抽出 → npz 保存 → 基本統計 |
| `02_similarity_search.ipynb` | npz → FAISS インデックス構築 → kNN 検索 → matplotlib/folium 可視化 |

## プロジェクト構造

```
alphaearth_embeddings/
├── pyproject.toml
├── scripts/
│   ├── download_embeddings.py    # EE からタイルごとにダウンロード + マージ
│   ├── build_index.py            # .npy から FAISS FlatIP インデックス構築
│   ├── build_ann_index.py        # ANN インデックス構築 (省メモリ chunked pipeline)
│   ├── benchmark_ann.py          # FAISS ANN 候補ベンチマーク
│   └── benchmark_external.py    # 外部ライブラリ (USearch, LanceDB) ベンチマーク
├── src/aef/
│   ├── config.py                 # 定数・パス定義・リージョン定義
│   ├── ee_client.py              # Earth Engine embedding 抽出
│   ├── faiss_index.py            # FAISS インデックス (FlatIP / ANN 両対応)
│   ├── similarity.py             # 検索ワークフロー・類似度マップ
│   └── api.py                    # FastAPI バックエンド
├── notebooks/
│   ├── 01_extract_embeddings.ipynb
│   └── 02_similarity_search.ipynb
├── web/                          # React + Vite フロントエンド
│   └── src/
│       ├── App.tsx               # 3ペインレイアウト
│       └── components/
│           ├── MapView.tsx       # Leaflet 地図 + 矩形描画
│           ├── SettingsPanel.tsx  # 年次・k・タイルレイヤー設定
│           └── ResultsPanel.tsx  # Top-k 結果 + ミニマップ
└── data/                         # .gitignore 対象
    ├── embeddings/               # 抽出済み npz / npy
    ├── index/                    # FAISS インデックス (.faiss, .coords.npy, .meta.json, .embeddings.npy)
    └── benchmark/                # ベンチマーク結果 (JSON, TSV)
```

## API エンドポイント

| Method | Path | 説明 |
|---|---|---|
| GET | `/api/status` | ロード済みインデックスの情報 |
| POST | `/api/search` | 類似度検索 (`{ bbox, year, k }`) |
| GET | `/api/embedding` | 指定地点の embedding ベクトル取得 |

## 技術メモ

- **AEF コレクションはタイル化されている**: `filterBounds()` + `mosaic()` で空間フィルタ必須
- **`sampleRectangle` のスケール問題**: mosaic のデフォルト projection が粗いため、`setDefaultProjection(crs, scale)` を明示的に設定する必要がある
- **`sampleRectangle` の上限**: 1リクエストあたり 262,144 ピクセル → 大きな AOI はタイル分割が必要
- **100m 抽出は EE 側のリサンプリング**: 10m ネイティブ embedding を EE 側で平均化して返す。元の単位ベクトル性質が崩れるため集約後に再正規化している
- **FAISS `IndexFlatIP`**: 単位ベクトルの内積 = コサイン類似度。64次元・数万〜数十万セルなら flat で十分高速
- **ANN インデックス**: 200M+ vectors では `IVF+SQ8` や `IVF+SQfp16` を使う。量子化による reconstruct の精度低下は `.embeddings.npy` (mmap) で補完
- **省メモリ構築**: mmap + チャンク正規化 → サンプル学習 → チャンク追加の3フェーズで、ピークメモリをインデックス本体サイズ + ~500MB に抑える
