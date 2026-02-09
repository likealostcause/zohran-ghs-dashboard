# -*- coding: utf-8 -*-
"""
Created on 2026-01-12

1) Search an ESRI GRID folder tree for NYCCAS Year 14 rasters:
   - aa14_pm300m (PM2.5)
   - aa14_no2300m (NO2)
   Convert each to a high-compression GeoTIFF in the output folder.

2) Load school points from a FileGDB, sample both rasters at each point,
   add fields named by pollutant + year (e.g., pm25_aa14, no2_aa14),
   and write an updated FileGDB with a _011226 date suffix.

@author: André
"""

# =============================== IMPORTS =====================================

import os  # filesystem walking and path handling
import time  # runtime tracking
from datetime import datetime  # timestamps for logs

from osgeo import gdal, ogr, osr  # ADDED: OGR/OSR for writing FileGDB
import geopandas as gpd  # vector IO + reprojection
import rasterio  # point sampling from GeoTIFFs
import fiona  # list GDB layers and write outputs
import numpy as np  # ADDED: robust NaN / dtype handling
import pandas as pd  # ADDED: isna() for pandas missing values



# Enable GDAL exceptions so errors raise Python exceptions
gdal.UseExceptions()  # make GDAL errors easier to debug

# ============================ USER VARIABLES =================================

# Base folder containing the ESRI GRID subfolders (aa14_pm300m, aa14_no2300m)
in_base_folder = r"D:\Andre\Ecosoc\schools\data\air_pollution\AnnAvg_1_15_300m"

# Output folder for GeoTIFFs and the updated geodatabase
out_folder = r"D:\Andre\Ecosoc\schools\data\air_pollution"

# School points FileGDB path (input)
schools_gdb = (
    r"D:\Andre\Ecosoc\schools\data\school_points\master_schools\master_schools_dec25\master_schools_v2_122725.gdb"
)

# Date suffix requested for the output geodatabase name
date_suffix = "011226"

# Names of the ESRI GRID folders we want to find (most recent = Year 14)
target_grids = {
    "aa14_pm300m": {"pollutant": "pm25", "year": "aa14"},
    "aa14_no2300m": {"pollutant": "no2", "year": "aa14"},
}

# GeoTIFF compression settings (high compression)
compress_method = "DEFLATE"  # lossless compression
zlevel = 9  # max compression level for DEFLATE
tiled = "YES"  # tiling improves read performance
bigtiff = "IF_SAFER"  # avoid failures on large rasters

# ============================ HELPER FUNCTIONS ===============================

def find_grid_folder_paths(base_folder, grid_folder_names):
    """
    Walk base_folder and return a dict of {grid_folder_name: full_path}.
    """
    found = {}  # store matches here

    # Walk through every directory in the tree
    for root, dirs, files in os.walk(base_folder):
        # Loop over directories in this root
        for d in dirs:
            # If directory name matches one of the target ESRI GRID names
            if d in grid_folder_names:
                # Store the full path to the ESRI GRID folder
                found[d] = os.path.join(root, d)

    return found  # return all matches found


def gdal_dtype_is_float(gdal_dtype):
    """
    Return True if GDAL data type is float32/float64.
    """
    # GDAL float types are GDT_Float32 (6) and GDT_Float64 (7)
    return gdal_dtype in (gdal.GDT_Float32, gdal.GDT_Float64)


def esri_grid_to_geotiff(in_grid_path, out_tif_path):
    """
    Convert an ESRI GRID (folder-based) raster to high-compression GeoTIFF.
    """
    # Open the ESRI GRID dataset using GDAL
    ds = gdal.Open(in_grid_path)  # GDAL can open by folder path

    # Raise an error if GDAL couldn't open the dataset
    if ds is None:
        raise RuntimeError(f"GDAL could not open: {in_grid_path}")

    # Get the first band to detect data type
    band = ds.GetRasterBand(1)  # first band is used for dtype detection

    # Read GDAL dtype code (e.g., Float32, Int16)
    dtype = band.DataType  # GDAL dtype integer code

    # Use predictor 3 for float, predictor 2 for integers
    predictor = "3" if gdal_dtype_is_float(dtype) else "2"

    # Build creation options for compressed GeoTIFF
    creation_options = [
        f"COMPRESS={compress_method}",  # set compression to DEFLATE
        f"ZLEVEL={zlevel}",  # compression level for DEFLATE
        f"PREDICTOR={predictor}",  # predictor improves compression
        f"TILED={tiled}",  # write tiled GeoTIFF
        f"BIGTIFF={bigtiff}",  # handle big files safely
    ]

    # Translate (convert) to GeoTIFF without loading whole raster in memory
    gdal.Translate(
        destName=out_tif_path,  # output GeoTIFF path
        srcDS=ds,  # input dataset
        format="GTiff",  # output format
        creationOptions=creation_options,  # compression options
    )

    # Close dataset explicitly
    ds = None  # release file handles


def choose_school_layer(gdb_path):
    """
    Choose a likely layer from a FileGDB.
    If multiple layers exist, prefer one with 'school' or 'master' in name.
    """
    # List all layers inside the GDB
    layers = fiona.listlayers(gdb_path)  # returns list of layer names

    # If there's only one layer, use it
    if len(layers) == 1:
        return layers[0]  # return the only layer

    # Lowercase names for easy matching
    layers_lower = [lyr.lower() for lyr in layers]  # normalize case

    # Priority keywords to search for
    keywords = ["master", "school", "schools", "points"]  # likely layer hints

    # Try to find a layer that contains any keyword
    for kw in keywords:
        for lyr, lyr_l in zip(layers, layers_lower):
            if kw in lyr_l:
                return lyr  # return first good match

    # Fallback: just return the first layer
    return layers[0]  # safest default


def sample_raster_at_points(tif_path, points_gdf):
    """
    Sample a single-band GeoTIFF at point locations.
    Returns a list of sampled values aligned with points_gdf.
    """
    # Open the raster with rasterio for fast sampling
    with rasterio.open(tif_path) as src:
        # Reproject points to raster CRS if needed
        if points_gdf.crs != src.crs:
            points_proj = points_gdf.to_crs(src.crs)  # match raster CRS
        else:
            points_proj = points_gdf  # already matches CRS

        # Build a generator of (x, y) coordinates in raster CRS
        coords = (
            (geom.x, geom.y) for geom in points_proj.geometry
        )

        # Sample raster values at each coordinate (returns arrays per point)
        samples = src.sample(coords)  # generator of arrays

        # Extract first-band value per point, handling nodata as None
        vals = []  # store sampled values
        for arr in samples:
            # arr is a 1D array with length = band count (here 1)
            v = arr[0]  # first band value
            # Convert nodata to None where applicable
            if src.nodata is not None and v == src.nodata:
                vals.append(None)  # set nodata to None
            else:
                # Convert numpy scalars to Python float for clean output
                vals.append(float(v))  # store sampled value

    return vals  # return sampled values


def write_output_gdb(out_gdb_path, layer_name, gdf):
    """
    Write a GeoDataFrame to a File Geodatabase (.gdb) ONLY (no fallback).

    Uses GDAL/OGR drivers:
      1) OpenFileGDB (preferred if writable in your GDAL build)
      2) FileGDB (ESRI SDK-based, if available)

    Raises a clear error if neither driver can create a .gdb.
    """

    # ADDED: sanitize reserved field names that break GDB writers
    gdf_out = gdf.copy()  # make a safe copy so upstream isn't changed

    # ADDED: build lowercase map to preserve original case
    lower_to_orig = {c.lower(): c for c in gdf_out.columns}  # map for lookups

    # ADDED: rename 'fid' if present (conflicts with internal feature id)
    if "fid" in lower_to_orig:
        orig = lower_to_orig["fid"]  # original column name
        gdf_out = gdf_out.rename(columns={orig: "src_fid"})  # safe name

    # ADDED: rename OBJECTID if present (often treated specially)
    if "objectid" in lower_to_orig:
        orig = lower_to_orig["objectid"]  # original column name
        gdf_out = gdf_out.rename(columns={orig: "src_objectid"})  # safe name

    # ADDED: enforce field name length limit (FileGDB limit is 64 chars)
    rename_map = {}  # store any truncations here
    seen = set()  # track used names to avoid duplicates
    for col in gdf_out.columns:  # loop through all columns
        if col == gdf_out.geometry.name:  # skip geometry column
            continue  # do not rename geometry
        new = str(col)[:64]  # truncate to 64 chars
        base = new  # keep base for deduping
        i = 1  # suffix counter
        while new.lower() in seen:  # ensure uniqueness (case-insensitive)
            suf = f"_{i}"  # suffix text
            new = (base[: max(0, 64 - len(suf))] + suf)  # keep within 64
            i += 1  # increment suffix
        seen.add(new.lower())  # record used name
        if new != col:  # if renamed
            rename_map[col] = new  # store rename

    # ADDED: apply truncation renames if needed
    if rename_map:
        gdf_out = gdf_out.rename(columns=rename_map)  # rename columns safely

    # ADDED: choose a writable FileGDB driver from GDAL
    driver_names = ["OpenFileGDB", "FileGDB"]  # try in this order
    ogr_driver = None  # placeholder for selected driver
    for dn in driver_names:  # loop through candidate drivers
        d = ogr.GetDriverByName(dn)  # try to fetch driver
        if d is not None:  # if present in this GDAL build
            ogr_driver = d  # keep it
            break  # stop at first available

    # ADDED: fail loudly if no driver exists
    if ogr_driver is None:
        raise RuntimeError(
            "No writable FileGDB driver found in your GDAL build. "
            "GDAL needs OpenFileGDB (writable) or FileGDB installed."
        )

    # ADDED: delete existing output GDB if it already exists
    if os.path.exists(out_gdb_path):
        ogr_driver.DeleteDataSource(out_gdb_path)  # remove existing .gdb

    # ADDED: create the new GDB datasource
    ds = ogr_driver.CreateDataSource(out_gdb_path)  # create output .gdb
    if ds is None:
        raise RuntimeError(
            f"Failed to create FileGDB at: {out_gdb_path}. "
            "Your driver may be read-only (common for OpenFileGDB in some builds)."
        )

    # ADDED: build spatial reference from GeoDataFrame CRS
    srs = osr.SpatialReference()  # create an empty SRS
    if gdf_out.crs is not None:
        epsg = gdf_out.crs.to_epsg()  # try EPSG extraction
        if epsg is not None:
            srs.ImportFromEPSG(int(epsg))  # import EPSG
        else:
            srs.ImportFromWkt(gdf_out.crs.to_wkt())  # fallback to WKT

    # ADDED: create the output layer (geometry type inferred as Point)
    geom_type = ogr.wkbPoint  # your schools are points
    lyr = ds.CreateLayer(layer_name, srs=srs, geom_type=geom_type)  # make layer
    if lyr is None:
        raise RuntimeError(f"Failed to create layer '{layer_name}' in GDB.")


    # ADDED: create fields based on column dtypes (skip geometry)
    field_type_map = {}  # ADDED: remember each field's OGR type

    for col in gdf_out.columns:
        if col == gdf_out.geometry.name:
            continue  # skip geometry column

        series = gdf_out[col]  # column values

        if series.dtype.kind in ("i", "u"):
            ogr_type = ogr.OFTInteger64  # ADDED: integer field type
            fdef = ogr.FieldDefn(col, ogr_type)  # create field definition
        elif series.dtype.kind == "f":
            ogr_type = ogr.OFTReal  # ADDED: float field type
            fdef = ogr.FieldDefn(col, ogr_type)  # create field definition
        else:
            ogr_type = ogr.OFTString  # ADDED: string field type
            fdef = ogr.FieldDefn(col, ogr_type)  # create field definition
            fdef.SetWidth(254)  # set safe text width

        lyr.CreateField(fdef)  # add field to layer
        field_type_map[col] = ogr_type  # ADDED: store expected type


    # ADDED: write features row-by-row
    layer_defn = lyr.GetLayerDefn()  # schema reference
    for _, row in gdf_out.iterrows():
        feat = ogr.Feature(layer_defn)  # create a new feature

        # ADDED: set attribute fields (robust casting + NA/NaN handling)
        for col in gdf_out.columns:
            if col == gdf_out.geometry.name:
                continue  # skip geometry

            val = row[col]  # cell value

            # ADDED: treat pandas NA / NaN as NULL (OGR can't SetField with NaN)
            if val is None or pd.isna(val):
                continue  # keep null

            # ADDED: convert numpy scalar types to native Python types
            if hasattr(val, "item"):
                try:
                    val = val.item()  # numpy scalar -> python scalar
                except Exception:
                    pass  # keep as-is if conversion fails

            # ADDED: cast based on the field type we created
            ogr_type = field_type_map.get(col, ogr.OFTString)  # expected type

            try:
                if ogr_type == ogr.OFTInteger64:
                    # ADDED: handle floats that are actually ints, or strings
                    val = int(val)  # force integer
                elif ogr_type == ogr.OFTReal:
                    val = float(val)  # force float
                else:
                    val = str(val)  # force string
            except Exception:
                # ADDED: if casting fails, write NULL instead of crashing
                continue

            feat.SetField(col, val)  # set field value


        # ADDED: set geometry
        geom = row.geometry  # shapely geometry
        if geom is not None and not geom.is_empty:
            ogr_geom = ogr.CreateGeometryFromWkb(geom.wkb)  # shapely -> OGR
            feat.SetGeometry(ogr_geom)  # attach geometry

        lyr.CreateFeature(feat)  # write feature to disk
        feat = None  # free feature

    # ADDED: close and flush output
    ds = None  # close datasource and write to disk

    return out_gdb_path  # return final GDB path



# ================================ MAIN =======================================

if __name__ == "__main__":
    # Start runtime timer
    t0 = time.time()  # start time in seconds

    # Print start time for logs
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Ensure output folder exists
    os.makedirs(out_folder, exist_ok=True)  # create if missing

    # Find ESRI GRID folders in the base folder tree
    found_paths = find_grid_folder_paths(
        base_folder=in_base_folder,  # where to search
        grid_folder_names=set(target_grids.keys()),  # target names
    )

    # Check that we found each required grid
    for grid_name in target_grids:
        if grid_name not in found_paths:
            raise FileNotFoundError(
                f"Did not find required grid folder: {grid_name} "
                f"under {in_base_folder}"
            )

    # Convert each found ESRI GRID to a compressed GeoTIFF
    out_tifs = {}  # map grid_name -> output tif path
    for grid_name, grid_info in target_grids.items():
        # Get pollutant short name (pm25/no2) and year label (aa14)
        pol = grid_info["pollutant"]  # pollutant tag
        yr = grid_info["year"]  # year tag

        # Build output GeoTIFF filename
        out_tif_name = f"{pol}_{yr}.tif"  # requested naming pattern

        # Build full output path
        out_tif_path = os.path.join(out_folder, out_tif_name)  # output tif

        # Convert ESRI GRID folder to GeoTIFF
        print(f"Converting {grid_name} -> {out_tif_path}")
        esri_grid_to_geotiff(
            in_grid_path=found_paths[grid_name],  # ESRI GRID folder path
            out_tif_path=out_tif_path,  # GeoTIFF output path
        )

        # Store for later sampling
        out_tifs[grid_name] = out_tif_path  # save output path

    # Choose the school points layer from the input GDB
    schools_layer = choose_school_layer(schools_gdb)  # pick layer name
    print(f"Reading schools layer: {schools_layer}")

    # Read school points into a GeoDataFrame
    schools_gdf = gpd.read_file(
        schools_gdb,  # input GDB
        layer=schools_layer,  # chosen layer
    )

    # Ensure geometry exists and is point type
    if schools_gdf.geometry is None:
        raise RuntimeError("School layer has no geometry column.")

    # Sample each pollutant raster and add a field for it
    for grid_name, grid_info in target_grids.items():
        # Get pollutant and year labels
        pol = grid_info["pollutant"]  # pollutant tag
        yr = grid_info["year"]  # year tag

        # Build field name exactly as requested (pollutant + year)
        field_name = f"{pol}_{yr}"  # e.g., pm25_aa14, no2_aa14

        # Get the GeoTIFF path for this pollutant
        tif_path = out_tifs[grid_name]  # output tif to sample

        # Sample raster at school point locations
        print(f"Sampling {tif_path} -> field {field_name}")
        sampled_vals = sample_raster_at_points(
            tif_path=tif_path,  # raster path
            points_gdf=schools_gdf,  # school points
        )

        # Add the sampled values as a new column
        schools_gdf[field_name] = sampled_vals  # store pollutant values

    # Build output GDB name in the same out_folder
    out_gdb_name = f"master_schools_{date_suffix}.gdb"  # dated GDB name
    out_gdb_path = os.path.join(out_folder, out_gdb_name)  # full path

    # Build output layer name
    out_layer_name = f"master_schools_{date_suffix}"  # feature class name

    # Write updated schools to a new geodatabase (or GeoPackage fallback)
    written_path = write_output_gdb(
        out_gdb_path=out_gdb_path,  # target FileGDB path
        layer_name=out_layer_name,  # layer name
        gdf=schools_gdf,  # updated GeoDataFrame
    )

    # Report where output was written
    print(f"Saved updated output to: {written_path}")

    # End runtime timer
    t1 = time.time()  # end time in seconds

    # Compute elapsed time in seconds
    elapsed = t1 - t0  # total runtime

    # Convert to hours/minutes/seconds
    hours = int(elapsed // 3600)  # full hours
    minutes = int((elapsed % 3600) // 60)  # remaining minutes
    seconds = int(elapsed % 60)  # remaining seconds

    # Print total runtime
    print(f"Total runtime: {hours}h {minutes}m {seconds}s")
