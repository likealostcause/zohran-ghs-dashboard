# -*- coding: utf-8 -*-
"""
Created on 2026-02-15

Load school points and walking-distance polygons, spatially join the
WalkingB_1 field to points, and create a new text field (subway_dist)
formatted like "0-5 min", with nulls set to ">10 min". Save to GeoJSON.

@author: André
"""

# ============================================================
# SECTION 1: IMPORTS, RUNTIME TIMER, AND USER VARIABLES
# ============================================================

import os  # file and folder operations
import time  # runtime measurement
import geopandas as gpd  # geospatial dataframes
import pandas as pd  # table operations (null handling, string ops)

t0 = time.time()  # start timer

# --------------------------- User variables --------------------------- #

schools_path = (
    r"D:\Andre\Ecosoc\schools\data\school_points\master_schools"
    r"\master_schools_v2\master_schools_020926.geojson"
)  # input school points GeoJSON

walking_dist_path = (
    r"D:\Andre\Ecosoc\schools\data\subway\Walking_Distance.geojson"
)  # input walking-distance polygons GeoJSON

join_field = "WalkingB_1"  # field to bring from polygons
out_field = "subway_dist2"  # new output text field on schools

out_schools_path = (
    r"D:\Andre\Ecosoc\schools\data\school_points\master_schools"
    r"\master_schools_v2\master_schools_020926_subwaydist.geojson"
)  # output schools GeoJSON (new file)

# ============================================================
# SECTION 2: READ DATA
# ============================================================

schools_gdf = gpd.read_file(schools_path)  # read schools layer
walk_gdf = gpd.read_file(walking_dist_path)  # read walking-distance layer

# ============================================================
# SECTION 3: CRS ALIGNMENT
# ============================================================

if schools_gdf.crs is None:  # check schools CRS exists
    raise ValueError("Schools layer has no CRS defined.")  # stop with message

if walk_gdf.crs is None:  # check walking-distance CRS exists
    raise ValueError("Walking_Distance layer has no CRS defined.")  # stop

walk_gdf = walk_gdf.to_crs(schools_gdf.crs)  # reproject polygons to schools CRS

# ============================================================
# SECTION 4: SPATIAL JOIN (JOIN BY LOCATION)
# ============================================================

walk_sel = walk_gdf[[join_field, "geometry"]].copy()  # keep only needed field

schools_joined = gpd.sjoin(  # spatial join polygons -> points
    schools_gdf,  # left dataframe (points)
    walk_sel,  # right dataframe (polygons with join_field)
    how="left",  # keep all schools even if no match
    predicate="within",  # points within polygons
)

# ============================================================
# SECTION 5: BUILD subway_dist FIELD
# ============================================================

schools_joined[out_field] = schools_joined[join_field]  # start from joined field

schools_joined[out_field] = schools_joined[out_field].astype("string")  # ensure str

schools_joined[out_field] = schools_joined[out_field].str.replace(
    " ", "", regex=False
)  # remove spaces to turn "0 - 5" into "0-5"

schools_joined[out_field] = schools_joined[out_field].where(
    ~schools_joined[out_field].isna(),  # keep non-null
    ">10min",  # temporary fill for null joins
)  # set null joins

schools_joined[out_field] = schools_joined[out_field].apply(
    lambda x: f"{x} min" if x != ">10min" else ">10 min"
)  # add suffix, but keep ">10 min" exactly

# ============================================================
# SECTION 6: CLEAN UP JOIN FIELDS AND SAVE
# ============================================================

cols_to_drop = []  # list of columns to drop if present

if "index_right" in schools_joined.columns:  # join artifact column
    cols_to_drop.append("index_right")  # add to drop list

# Optionally drop the original joined WalkingB_1 field from output.
# If you want to keep it, comment out the next two lines.
if join_field in schools_joined.columns:  # check field exists
    cols_to_drop.append(join_field)  # drop if you only want subway_dist

schools_out = schools_joined.drop(columns=cols_to_drop)  # drop unwanted columns

out_dir = os.path.dirname(out_schools_path)  # output directory
if out_dir and not os.path.exists(out_dir):  # check output directory exists
    os.makedirs(out_dir)  # create output directory if needed

schools_out.to_file(out_schools_path, driver="GeoJSON")  # write output GeoJSON

print(f"Saved updated schools GeoJSON to:\n{out_schools_path}")  # confirm save

# ============================================================
# SECTION 7: RUNTIME REPORT
# ============================================================

t1 = time.time()  # end timer
dt = int(round(t1 - t0))  # total runtime seconds
hh = dt // 3600  # hours
mm = (dt % 3600) // 60  # minutes
ss = dt % 60  # seconds
print(f"Total runtime: {hh:02d}:{mm:02d}:{ss:02d}")  # print runtime
