export interface SearchResult {
  rank: number;
  similarity: number;
  lon: number;
  lat: number;
}

export interface SearchResponse {
  query_center: [number, number];
  results: SearchResult[];
}

export interface SearchRequest {
  bbox: [number, number, number, number]; // [west, south, east, north]
  year: number;
  k: number;
  exclude_query: boolean;
  min_distance_km: number;
}

export interface StatusResponse {
  loaded: boolean;
  ntotal: number;
  metadata: {
    bbox?: [number, number, number, number];
    [key: string]: unknown;
  };
}

export type TileLayerType = "osm" | "satellite";
