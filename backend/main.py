# main.py - API between the real ocean data and the dashboard.
# Run with:  uvicorn main:app --reload
# It now provides everything page.tsx asks for:
#   GET  /api/ocean-metrics      -> zones + best_zone + data_source
#   GET  /api/market-catches     -> sample marketplace rows
#   POST /api/broadcast-advisory -> SMS (or an honest "demo_mode" reply)

import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ocean_data import get_real_zones

app = FastAPI(title="AquaPredict Pro API")

# CORS: lets the dashboard (port 3000) call this API (port 8000).
app.add_middleware(
    CORSMiddleware,
       allow_origins=[
       "http://localhost:3000",
       "http://127.0.0.1:3000",
       "https://aquapredict-pro.vercel.app",
   ],
)

# ---- Cache: remember the last slow download for 6 hours ----
CACHE_HOURS = 6
cache = {"zones": None, "fetched_at": 0.0, "source": "none"}

SAMPLE_ZONES = [
    {"sector": "Sample Alpha", "lat": 4.25, "lon": 5.10, "sst": 24.5,
     "chlorophyll": 3.5, "yield_index": 0.92, "status": "High Yield"},
    {"sector": "Sample Beta", "lat": 4.50, "lon": 5.30, "sst": 26.2,
     "chlorophyll": 1.2, "yield_index": 0.61, "status": "Moderate"},
]

def first_of(zone, names, default):
    """Return the first field found under any of these names.
    WHY: we don't want one differently-named field to break the page."""
    for n in names:
        if n in zone and zone[n] is not None:
            return zone[n]
    return default

def tidy(raw):
    """Turn whatever get_real_zones() returned into the exact list of
    dictionaries the dashboard expects. This is the part that fixes the crash."""
    # A pandas table -> list of dictionaries
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict(orient="records")
    # A dictionary wrapping the list -> pull the list out
    if isinstance(raw, dict):
        raw = first_of(raw, ["zones", "data", "results"], [])
    zones = []
    for i, z in enumerate(raw):
        # If your real field names differ, add them to these lists:
        score = float(first_of(z, ["yield_index", "score", "total_score"], 0))
        zones.append({
            "sector": str(first_of(z, ["sector", "name", "zone"], f"Zone {i + 1}")),
            "lat": float(first_of(z, ["lat", "latitude"], 0)),
            "lon": float(first_of(z, ["lon", "longitude", "lng"], 0)),
            "sst": round(float(first_of(z, ["sst", "temp", "temperature", "temp_c"], 0)), 1),
            "chlorophyll": round(float(first_of(z, ["chlorophyll", "chl"], 0)), 2),
            "yield_index": round(score, 2),
            # If there is no status field, rate by score (0.7+ = High Yield)
            "status": first_of(z, ["status"], "High Yield" if score >= 0.7 else "Moderate"),
        })
    return zones

def load_zones():
    age = time.time() - cache["fetched_at"]
    if cache["zones"] is not None and age < CACHE_HOURS * 3600:
        return cache["zones"], cache["source"]
    try:
        zones = tidy(get_real_zones())          # slow real Copernicus call
        cache.update(zones=zones, fetched_at=time.time(), source="Copernicus (live)")
    except Exception as error:
        print("Copernicus fetch failed:", error)
        if cache["zones"] is None:
            return SAMPLE_ZONES, "Sample data (Copernicus unavailable)"
    return cache["zones"], cache["source"]

@app.get("/api/ocean-metrics")
def ocean_metrics():
    zones, source = load_zones()
    best = max(zones, key=lambda z: z["yield_index"]) if zones else None
    return {"status": "success", "data_source": source,
            "best_zone": best, "data": zones}

# ---- Marketplace: still sample data (labelled as such on the page) ----
@app.get("/api/market-catches")
def market_catches():
    return {"catches": [
        {"bmu": "Epe Jetty Unit A", "composition": "Red Snapper, Croaker",
         "volume_kg": 450, "status": "Reserved"},
        {"bmu": "Badagry Coastal Outpost", "composition": "Pelagic Mix",
         "volume_kg": 1200, "status": "Available"},
    ]}

# ---- SMS: honest about whether anything was really sent ----
class Broadcast(BaseModel):
    zone: str
    message: str
    phone_numbers: list[str]

@app.post("/api/broadcast-advisory")
def broadcast(req: Broadcast):
    key = os.getenv("AT_API_KEY")
    if not key:
        # No SMS account connected yet: say so, never pretend.
        return {"status": "demo_mode",
                "message": f"No SMS gateway connected. Nothing sent to {len(req.phone_numbers)} number(s)."}
    try:
        import africastalking
        africastalking.initialize(os.getenv("AT_USERNAME", "sandbox"), key)
        africastalking.SMS.send(req.message, req.phone_numbers)
        return {"status": "sent", "message": f"Handed to gateway for {len(req.phone_numbers)} number(s)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}