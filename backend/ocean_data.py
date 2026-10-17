# ocean_data.py
# PURPOSE: Download REAL ocean data from Copernicus and turn it into fishing zones.
# This replaces the invented sample numbers in scoring.py.
#
# THE IDEA (why the old temperature band was dropped):
# Real water here is 27-30 C, so a fixed "ideal band" can't tell places apart.
# Instead we look for what stands out compared with the surroundings:
#   1. FRONTS: where warm and cooler water meet (temperature changes quickly
#      between neighbouring points). Mixing there feeds plankton, and fish follow.
#   2. COOL POCKETS: water cooler than the area average can mean nutrient-rich
#      water rising from below ("upwelling").
#   3. CHLOROPHYLL: a measure of plankton, the base of the food chain.
# These are common ideas in fisheries science, but the weights below are
# STARTING ASSUMPTIONS. Describe this honestly as a rule-based model that will be
# calibrated with local catch data during the pilot.

import os
from datetime import datetime, timedelta

import numpy as np
import xarray as xr
import copernicusmarine

# --- SETTINGS: all in one place so they are easy to change -------------------
TEMP_DATASET = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"   # sea temperature
CHL_DATASET = "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m"        # chlorophyll (plankton)

LAT_MIN, LAT_MAX = 4.0, 6.5     # the box we study: Nigerian coast / Gulf of Guinea
LON_MIN, LON_MAX = 3.0, 8.5

# Folder for downloaded files. Built from this file's own location so it is the
# same folder no matter where you start the server from.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _is_fresh(path):
    """True if the file exists AND was downloaded today.
    WHY: the data updates once a day, so downloading again within the same day
    would only waste time. This is called 'caching'."""
    if not os.path.exists(path):
        return False
    return datetime.fromtimestamp(os.path.getmtime(path)).date() == datetime.now().date()


def _download(dataset_id, variable, filename):
    """Download a small box of data for the last few days, unless we already have today's."""
    path = os.path.join(DATA_DIR, filename)
    if _is_fresh(path):
        return path

    today = datetime.now()
    copernicusmarine.subset(
        dataset_id=dataset_id,
        variables=[variable],
        minimum_longitude=LON_MIN, maximum_longitude=LON_MAX,
        minimum_latitude=LAT_MIN, maximum_latitude=LAT_MAX,
        minimum_depth=0, maximum_depth=1,           # surface layer only
        start_datetime=(today - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00"),
        end_datetime=today.strftime("%Y-%m-%dT00:00:00"),
        output_directory=DATA_DIR,
        output_filename=filename,
        overwrite=True,
    )
    return path


def _latest_surface(path, variable):
    """Open a downloaded file and return a 2D grid (latitude x longitude) for the
    most recent day at the surface."""
    # 'with' closes the file when finished; .load() copies the numbers into memory.
    # WHY: on Windows an open file can't be replaced by tomorrow's download.
    with xr.open_dataset(path) as ds:
        grid = ds[variable].load()
    if "time" in grid.dims:
        grid = grid.isel(time=-1)       # -1 means "the last one" = most recent day
    if "depth" in grid.dims:
        grid = grid.isel(depth=0)       # first depth = the surface
    return grid


def _scale01(values):
    """Rescale numbers to 0-1, where 0 = among the lowest and 1 = among the highest.
    We use the 5th and 95th percentiles so a single extreme point can't squash
    everything else. NaN (land) stays NaN."""
    low, high = np.nanpercentile(values, [5, 95])
    if high - low == 0:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0, 1)


def get_real_zones(max_zones=6, min_gap_deg=0.5):
    """Main function: returns the best fishing zones from today's real data."""
    temp_path = _download(TEMP_DATASET, "thetao", "temperature.nc")
    chl_path = _download(CHL_DATASET, "chl", "chlorophyll.nc")

    sst_grid = _latest_surface(temp_path, "thetao")
    chl_grid = _latest_surface(chl_path, "chl")

    # The two datasets use different grid sizes (9 km vs 28 km). For every
    # temperature point we pick the nearest chlorophyll value so both line up.
    chl_grid = chl_grid.sel(latitude=sst_grid.latitude, longitude=sst_grid.longitude,
                            method="nearest")

    sst = sst_grid.values.astype(float)     # temperature table; land = NaN (no value)
    chl = chl_grid.values.astype(float)
    lats = sst_grid.latitude.values
    lons = sst_grid.longitude.values
    water = ~np.isnan(sst)                  # True where there is sea

    # Missing chlorophyll values are filled with the typical (median) value.
    chl = np.where(np.isnan(chl), np.nanmedian(chl), chl)

    # --- THE THREE SIGNALS ---------------------------------------------------
    # 1) Front strength: how fast temperature changes between neighbouring points.
    d_lat, d_lon = np.gradient(sst)
    front = np.hypot(d_lat, d_lon)
    front = np.where(np.isnan(front) & water, 0, front)   # coastal points: no front info

    # 2) Cool pocket: how much cooler than the area average (never below zero).
    cool = np.clip(np.nanmean(sst) - sst, 0, None)

    # 3) Plankton: chlorophyll varies hugely, so we use a log scale (each step =
    #    10x more) to stop a few very high spots from dominating.
    plankton = np.log10(np.clip(chl, 0.01, None))

    # Blend: fronts 40%, plankton 40%, cool pockets 20%
    score = 0.4 * _scale01(front) + 0.4 * _scale01(plankton) + 0.2 * _scale01(cool)
    score = np.where(water, score, np.nan)  # never recommend land

    # --- PICK THE BEST ZONES -------------------------------------------------
    # Neighbouring points have almost identical scores, so we require chosen
    # zones to be at least 0.5 degrees (about 55 km) apart. Otherwise we'd
    # list the same spot six times.
    order = np.argsort(-np.nan_to_num(score, nan=-1).ravel())   # best first
    zones = []
    for flat_index in order:
        i, j = np.unravel_index(flat_index, score.shape)
        if np.isnan(score[i, j]):
            break
        far_enough = all(
            np.hypot(lats[i] - z["lat"], lons[j] - z["lon"]) >= min_gap_deg for z in zones
        )
        if far_enough:
            value = float(score[i, j])
            zones.append({
                "sector": f"Sector {'ABCDEFGH'[len(zones)]}",
                "lat": round(float(lats[i]), 2),
                "lon": round(float(lons[j]), 2),
                "sst": round(float(sst[i, j]), 1),
                "chlorophyll": round(float(chl[i, j]), 2),
                "yield_index": round(value, 2),
                "status": "High Yield" if value >= 0.85 else "Promising",
            })
        if len(zones) >= max_zones:
            break

    return {
        "zones": zones,
        "best_zone": zones[0],
        "data_date": str(sst_grid.time.values)[:10],
        "cells_analysed": int(water.sum()),
    }


# Runs only when you type: python ocean_data.py  (a quick test without the API)
if __name__ == "__main__":
    print("Fetching real ocean data (first run can take a minute)...")
    result = get_real_zones()
    print(f"Data date: {result['data_date']}  |  Sea points analysed: {result['cells_analysed']}\n")
    for z in result["zones"]:
        print(z)