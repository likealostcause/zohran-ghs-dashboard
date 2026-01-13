# -*- coding: utf-8 -*-
"""
Created on 2025-11-30

Prepare NYC school points with:
- Hurricane evacuation zone (hurricane_evacZone),
- Heat index class (OHEI),
- Distance (miles) to nearest evacuation center
  (evacCenters_distance_mi),
- Distance (miles) to nearest cooling center
  (cooling_centers_distance_mi),

then export as a GeoPackage (can be converted to .gdb later).

Unwanted join fields (index_hz, index_hi, hurricane_, OHEI_Class,
etc.) are removed so only your original school fields + the four
new fields remain.

@author: André
"""

# ============================================================
# SECTION 1: IMPORTS, RUNTIME TIMER, AND USER VARIABLES
# ============================================================

import os                  # for filesystem operations
import time                # for runtime measurement
import geopandas as gpd    # for vector / spatial operations
from shapely.geometry import Point  # handy for debug if needed

# start runtime timer
start_time = time.time()

# --------------- USER-EDITABLE VARIABLES --------------------

# path to input school points shapefile
schools_path = (
    r"D:\André\Ecosoc\schools\data\school_points\master_schools"
    r"\master_schools_v2\master_schools_test_nov24.shp"
)

# path to hurricane evacuation zones polygon layer (Shapefile)
hurricane_zones_path = (
    r"D:\André\Ecosoc\schools\data\hurricane\EvacZonesSHP.shp"
)

# field name in hurricane evac zones to keep
hurricane_field_name = "hurricane_"

# desired joined field name for hurricane evac zone in schools
joined_hurricane_field = "hurricane_evacZone"

# path to heat index polygons (GeoJSON)
heat_index_path = (
    r"D:\André\Ecosoc\schools\data\Heat_Index\NTAHeatData.geojson"
)

# field name in heat index layer to keep
heat_index_field_name = "OHEI_Class"

# desired joined field name for heat index in schools
joined_heat_index_field = "OHEI"

# path to evacuation centers (points, GeoJSON)
evac_centers_path = (
    r"D:\André\Ecosoc\schools\data\hurricane\EvacCenters.geojson"
)

# field name for distance to nearest evac center (miles)
distance_field_evac = "evacCenters_distance_mi"

# path to cooling centers (points, Shapefile)
cooling_centers_path = (
    r"D:\André\Ecosoc\schools\data\cooling_centers"
    r"\Cooling_Centers.shp"
)

# field name for distance to nearest cooling center (miles)
distance_field_cooling = "cooling_centers_distance_mi"

# projected CRS for NYC (feet) for distance calculations
# EPSG:2263 = NAD83 / New York Long Island (ftUS)
nyc_projected_crs = "EPSG:2263"

# output GeoPackage path (directory will be created if missing)
output_gpkg_path = (
    r"D:\André\Ecosoc\schools\data\school_points\outputs"
    r"\master_schools_with_hazard_metrics.gpkg"
)

# name of the output layer in the GeoPackage
output_layer_name = "master_schools_with_hazard_metrics"


# ============================================================
# SECTION 2: READ INPUT LAYERS
# ============================================================

# read school points from shapefile
schools_gdf = gpd.read_file(schools_path)

# ensure geometry column is active (usually already correct)
schools_gdf = schools_gdf.set_geometry("geometry")

# read hurricane evacuation zones polygons
hurricane_gdf = gpd.read_file(hurricane_zones_path)

# read heat index polygons
heat_index_gdf = gpd.read_file(heat_index_path)

# read evacuation centers points
evac_centers_gdf = gpd.read_file(evac_centers_path)

# read cooling centers points
cooling_centers_gdf = gpd.read_file(cooling_centers_path)

# print basic CRS and count info for sanity check
print("Schools CRS:", schools_gdf.crs)
print("Hurricane zones CRS:", hurricane_gdf.crs)
print("Heat index CRS:", heat_index_gdf.crs)
print("Evac centers CRS:", evac_centers_gdf.crs)
print("Cooling centers CRS:", cooling_centers_gdf.crs)
print("Number of schools:", len(schools_gdf))


# ============================================================
# SECTION 3: ALIGN CRSs FOR SPATIAL OPERATIONS
# ============================================================

# reproject hurricane zones to match schools CRS
if hurricane_gdf.crs != schools_gdf.crs:
    hurricane_gdf = hurricane_gdf.to_crs(schools_gdf.crs)

# reproject heat index polygons to match schools CRS
if heat_index_gdf.crs != schools_gdf.crs:
    heat_index_gdf = heat_index_gdf.to_crs(schools_gdf.crs)

# reproject evac centers to match schools CRS for consistency
if evac_centers_gdf.crs != schools_gdf.crs:
    evac_centers_gdf = evac_centers_gdf.to_crs(schools_gdf.crs)

# reproject cooling centers to match schools CRS for consistency
if cooling_centers_gdf.crs != schools_gdf.crs:
    cooling_centers_gdf = cooling_centers_gdf.to_crs(schools_gdf.crs)


# ============================================================
# SECTION 4: SPATIAL JOIN – HURRICANE EVACUATION ZONES
# ============================================================

# keep only needed column and geometry in hurricane layer
hurricane_cols = [hurricane_field_name, "geometry"]
hurricane_gdf = hurricane_gdf[hurricane_cols]

# spatial join: assign evac zone to each school by intersection
schools_with_hurricane = gpd.sjoin(
    schools_gdf,            # left: schools points
    hurricane_gdf,          # right: evac zones polygons
    how="left",             # keep all schools
    predicate="intersects", # intersect test
    lsuffix="sch",          # suffix for left columns
    rsuffix="hz"            # suffix for right columns
)

# drop join index column if present
if "index_right" in schools_with_hurricane.columns:
    schools_with_hurricane = schools_with_hurricane.drop(
        columns=["index_right"]
    )

# verify that hurricane field exists after join
if hurricane_field_name not in schools_with_hurricane.columns:
    raise ValueError(
        f"Field '{hurricane_field_name}' not found after "
        "hurricane zones spatial join."
    )

# create joined hurricane field with desired name
schools_with_hurricane[joined_hurricane_field] = (
    schools_with_hurricane[hurricane_field_name]
)


# ============================================================
# SECTION 5: SPATIAL JOIN – HEAT INDEX CLASSES
# ============================================================

# copy joined schools for heat index join
schools_joined = schools_with_hurricane.copy()

# keep only needed column and geometry in heat index layer
heat_index_cols = [heat_index_field_name, "geometry"]
heat_index_gdf = heat_index_gdf[heat_index_cols]

# spatial join: assign heat index class to each school
schools_with_heat = gpd.sjoin(
    schools_joined,         # left: schools with hurricane field
    heat_index_gdf,         # right: heat index polygons
    how="left",             # keep all schools
    predicate="intersects", # intersect test
    lsuffix="sch",          # suffix for left columns
    rsuffix="hi"            # suffix for right columns
)

# drop join index column if present
if "index_right" in schools_with_heat.columns:
    schools_with_heat = schools_with_heat.drop(
        columns=["index_right"]
    )

# verify that heat index field exists after join
if heat_index_field_name not in schools_with_heat.columns:
    raise ValueError(
        f"Field '{heat_index_field_name}' not found after "
        "heat index spatial join."
    )

# create joined heat index field with desired name
schools_with_heat[joined_heat_index_field] = (
    schools_with_heat[heat_index_field_name]
)

# overwrite schools GeoDataFrame with fully joined data
schools_gdf = schools_with_heat


# ============================================================
# SECTION 6: NEAREST DISTANCE TO EVACUATION CENTERS (MILES)
# ============================================================

# project schools to NYC projected CRS (feet) for distance
schools_proj = schools_gdf.to_crs(nyc_projected_crs)

# project evac centers to same NYC projected CRS
evac_centers_proj = evac_centers_gdf.to_crs(nyc_projected_crs)

# nearest spatial join with distance in feet (evac centers)
schools_nearest_evac = gpd.sjoin_nearest(
    schools_proj,                    # left: projected schools
    evac_centers_proj[["geometry"]], # right: projected centers
    how="left",                      # keep all schools
    distance_col="distance_ft"       # store distance in feet
)

# align indices to safely transfer distances back
schools_nearest_evac = schools_nearest_evac.sort_index()
schools_gdf = schools_gdf.sort_index()

# extract evac-center distance in feet as Series
distance_ft_evac = schools_nearest_evac["distance_ft"]

# convert feet to miles (1 mile = 5280 feet)
schools_gdf[distance_field_evac] = distance_ft_evac / 5280.0

# print summary statistics of evac distance field
print("Distance (miles) to nearest evac center (summary):")
print(schools_gdf[distance_field_evac].describe())


# ============================================================
# SECTION 7: NEAREST DISTANCE TO COOLING CENTERS (MILES)
# ============================================================

# project cooling centers to NYC projected CRS
cooling_centers_proj = cooling_centers_gdf.to_crs(nyc_projected_crs)

# nearest spatial join with distance in feet (cooling centers)
schools_nearest_cool = gpd.sjoin_nearest(
    schools_proj,                        # left: projected schools
    cooling_centers_proj[["geometry"]],  # right: projected centers
    how="left",                          # keep all schools
    distance_col="distance_ft"           # store distance in feet
)

# align indices again to ensure matching order
schools_nearest_cool = schools_nearest_cool.sort_index()
# schools_gdf is already sorted above, so we don't re-sort it

# extract cooling-center distance in feet as Series
distance_ft_cool = schools_nearest_cool["distance_ft"]

# convert feet to miles and store in new field
schools_gdf[distance_field_cooling] = distance_ft_cool / 5280.0

# print summary statistics of cooling distance field
print("Distance (miles) to nearest cooling center (summary):")
print(schools_gdf[distance_field_cooling].describe())


# ============================================================
# SECTION 8: DROP UNWANTED JOIN FIELDS
# ============================================================

# collect unwanted columns from joins:
# - any 'index_*' columns from sjoin
# - the original hurricane_ and OHEI_Class fields
#   (we keep only hurricane_evacZone and OHEI)
cols_to_drop = []

for col in schools_gdf.columns:
    # drop any index_* columns created during joins
    if col.startswith("index_"):
        cols_to_drop.append(col)
    # drop original right-side join fields
    if col in [hurricane_field_name, heat_index_field_name]:
        cols_to_drop.append(col)

# make list unique while preserving order
cols_to_drop = list(dict.fromkeys(cols_to_drop))

if cols_to_drop:
    print("Dropping join helper fields:", cols_to_drop)
    schools_gdf = schools_gdf.drop(columns=cols_to_drop)

# Now schools_gdf has:
# - all original school attributes
# - hurricane_evacZone
# - OHEI
# - evacCenters_distance_mi
# - cooling_centers_distance_mi
# - geometry


# ============================================================
# SECTION 9: EXPORT TO GEOPACKAGE (INSTEAD OF .GDB)
# ============================================================

# ensure output directory exists before writing
output_dir = os.path.dirname(output_gpkg_path)
os.makedirs(output_dir, exist_ok=True)

# write final schools GeoDataFrame to GeoPackage
schools_gdf.to_file(
    output_gpkg_path,        # path to output .gpkg
    layer=output_layer_name, # layer name inside GPKG
    driver="GPKG"            # GeoPackage driver
)

print(f"Exported layer to: {output_gpkg_path}")
print(f"Layer name: {output_layer_name}")
print("You can convert this GPKG to a FileGDB in QGIS/ArcGIS "
      "if needed.")


# ============================================================
# SECTION 10: TOTAL RUNTIME
# ============================================================

# compute total elapsed time in seconds
end_time = time.time()
total_seconds = int(end_time - start_time)

# convert seconds to hours, minutes, seconds
hours = total_seconds // 3600
minutes = (total_seconds % 3600) // 60
seconds = total_seconds % 60

# print formatted runtime
print(
    f"Total runtime: {hours:02d}:{minutes:02d}:{seconds:02d}"
)
