# test_copernicus.py
# PURPOSE: A standalone experiment. Download a small piece of real ocean data
# and look at it. We do this separately from main.py so that if something goes
# wrong, we know it's the data connection and not the rest of the project.

import copernicusmarine
import xarray as xr
from datetime import datetime, timedelta

# Which dataset to use. Copernicus has hundreds; each has an ID.
# This one is a global ocean model that is updated daily and also forecasts ahead.
DATASET_ID = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"

# The area we care about: the Nigerian coast and the Gulf of Guinea.
# We only ask for a small box, because downloading the whole world would be slow.
LAT_MIN, LAT_MAX = 4.0, 6.5
LON_MIN, LON_MAX = 3.0, 8.5

# Ask for the last 2 days. "Latest available" is what a daily advisory needs.
today = datetime.now()
start = (today - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00")
end = today.strftime("%Y-%m-%dT00:00:00")

print("Requesting data from Copernicus... (this can take a minute)")

copernicusmarine.subset(
    dataset_id=DATASET_ID,
    variables=["thetao"],           # "thetao" is Copernicus's name for sea water temperature
    minimum_longitude=LON_MIN,
    maximum_longitude=LON_MAX,
    minimum_latitude=LAT_MIN,
    maximum_latitude=LAT_MAX,
    minimum_depth=0,                # surface only: that's where small canoes fish
    maximum_depth=1,
    start_datetime=start,
    end_datetime=end,
    output_directory="data",        # saves into a folder called "data"
    output_filename="temperature.nc",
    overwrite=True,                 # replace the old file each run
)

# Open the downloaded file and take a look.
ds = xr.open_dataset("data/temperature.nc")
print("\n--- What we got ---")
print(ds)                           # a summary: variables, size, dates

# Pick the most recent day and the surface layer, then show a few numbers.
latest = ds["thetao"].isel(time=-1, depth=0)
print("\nDate of data:", str(latest.time.values)[:10])
print("Temperature range in our box: "
      f"{float(latest.min()):.1f} to {float(latest.max()):.1f} degrees C")
