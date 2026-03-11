# AlphaEarth Embeddings - FAISS kNN Search + Web UI

Google DeepMind の [AlphaEarth Foundations Satellite Embeddings](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL) を使った類似度検索ツール。全球の衛星画像を64次元ベクトルで表現したこのデータセットに対して、FAISS による kNN 類似度検索を行い、インタラクティブな Web UI で体験できる。

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

### 1. インデックス構築

Earth Engine からデータを抽出し、FAISS インデックスを構築する。

```bash
uv run python scripts/build_index.py
```

デフォルトでは北海道の 1x0.5 度領域 (142.5-143.5E, 43.0-43.5N) を 100m/pixel で抽出し、1km グリッドに集約して `data/index/default.*` に保存する。対象領域やパラメータは `scripts/build_index.py` の定数を編集して変更できる。

### 2. Web UI 起動

ターミナルを2つ開き、それぞれ実行する。

**バックエンド (port 8000):**

```bash
uv run uvicorn aef.api:app --reload
```

**フロントエンド (port 5173):**

```bash
cd web
npm run dev
```

ブラウザで http://localhost:5173 を開く。

### 3. ノートブック

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
│   └── build_index.py            # FAISS インデックス構築スクリプト
├── src/aef/
│   ├── config.py                 # 定数・パス定義
│   ├── ee_client.py              # Earth Engine embedding 抽出
│   ├── faiss_index.py            # FAISS インデックス (IndexFlatIP)
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
    ├── embeddings/               # 抽出済み npz
    └── index/                    # FAISS インデックス (.faiss, .coords.npy, .meta.json)
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
