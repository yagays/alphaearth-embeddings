import { useRef, useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { SearchResult } from "../types";
import { ESRI_URL, ESRI_ATTR } from "../constants";

interface Props {
  results: SearchResult[];
  loading: boolean;
  highlightedRank: number | null;
  onHover: (rank: number | null) => void;
  onClick: (lon: number, lat: number) => void;
}

function MiniMap({ result }: { result: SearchResult }) {
  return (
    <div className="mini-map">
      <MapContainer
        center={[result.lat, result.lon]}
        zoom={14}
        zoomControl={false}
        attributionControl={false}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer url={ESRI_URL} attribution={ESRI_ATTR} />
        <CircleMarker
          center={[result.lat, result.lon]}
          radius={5}
          pathOptions={{ color: "#e94560", fillColor: "#e94560", fillOpacity: 0.8 }}
        />
      </MapContainer>
    </div>
  );
}

export default function ResultsPanel({
  results,
  loading,
  highlightedRank,
  onHover,
  onClick,
}: Props) {
  const listRef = useRef<HTMLDivElement>(null);

  // Scroll to highlighted card
  useEffect(() => {
    if (highlightedRank !== null && listRef.current) {
      const card = listRef.current.querySelector(
        `[data-rank="${highlightedRank}"]`
      );
      card?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlightedRank]);

  return (
    <div className="results-panel">
      <h2>Results {results.length > 0 && `(${results.length})`}</h2>

      {loading && <div className="loading">Searching</div>}

      {!loading && results.length === 0 && (
        <div className="no-results">
          Draw a rectangle on the map and click Search to find similar regions.
        </div>
      )}

      <div className="results-list" ref={listRef}>
        {results.map((r) => (
          <div
            key={r.rank}
            data-rank={r.rank}
            className={`result-card ${highlightedRank === r.rank ? "highlighted" : ""}`}
            onMouseEnter={() => onHover(r.rank)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onClick(r.lon, r.lat)}
            style={{ cursor: "pointer" }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
              }}
            >
              <span className="rank">#{r.rank}</span>
              <span className="similarity">{r.similarity.toFixed(4)}</span>
            </div>
            <div className="coords">
              {r.lon.toFixed(4)}, {r.lat.toFixed(4)}
            </div>
            <MiniMap result={r} />
          </div>
        ))}
      </div>
    </div>
  );
}
