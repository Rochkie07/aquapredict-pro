# find_datasets.py
# PURPOSE: Ask Copernicus "which datasets contain this variable?" and print
# the dataset names. Dataset names change over time, so we look them up
# instead of trusting old documentation.
#
# USAGE:  python find_datasets.py thetao      (temperature)
#         python find_datasets.py chl         (chlorophyll)

import re
import sys
import copernicusmarine

# Which variable to search for. Read from the command line, default to temperature.
variable = sys.argv[1] if len(sys.argv) > 1 else "thetao"

print(f"Searching Copernicus for datasets containing '{variable}' ...")
catalogue = copernicusmarine.describe(contains=[variable])

# The catalogue is a big nested object. Rather than depend on its exact
# structure (which can change between versions), we turn it into plain text
# and pull out anything that looks like a dataset name. Names always start
# with "cmems_".
try:
    text = catalogue.model_dump_json()
except AttributeError:
    text = str(catalogue)

names = sorted(set(re.findall(r"cmems_[A-Za-z0-9_.\-]+", text)))

# Keep only "analysis and forecast" (anfc) datasets with a daily time step (P1D):
# those are updated every day, which is what a daily advisory needs.
daily = [n for n in names if "anfc" in n and "P1D" in n]

print("\n--- Daily analysis/forecast datasets ---")
for n in daily:
    print(n)

if not daily:
    print("(none matched the filter; showing everything found)")
    for n in names:
        print(n)