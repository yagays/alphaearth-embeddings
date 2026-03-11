import { useEffect, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { SearchResult, TileLayerType } from "../types";
import { OSM_URL, OSM_ATTR, ESRI_URL, ESRI_ATTR } from "../constants";

interface Props {
  tileLayer: TileLayerType;
  bbox: [number, number, number, number] | null;
  indexBbox: [number, number, number, number] | null;
  cellSizeDeg: number | null;
  results: SearchResult[];
  queryCenter: [number, number] | null;
  highlightedRank: number | null;
  onRectangleDrawn: (
    west: number,
    south: number,
    east: number,
    north: number
  ) => void;
  onMarkerClick: (rank: number) => void;
  flyTo: { target: [number, number]; id: number } | null;
}

/**
 * Imperative rectangle layer that updates when bbox changes.
 * Using Leaflet API directly instead of react-leaflet Rectangle
 * to avoid rendering issues.
 */
function ImperativeRectangle({
  bbox,
  options,
}: {
  bbox: [number, number, number, number] | null;
  options: L.PathOptions;
}) {
  const map = useMap();
  const layerRef = useRef<L.Rectangle | null>(null);

  useEffect(() => {
    // Remove previous
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }
    // Add new
    if (bbox) {
      const [west, south, east, north] = bbox;
      layerRef.current = L.rectangle(
        [
          [south, west],
          [north, east],
        ],
        options
      ).addTo(map);
    }
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [map, bbox, options]);

  return null;
}

function DrawRectangle({
  onRectangleDrawn,
}: {
  onRectangleDrawn: Props["onRectangleDrawn"];
}) {
  const map = useMap();
  const drawingRef = useRef(false);
  const startRef = useRef<L.LatLng | null>(null);
  const previewRef = useRef<L.Rectangle | null>(null);
  const activeRef = useRef(false);
  const btnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const DrawButton = L.Control.extend({
      onAdd() {
        const btn = L.DomUtil.create("button", "draw-rect-btn") as HTMLButtonElement;
        btn.innerHTML = "\u25a1 Draw";
        btn.title = "Draw a rectangle to search";
        btn.style.cssText =
          "background:#fff;border:2px solid rgba(0,0,0,0.2);border-radius:4px;padding:4px 10px;cursor:pointer;font-size:13px;font-weight:600;line-height:1.4;";
        btn.onclick = (e) => {
          e.stopPropagation();
          activeRef.current = !activeRef.current;
          map.getContainer().style.cursor = activeRef.current
            ? "crosshair"
            : "";
          btn.style.background = activeRef.current ? "#4a90d9" : "#fff";
          btn.style.color = activeRef.current ? "#fff" : "#000";
        };
        L.DomEvent.disableClickPropagation(btn);
        btnRef.current = btn;
        return btn;
      },
    });
    const control = new DrawButton({ position: "topleft" });
    map.addControl(control);

    const deactivate = () => {
      activeRef.current = false;
      map.getContainer().style.cursor = "";
      if (btnRef.current) {
        btnRef.current.style.background = "#fff";
        btnRef.current.style.color = "#000";
      }
    };

    const onMouseDown = (e: L.LeafletMouseEvent) => {
      if (!activeRef.current) return;
      drawingRef.current = true;
      startRef.current = e.latlng;
      map.dragging.disable();
    };

    const onMouseMove = (e: L.LeafletMouseEvent) => {
      if (!drawingRef.current || !startRef.current) return;
      const bounds = L.latLngBounds(startRef.current, e.latlng);
      if (!previewRef.current) {
        previewRef.current = L.rectangle(bounds, {
          color: "#4a90d9",
          weight: 2,
          fillOpacity: 0.15,
          dashArray: "4 4",
        }).addTo(map);
      } else {
        previewRef.current.setBounds(bounds);
      }
    };

    const onMouseUp = (e: L.LeafletMouseEvent) => {
      if (!drawingRef.current || !startRef.current) return;
      drawingRef.current = false;
      map.dragging.enable();
      const bounds = L.latLngBounds(startRef.current, e.latlng);
      if (previewRef.current) {
        map.removeLayer(previewRef.current);
        previewRef.current = null;
      }
      if (
        bounds.getNorth() !== bounds.getSouth() &&
        bounds.getEast() !== bounds.getWest()
      ) {
        onRectangleDrawn(
          bounds.getWest(),
          bounds.getSouth(),
          bounds.getEast(),
          bounds.getNorth()
        );
      }
      deactivate();
    };

    map.on("mousedown", onMouseDown);
    map.on("mousemove", onMouseMove);
    map.on("mouseup", onMouseUp);

    return () => {
      map.off("mousedown", onMouseDown);
      map.off("mousemove", onMouseMove);
      map.off("mouseup", onMouseUp);
      map.removeControl(control);
      if (previewRef.current) map.removeLayer(previewRef.current);
    };
  }, [map, onRectangleDrawn]);

  return null;
}

/** Minimum zoom level to show grid (below this it's too dense) */
const GRID_MIN_ZOOM = 11;

function CellGrid({
  indexBbox,
  cellSizeDeg,
}: {
  indexBbox: [number, number, number, number];
  cellSizeDeg: number;
}) {
  const map = useMap();
  const layerRef = useRef<L.LayerGroup | null>(null);
  const [zoom, setZoom] = useState(map.getZoom());
  const [visible, setVisible] = useState(true);
  const btnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const group = L.layerGroup();
    layerRef.current = group;
    map.addLayer(group);

    const GridButton = L.Control.extend({
      onAdd() {
        const btn = L.DomUtil.create("button", "grid-toggle-btn") as HTMLButtonElement;
        btn.innerHTML = "# Grid";
        btn.title = "Toggle cell grid";
        btn.style.cssText =
          "background:#4a90d9;color:#fff;border:2px solid rgba(0,0,0,0.2);border-radius:4px;padding:4px 10px;cursor:pointer;font-size:13px;font-weight:600;line-height:1.4;";
        btn.onclick = (e) => {
          e.stopPropagation();
          setVisible((prev) => {
            const next = !prev;
            btn.style.background = next ? "#4a90d9" : "#fff";
            btn.style.color = next ? "#fff" : "#000";
            return next;
          });
        };
        L.DomEvent.disableClickPropagation(btn);
        btnRef.current = btn;
        return btn;
      },
    });
    const control = new GridButton({ position: "topleft" });
    map.addControl(control);

    const onZoomEnd = () => setZoom(map.getZoom());
    const onMoveEnd = () => setZoom(map.getZoom());
    map.on("zoomend", onZoomEnd);
    map.on("moveend", onMoveEnd);

    return () => {
      map.off("zoomend", onZoomEnd);
      map.off("moveend", onMoveEnd);
      map.removeControl(control);
      map.removeLayer(group);
    };
  }, [map]);

  useEffect(() => {
    const group = layerRef.current;
    if (!group) return;
    group.clearLayers();

    if (!visible || zoom < GRID_MIN_ZOOM) return;

    const [west, south, east, north] = indexBbox;
    const mapBounds = map.getBounds();

    // Clip to visible area intersected with index bbox
    const visWest = Math.max(west, mapBounds.getWest());
    const visSouth = Math.max(south, mapBounds.getSouth());
    const visEast = Math.min(east, mapBounds.getEast());
    const visNorth = Math.min(north, mapBounds.getNorth());

    if (visWest >= visEast || visSouth >= visNorth) return;

    // Snap to grid
    const startLon = Math.floor(visWest / cellSizeDeg) * cellSizeDeg;
    const startLat = Math.floor(visSouth / cellSizeDeg) * cellSizeDeg;

    const style: L.PolylineOptions = {
      color: "#666",
      weight: 1,
      opacity: 0.7,
    };

    // Vertical lines
    for (let lon = startLon; lon <= visEast; lon += cellSizeDeg) {
      if (lon < west) continue;
      group.addLayer(
        L.polyline(
          [
            [visSouth, lon],
            [visNorth, lon],
          ],
          style
        )
      );
    }

    // Horizontal lines
    for (let lat = startLat; lat <= visNorth; lat += cellSizeDeg) {
      if (lat < south) continue;
      group.addLayer(
        L.polyline(
          [
            [lat, visWest],
            [lat, visEast],
          ],
          style
        )
      );
    }
  }, [map, zoom, visible, indexBbox, cellSizeDeg]);

  return null;
}

function FitToIndex({
  indexBbox,
}: {
  indexBbox: [number, number, number, number] | null;
}) {
  const map = useMap();
  const fittedRef = useRef(false);

  useEffect(() => {
    if (indexBbox && !fittedRef.current) {
      const [west, south, east, north] = indexBbox;
      map.fitBounds(
        [
          [south, west],
          [north, east],
        ],
        { padding: [30, 30] }
      );
      fittedRef.current = true;
    }
  }, [map, indexBbox]);

  return null;
}

function FlyToPoint({ target }: { target: [number, number] }) {
  const map = useMap();

  useEffect(() => {
    map.flyTo(target, Math.max(map.getZoom(), 13), { duration: 0.8 });
  }, [map, target]);

  return null;
}

function TileLayerSwitcher({ tileLayer }: { tileLayer: TileLayerType }) {
  const url = tileLayer === "satellite" ? ESRI_URL : OSM_URL;
  const attr = tileLayer === "satellite" ? ESRI_ATTR : OSM_ATTR;
  return <TileLayer key={tileLayer} url={url} attribution={attr} />;
}

// Stable style objects (avoid re-creating on every render)
const INDEX_BBOX_STYLE: L.PathOptions = {
  color: "#4ecdc4",
  weight: 2,
  dashArray: "8 4",
  fillOpacity: 0.05,
};

const QUERY_BBOX_STYLE: L.PathOptions = {
  color: "#4a90d9",
  weight: 2,
  fillOpacity: 0.15,
};

export default function MapView({
  tileLayer,
  bbox,
  indexBbox,
  cellSizeDeg,
  results,
  queryCenter,
  highlightedRank,
  onRectangleDrawn,
  onMarkerClick,
  flyTo,
}: Props) {
  const center: [number, number] = [38.0, 140.0];

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={6}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayerSwitcher tileLayer={tileLayer} />
        <DrawRectangle onRectangleDrawn={onRectangleDrawn} />
        <FitToIndex indexBbox={indexBbox} />
        {flyTo && <FlyToPoint key={flyTo.id} target={flyTo.target} />}

        {/* Cell grid (visible at high zoom) */}
        {indexBbox && cellSizeDeg && (
          <CellGrid indexBbox={indexBbox} cellSizeDeg={cellSizeDeg} />
        )}

        {/* Index coverage area (turquoise dashed) */}
        <ImperativeRectangle bbox={indexBbox} options={INDEX_BBOX_STYLE} />

        {/* Query bbox (blue solid) */}
        <ImperativeRectangle bbox={bbox} options={QUERY_BBOX_STYLE} />

        {/* Query center */}
        {queryCenter && (
          <CircleMarker
            center={[queryCenter[1], queryCenter[0]]}
            radius={8}
            pathOptions={{
              color: "#4a90d9",
              fillColor: "#4a90d9",
              fillOpacity: 0.8,
            }}
          >
            <Popup>Query Center</Popup>
          </CircleMarker>
        )}

        {/* Result markers */}
        {results.map((r) => (
          <CircleMarker
            key={r.rank}
            center={[r.lat, r.lon]}
            radius={highlightedRank === r.rank ? 10 : 7}
            pathOptions={{
              color: highlightedRank === r.rank ? "#ffcc00" : "#e94560",
              fillColor: highlightedRank === r.rank ? "#ffcc00" : "#e94560",
              fillOpacity: 0.8,
              weight: highlightedRank === r.rank ? 3 : 2,
            }}
            eventHandlers={{
              click: () => onMarkerClick(r.rank),
            }}
          >
            <Popup>
              #{r.rank} — Similarity: {r.similarity.toFixed(3)}
              <br />({r.lon.toFixed(4)}, {r.lat.toFixed(4)})
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
