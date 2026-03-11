import type { TileLayerType, StatusResponse } from "../types";

interface Props {
  year: number;
  onYearChange: (y: number) => void;
  k: number;
  onKChange: (k: number) => void;
  tileLayer: TileLayerType;
  onTileLayerChange: (t: TileLayerType) => void;
  excludeQuery: boolean;
  onExcludeQueryChange: (v: boolean) => void;
  minDistanceKm: number;
  onMinDistanceKmChange: (v: number) => void;
  canSearch: boolean;
  onSearch: () => void;
  loading: boolean;
  error: string | null;
  status: StatusResponse | null;
}

const YEARS = Array.from({ length: 9 }, (_, i) => 2017 + i);

export default function SettingsPanel({
  year,
  onYearChange,
  k,
  onKChange,
  tileLayer,
  onTileLayerChange,
  excludeQuery,
  onExcludeQueryChange,
  minDistanceKm,
  onMinDistanceKmChange,
  canSearch,
  onSearch,
  loading,
  error,
  status,
}: Props) {
  return (
    <div className="settings-panel">
      <div>
        <h2>AEF Search</h2>
        <p style={{ fontSize: "0.8rem", color: "#a0a0b0", marginTop: 4 }}>
          AlphaEarth Satellite Embeddings
        </p>
      </div>

      <div>
        <label>Index Status</label>
        {status ? (
          <div className={`status ${status.loaded ? "loaded" : "error"}`}>
            {status.loaded
              ? `Loaded: ${status.ntotal.toLocaleString()} vectors`
              : "No index loaded"}
          </div>
        ) : (
          <div className="status error">Backend unavailable</div>
        )}
      </div>

      <div>
        <label htmlFor="year">Year</label>
        <select
          id="year"
          value={year}
          onChange={(e) => onYearChange(Number(e.target.value))}
        >
          {YEARS.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="k">
          Results (k) <span className="value-display">{k}</span>
        </label>
        <input
          id="k"
          type="range"
          min={1}
          max={50}
          value={k}
          onChange={(e) => onKChange(Number(e.target.value))}
        />
      </div>

      <div>
        <label htmlFor="tile-layer">Tile Layer</label>
        <select
          id="tile-layer"
          value={tileLayer}
          onChange={(e) => onTileLayerChange(e.target.value as TileLayerType)}
        >
          <option value="osm">OpenStreetMap</option>
          <option value="satellite">Satellite (Esri)</option>
        </select>
      </div>

      <div>
        <label
          htmlFor="exclude-query"
          style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}
        >
          <input
            id="exclude-query"
            type="checkbox"
            checked={excludeQuery}
            onChange={(e) => onExcludeQueryChange(e.target.checked)}
            style={{ margin: 0 }}
          />
          Exclude query area
        </label>
      </div>

      <div>
        <label htmlFor="min-distance">
          Min distance <span className="value-display">{minDistanceKm} km</span>
        </label>
        <input
          id="min-distance"
          type="range"
          min={0}
          max={100}
          step={1}
          value={minDistanceKm}
          onChange={(e) => onMinDistanceKmChange(Number(e.target.value))}
        />
      </div>

      <button disabled={!canSearch} onClick={onSearch}>
        {loading ? "Searching..." : "Search"}
      </button>

      {error && <div className="status error">{error}</div>}

      <div style={{ fontSize: "0.75rem", color: "#666", marginTop: "auto" }}>
        Draw a rectangle on the map to define the query area, then click Search.
      </div>
    </div>
  );
}
