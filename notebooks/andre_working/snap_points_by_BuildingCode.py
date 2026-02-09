# -*- coding: utf-8 -*-
"""
Created on 2026-02-08

Snap all points that share the same Bldg_Code to the exact same coordinate.
Keeps ALL rows and ALL attributes unchanged, except updates:
- geometry (point location)
- lat and lng fields (to match snapped geometry)

Writes a new GeoJSON in the same folder.

@author: André
"""

# ================================ IMPORTS ====================================

import os  # build output paths
import time  # runtime tracking
import pandas as pd  # safe dtype handling and grouping
import geopandas as gpd  # read/write GeoJSON and edit geometries
from shapely.geometry import Point  # create point geometries


# ============================== USER VARIABLES ===============================

in_path = (
    r"D:\Andre\Ecosoc\schools\data\school_points\master_schools"
    r"\master_schools_v2\master_schools_020326.geojson"
)  # input point layer

out_name = "master_schools_020326_snapBldg.geojson"  # output filename

group_field = "Bldg_Code"  # field used to snap points together
lat_field = "lat"  # latitude field to update
lng_field = "lng"  # longitude field to update


# ============================== HELPER FUNCTION ==============================

def is_valid_point(geom):
    """
    Return True if geom is a non-empty Point geometry.
    """
    if geom is None:
        return False
    if geom.is_empty:
        return False
    if geom.geom_type != "Point":
        return False
    return True


# ================================== MAIN ====================================

t0 = time.time()  # start timer

gdf = gpd.read_file(in_path)  # read the input GeoJSON

n_before = len(gdf)  # ADDED: feature count before changes

# ADDED
# Validate required fields exist.
for req in [group_field, lat_field, lng_field]:
    if req not in gdf.columns:
        raise ValueError(f"Missing required field: {req}")

# ADDED
# Normalize building codes (do NOT drop any rows; blanks just won't be snapped).
codes = gdf[group_field].astype("string").str.strip()  # normalized codes
gdf[group_field] = codes  # write back normalized codes

# ADDED
# Build target coordinate per Bldg_Code using the first valid point geometry.
targets = {}  # maps Bldg_Code -> (x, y)
for code, idxs in gdf.groupby(group_field).groups.items():
    if pd.isna(code) or code == "":
        continue  # skip blank codes (leave those rows unchanged)

    found = False  # track if we found a valid geometry
    for i in idxs:
        geom = gdf.at[i, "geometry"]
        if is_valid_point(geom):
            targets[code] = (float(geom.x), float(geom.y))
            found = True
            break

    if not found:
        continue  # if no valid geometry in group, leave unchanged

# ADDED
# Apply snapping to ALL rows with a target coordinate (no row filtering).
mask = gdf[group_field].isin(list(targets.keys()))  # rows to snap

# ADDED
# Update geometry + lng/lat based on the building's target coordinate.
gdf.loc[mask, "geometry"] = gdf.loc[mask, group_field].map(
    lambda c: Point(targets[c][0], targets[c][1])
)

gdf.loc[mask, lng_field] = gdf.loc[mask, group_field].map(
    lambda c: targets[c][0]
)

gdf.loc[mask, lat_field] = gdf.loc[mask, group_field].map(
    lambda c: targets[c][1]
)

# ADDED
# Coerce lat/lng to numeric for consistency (does not change values).
gdf[lat_field] = pd.to_numeric(gdf[lat_field], errors="coerce")
gdf[lng_field] = pd.to_numeric(gdf[lng_field], errors="coerce")

out_folder = os.path.dirname(in_path)  # same folder as input
out_path = os.path.join(out_folder, out_name)  # full output path

gdf.to_file(out_path, driver="GeoJSON")  # write updated layer

n_after = len(gdf)  # ADDED: feature count after changes

t1 = time.time()  # end timer
elapsed = int(round(t1 - t0))  # elapsed seconds as integer

hrs = elapsed // 3600  # hours component
mins = (elapsed % 3600) // 60  # minutes component
secs = elapsed % 60  # seconds component

print(f"Rows before: {n_before}")  # confirm no deletion
print(f"Rows after:  {n_after}")  # confirm no deletion
print(f"Rows snapped: {int(mask.sum())}")  # how many rows moved
print(f"Unique Bldg_Code snapped: {len(targets)}")  # groups handled
print(f"Saved: {out_path}")  # confirm output path
print(f"Total runtime: {hrs:02d}:{mins:02d}:{secs:02d}")  # runtime report
