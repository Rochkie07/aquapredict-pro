# scoring.py
# PURPOSE: Turn raw ocean measurements into a simple "where should I fish?" score.
# WHY a separate file: the API (main.py) handles web requests; this file handles
# the thinking. Keeping them apart means you can improve the science later
# without touching the web code.

import numpy as np
import pandas as pd


def get_ocean_grid() -> pd.DataFrame:
    """
    Returns a table of ocean measurements, one row per map point.

    RIGHT NOW this is SAMPLE data so you can build and demo without waiting
    on satellite accounts. Later we replace the inside of this function with a
    real Copernicus Marine call. Nothing else in the project needs to change,
    which is the benefit of keeping the data source in one function.
    """
    data = {
        "sector": ["Sector Alpha", "Sector Beta", "Sector Gamma", "Sector Delta", "Sector Epsilon"],
        "lat": [4.25, 4.50, 4.75, 5.00, 5.25],      # latitude: north-south position
        "lon": [5.10, 5.30, 5.50, 5.70, 5.90],      # longitude: east-west position
        "sst": [26.5, 24.2, 24.0, 27.8, 25.1],      # sea surface temperature in degrees C
        "chlorophyll": [1.2, 3.5, 3.8, 0.5, 2.9],   # chlorophyll-a: a proxy for plankton, which fish feed on
    }
    return pd.DataFrame(data)


def score_zones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a 'yield_index' column (0 to 1) to each point. Higher = better fishing.

    The logic is a simple rule of thumb ("heuristic"):
      - Fish tend to gather in a certain temperature band  -> temperature score
      - Fish tend to gather where plankton is plentiful    -> plankton score
    We blend the two, giving temperature a bit more weight (60/40).

    NOTE: the 24.0 to 25.8 C band and the 60/40 weights are starting assumptions
    for the prototype, not proven science. Be upfront about this in your pitch
    ("rule-based model, to be calibrated with local catch data in the pilot").
    Judges respect honesty about this more than overclaiming.
    """
    df = df.copy()  # work on a copy so we never accidentally alter the original data

    # 1.0 if the temperature is inside the ideal band, otherwise a low 0.4
    in_band = (df["sst"] >= 24.0) & (df["sst"] <= 25.8)
    df["temp_score"] = np.where(in_band, 1.0, 0.4)

    # Scale chlorophyll to 0-1 by dividing by the highest value in the table
    df["plankton_score"] = df["chlorophyll"] / df["chlorophyll"].max()

    # Blend the two scores into the final index
    df["yield_index"] = (df["temp_score"] * 0.6 + df["plankton_score"] * 0.4).round(2)

    # Plain-English label, since fishers read words better than decimals
    df["status"] = np.where(df["yield_index"] >= 0.8, "High Yield", "Moderate")
    return df


def best_zone(df: pd.DataFrame) -> dict:
    """Returns the single highest-scoring row as a simple dictionary."""
    top = df.sort_values("yield_index", ascending=False).iloc[0]
    return top.to_dict()


# This block only runs when you execute THIS file directly (python scoring.py).
# It's a quick way to test the brain without starting the whole API.
if __name__ == "__main__":
    scored = score_zones(get_ocean_grid())
    print(scored)
    print("\nBest zone:", best_zone(scored))