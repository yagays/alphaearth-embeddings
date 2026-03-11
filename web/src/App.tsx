import { useState, useCallback, useEffect } from "react";
import MapView from "./components/MapView";
import SettingsPanel from "./components/SettingsPanel";
import ResultsPanel from "./components/ResultsPanel";
import type { SearchResult, SearchResponse, StatusResponse, TileLayerType } from "./types";

export default function App() {
  const [year, setYear] = useState(2025);
  const [k, setK] = useState(10);
  const [tileLayer, setTileLayer] = useState<TileLayerType>("osm");
  const [bbox, setBbox] = useState<[number, number, number, number] | null>(
    null
  );
  const [results, setResults] = useState<SearchResult[]>([]);
  const [queryCenter, setQueryCenter] = useState<[number, number] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightedRank, setHighlightedRank] = useState<number | null>(null);
  const [flyTo, setFlyTo] = useState<{ target: [number, number]; id: number } | null>(null);
  const [excludeQuery, setExcludeQuery] = useState(true);
  const [minDistanceKm, setMinDistanceKm] = useState(10);
  const [indexBbox, setIndexBbox] = useState<[number, number, number, number] | null>(null);
  const [cellSizeDeg, setCellSizeDeg] = useState<number | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((data: StatusResponse) => {
        setStatus(data);
        if (data.loaded && data.metadata.bbox) {
          setIndexBbox(data.metadata.bbox);
        }
        if (data.loaded && typeof data.metadata.cell_size_deg === "number") {
          setCellSizeDeg(data.metadata.cell_size_deg);
        }
      })
      .catch(() => {});
  }, []);

  const handleRectangleDrawn = useCallback(
    (west: number, south: number, east: number, north: number) => {
      setBbox([west, south, east, north]);
      setError(null);
    },
    []
  );

  const handleSearch = useCallback(async () => {
    if (!bbox) return;
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const resp = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bbox, year, k, exclude_query: excludeQuery, min_distance_km: minDistanceKm }),
      });
      if (!resp.ok) {
        const detail = await resp.json();
        throw new Error(detail.detail || `HTTP ${resp.status}`);
      }
      const data: SearchResponse = await resp.json();
      setResults(data.results);
      setQueryCenter(data.query_center);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [bbox, year, k, excludeQuery, minDistanceKm]);

  return (
    <div className="app">
      <SettingsPanel
        year={year}
        onYearChange={setYear}
        k={k}
        onKChange={setK}
        tileLayer={tileLayer}
        onTileLayerChange={setTileLayer}
        excludeQuery={excludeQuery}
        onExcludeQueryChange={setExcludeQuery}
        minDistanceKm={minDistanceKm}
        onMinDistanceKmChange={setMinDistanceKm}
        canSearch={bbox !== null && !loading}
        onSearch={handleSearch}
        loading={loading}
        error={error}
        status={status}
      />
      <MapView
        tileLayer={tileLayer}
        bbox={bbox}
        indexBbox={indexBbox}
        cellSizeDeg={cellSizeDeg}
        results={results}
        queryCenter={queryCenter}
        highlightedRank={highlightedRank}
        onRectangleDrawn={handleRectangleDrawn}
        onMarkerClick={setHighlightedRank}
        flyTo={flyTo}
      />
      <ResultsPanel
        results={results}
        loading={loading}
        highlightedRank={highlightedRank}
        onHover={setHighlightedRank}
        onClick={(lon, lat) => setFlyTo({ target: [lat, lon], id: Date.now() })}
      />
    </div>
  );
}
