import os
import json
import uuid
import time
from typing import Any, Dict, List, Tuple, Optional
from functools import lru_cache
import threading

import geopandas as gpd
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from shapely.geometry import LineString, shape
from dotenv import load_dotenv


class LatLng(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class OptimizeRouteRequest(BaseModel):
    start: LatLng
    end: LatLng


def load_flood_zones() -> gpd.GeoDataFrame:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(script_dir, "flood_prone.geojson")
    gdf = gpd.read_file(geojson_path)
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    else:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


def query_ors_route(start: Tuple[float, float], end: Tuple[float, float], api_key: str) -> Dict[str, Any]:
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    payload = {
        "coordinates": [
            [start[0], start[1]],
            [end[0], end[1]],
        ]
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }


    max_conc = int(os.getenv("ORS_MAX_CONCURRENCY", "1") or "1")
    if not hasattr(query_ors_route, "_sem"):
        query_ors_route._sem = threading.Semaphore(max_conc)

    with query_ors_route._sem:
        last_resp = None
        for attempt in range(5):
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            last_resp = resp
            if resp.status_code == 200:
                break
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = min(4.0, 0.4 * (2 ** attempt))
                time.sleep(wait)
                continue
            raise HTTPException(status_code=502, detail=f"ORS error {resp.status_code}: {resp.text[:200]}")

    if last_resp is None or last_resp.status_code != 200:
        code = getattr(last_resp, "status_code", "?")
        text = getattr(last_resp, "text", "")
        raise HTTPException(status_code=502, detail=f"ORS error {code}: {text[:200]}")

    data = last_resp.json()

    # ORS returns a FeatureCollection
    features = (data.get("features") or []) if isinstance(data, dict) else []
    if not features:
        raise HTTPException(status_code=404, detail="ORS returned no route features")

    feature = features[0]
    geometry = feature.get("geometry") or {}
    props = feature.get("properties") or {}
    summary = (props.get("summary") or {}) if isinstance(props, dict) else {}
    distance_m = float(summary.get("distance") or 0.0)
    duration_s = float(summary.get("duration") or 0.0)

    if distance_m <= 0 or duration_s <= 0:
        raise HTTPException(status_code=404, detail="ORS returned non-positive distance or duration")

    return {
        "distance": distance_m,  # meters
        "duration": duration_s,  # seconds
        "geometry": geometry,    # GeoJSON LineString
    }


def _round_coord(value: float, decimals: int = 5) -> float:
    return float(f"{value:.{decimals}f}")


@lru_cache(maxsize=256)
def get_route_cached(
    start_lng: float,
    start_lat: float,
    end_lng: float,
    end_lat: float,
    api_key: str,
) -> Dict[str, Any]:
    # Round to reduce cache fragmentation
    start = (_round_coord(start_lng), _round_coord(start_lat))
    end = (_round_coord(end_lng), _round_coord(end_lat))
    return query_ors_route(start, end, api_key)


def compute_risk(
    route_coords: List[List[float]], flood_gdf: gpd.GeoDataFrame
) -> Tuple[float, int]:
    line = LineString(route_coords)
    total_km = line.length * 111.32  # rough conversion deg->km at low latitudes

    intersections = 0
    base_score = 0.0

    for _, row in flood_gdf.iterrows():
        polygon = row.geometry
        if polygon is None or polygon.is_empty:
            continue
        if not line.intersects(polygon):
            continue
        intersections += 1
        inter = line.intersection(polygon)
        inter_len_deg = 0.0
        if inter.is_empty:
            continue
        if inter.geom_type == "LineString":
            inter_len_deg = inter.length
        elif inter.geom_type == "MultiLineString":
            inter_len_deg = sum(seg.length for seg in inter.geoms)
        else:
            inter_len_deg = 0.0

        inter_len_km = inter_len_deg * 111.32
        risk_multiplier = 1.0
        if "risk" in row and isinstance(row["risk"], (int, float)):
            # Optional attribute if available
            risk_multiplier = max(0.5, float(row["risk"]))

        base_score += inter_len_km * risk_multiplier

    if total_km <= 0:
        return 0.0, intersections

    final_score = (base_score / total_km) * 10.0
    return float(final_score), intersections


app = FastAPI(title="Bataan Smart Route Optimizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
_FLOOD_GDF = load_flood_zones()
_HAS_ORS = bool(os.getenv("ORS_API_KEY"))


@app.get("/flood-zones")
def get_flood_zones() -> Dict[str, Any]:
    return json.loads(_FLOOD_GDF.to_json())


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "provider": "openrouteservice",
        "ors_key_present": _HAS_ORS,
    }


@app.post("/optimize-route")
def optimize_route(req: OptimizeRouteRequest) -> Dict[str, Any]:
    start = (req.start.lng, req.start.lat)
    end = (req.end.lng, req.end.lat)

    ors_api_key: Optional[str] = os.getenv("ORS_API_KEY")
    if not ors_api_key:
        raise HTTPException(status_code=500, detail="ORS_API_KEY not configured")
    # Use cached routing to reduce provider calls
    route = get_route_cached(start[0], start[1], end[0], end[1], ors_api_key)
    geometry = route.get("geometry", {})
    coords = geometry.get("coordinates") or []
    distance_km = float((route.get("distance") or 0) / 1000.0)
    duration_min = float((route.get("duration") or 0) / 60.0)

    if not coords:
        raise HTTPException(status_code=500, detail="OSRM returned no geometry coordinates")

    risk_score, intersections = compute_risk(coords, _FLOOD_GDF)

    warnings: List[str] = []
    if intersections > 0:
        warnings.append(f"Route passes through {intersections} flood-prone areas")

    return {
        "route_id": str(uuid.uuid4()),
        "geometry": coords,
        "risk_score": round(risk_score, 2),
        "flood_intersections": intersections,
        "distance_km": round(distance_km, 2),
        "estimated_time_minutes": round(duration_min),
        "warnings": warnings,
        "alternative_available": False
    }


# Local run: uvicorn app:app --reload

