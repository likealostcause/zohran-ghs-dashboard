# -*- coding: utf-8 -*-
"""
Created on 2026-02-03

Buffer NYC school points by 300 ft (after projecting to EPSG:2263), spatially
join to the NYC stormwater flood layer, and attach ONLY the highest-priority
(overlap-min) Stormwater_Flood_Risk record (1 beats 2 beats 3 beats 4) back to
the ORIGINAL school points. Points with no overlap get a default "no risk"
label and risk=0.

@author: André
"""

# ============================== IMPORTS ======================================

import time  # runtime tracking
import geopandas as gpd  # vector IO + spatial joins
import pandas as pd  # table helpers


# =========================== USER VARIABLES ==================================

schools_points_path = (
    r"D:\Andre\Ecosoc\schools\data\school_points\master_schools"
    r"\master_schools_v2\master_schools_013126.geojson"
)  # input school points (EPSG:4326)

stormwater_path = (
    r"D:\Andre\Ecosoc\schools\data\NYC_stormwater"
    r"\NYC_Stormwater_Flood_Current_Sea_Level.geojson"
)  # input stormwater polygons (EPSG:2263)

target_crs_epsg = 2263  # NY State Plane Long Island (ft)

buffer_distance_ft = 300.0  # buffer distance in feet (in EPSG:2263 units)

# Fields to bring over from stormwater layer
scenario_field = "Flood_Scenario"  # text
category_field = "Flood_Category"  # text
risk_field = "Stormwater_Flood_Risk"  # integer 1-4 (priority)

# Default values when NO overlap occurs
no_risk_label = "No forecasted risk of stormwater flooding"  # default text
no_risk_value = 0  # default risk integer for no-overlap

# Outputs
output_points_geojson = (
    r"D:\Andre\Ecosoc\schools\data\NYC_stormwater"
    r"\master_schools_013126_stormwater_joined.geojson"
)  # output points with joined fields

output_buffers_geojson = (
    r"D:\Andre\Ecosoc\schools\data\NYC_stormwater"
    r"\master_schools_013126_300ft_buffers.geojson"
)  # output buffers (optional, but useful for QA)


# ============================== MAIN =========================================

t0 = time.time()  # start runtime timer

# -------------------------- READ SCHOOL POINTS -------------------------------

schools_gdf = gpd.read_file(schools_points_path)  # read school points

if "geometry" not in schools_gdf.columns:  # verify geometry exists
    raise ValueError("School points file has no geometry column.")  # stop

if schools_gdf.crs is None:  # verify CRS exists
    raise ValueError("School points CRS is missing.")  # stop

schools_gdf = schools_gdf[schools_gdf.geometry.notnull()].copy()  # drop null
schools_gdf = schools_gdf[~schools_gdf.geometry.is_empty].copy()  # drop empty

schools_gdf = schools_gdf.reset_index(drop=True)  # reset index
schools_gdf["__pt_id"] = schools_gdf.index.astype(int)  # stable join id

# ADDED: prevent _x/_y collisions if fields already exist on schools
drop_if_exists = [scenario_field, category_field, risk_field]  # fields to drop
cols_to_drop = [c for c in drop_if_exists if c in schools_gdf.columns]  # list
if len(cols_to_drop) > 0:  # only if something exists
    schools_gdf = schools_gdf.drop(columns=cols_to_drop)  # drop them

# -------------------------- PROJECT + BUFFER ---------------------------------

schools_2263 = schools_gdf.to_crs(epsg=target_crs_epsg)  # project to ft CRS

buffers_gdf = schools_2263[["__pt_id", "geometry"]].copy()  # keep id+geom
buffers_gdf["geometry"] = buffers_gdf.geometry.buffer(  # build buffers
    buffer_distance_ft
)

buffers_gdf = buffers_gdf[buffers_gdf.geometry.notnull()].copy()  # keep valid
buffers_gdf = buffers_gdf[~buffers_gdf.geometry.is_empty].copy()  # keep valid

# -------------------------- READ STORMWATER LAYER ----------------------------

storm_gdf = gpd.read_file(stormwater_path)  # read stormwater polygons

if storm_gdf.crs is None:  # verify CRS exists
    raise ValueError("Stormwater layer CRS is missing.")  # stop

needed = [scenario_field, category_field, risk_field, "geometry"]  # required
missing = [c for c in needed if c not in storm_gdf.columns]  # check fields
if len(missing) > 0:  # if any required field missing
    raise ValueError(f"Missing stormwater fields: {missing}")  # stop

storm_keep = storm_gdf[needed].copy()  # keep only needed fields
storm_keep = storm_keep[storm_keep.geometry.notnull()].copy()  # keep valid
storm_keep = storm_keep[~storm_keep.geometry.is_empty].copy()  # keep valid

if storm_keep.crs.to_epsg() != target_crs_epsg:  # ensure same CRS as buffers
    storm_keep = storm_keep.to_crs(epsg=target_crs_epsg)  # reproject polygons

# -------------------------- SPATIAL JOIN (MANY-TO-ONE) -----------------------

joined = gpd.sjoin(  # join buffers to polygons
    buffers_gdf[["__pt_id", "geometry"]],  # left: buffer geometries
    storm_keep[[scenario_field, category_field, risk_field, "geometry"]],  # rt
    how="left",  # keep all buffers (even if no match)
    predicate="intersects",  # overlap or boundary touch
)

# -------------------------- PICK BEST (LOWEST RISK) --------------------------

ranked = joined.dropna(subset=[risk_field]).copy()  # keep rows with matches

# Coerce risk to numeric safely (handles strings like "1")
ranked[risk_field] = pd.to_numeric(  # convert to numeric
    ranked[risk_field],
    errors="coerce",
)

ranked = ranked.dropna(subset=[risk_field]).copy()  # drop non-numeric risk
ranked[risk_field] = ranked[risk_field].astype(int)  # make it integer

best = (  # choose the single best polygon per buffer
    ranked.sort_values(["__pt_id", risk_field], ascending=[True, True])  # 1st
    .drop_duplicates(subset=["__pt_id"], keep="first")  # keep lowest risk
    [["__pt_id", scenario_field, category_field, risk_field]]  # keep cols
)

# -------------------------- MERGE BACK TO ORIGINAL POINTS --------------------

out_points = schools_gdf.merge(  # attach chosen attributes to points
    best,
    on="__pt_id",
    how="left",
)

# Fill defaults for points with no overlap
out_points[scenario_field] = out_points[scenario_field].fillna(  # default text
    no_risk_label
)
out_points[category_field] = out_points[category_field].fillna(  # default text
    no_risk_label
)
out_points[risk_field] = out_points[risk_field].fillna(  # default numeric
    no_risk_value
).astype(int)

out_points = out_points.drop(columns=["__pt_id"])  # remove helper id

# -------------------------- WRITE OUTPUTS ------------------------------------

out_points.to_file(output_points_geojson, driver="GeoJSON")  # save points

buffers_gdf.to_file(output_buffers_geojson, driver="GeoJSON")  # save buffers

# -------------------------- RUNTIME PRINT ------------------------------------

t1 = time.time()  # end runtime timer
dt = t1 - t0  # elapsed seconds
hh = int(dt // 3600)  # hours
mm = int((dt % 3600) // 60)  # minutes
ss = dt % 60  # seconds

print(f"Saved points:\n{output_points_geojson}")  # confirm points output
print(f"Saved buffers:\n{output_buffers_geojson}")  # confirm buffers output
print(f"Runtime {hh:02d}:{mm:02d}:{ss:05.2f}")  # runtime
