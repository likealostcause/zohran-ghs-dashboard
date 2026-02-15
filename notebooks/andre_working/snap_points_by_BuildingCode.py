# -*- coding: utf-8 -*-
"""
Created on 2026-02-10

Create mock DSM rasters (10 m) for SOC stock (tCO2e/ha) inside each field
polygon using a Gaussian-looking spatial variation surface:

1) Read field polygons and matching sample points (join by 'id')
2) Build one global 10 m raster grid covering all fields
3) For each timepoint, fill pixels inside each field with a smooth Gaussian
   random surface scaled around that field's base SOC value
4) Mask strictly by polygon (cell centers only; no edge inclusion)
5) Write one GeoTIFF per timepoint (+ optional PNG preview)
6) Create an additional GeoTIFF for total change across the time series:
   (SOC_t20 - SOC_t1) per pixel, with the same spatial texture

@author: André
"""

# ================================ IMPORTS ====================================

import os  # build output paths
import time  # runtime tracking
import numpy as np  # array math and random numbers
import geopandas as gpd  # read/write vector data
import rasterio  # raster I/O
from rasterio.transform import from_origin  # affine transform
from rasterio.features import geometry_mask  # polygon mask to raster grid
from scipy.ndimage import gaussian_filter  # smooth random fields
import matplotlib.pyplot as plt  # optional previews


# ============================== USER VARIABLES ===============================

fields_path = (
    r"D:\TerraCarbon\2026_projects\MARS\proposal\mock_fields_UTM.geojson"
)  # field polygons (UTM meters)

samples_path = (
    r"D:\TerraCarbon\2026_projects\MARS\proposal\mock_samples_UTM.geojson"
)  # sample points (UTM meters)

id_field = "id"  # field used to match points to polygons

time_fields = [
    "SOC_t1",
    "SOC_t5",
    "SOC_t10",
    "SOC_t15",
    "SOC_t20",
]  # SOC timepoints (tCO2e/ha)

t_start = "SOC_t1"  # ADDED: first timepoint for total change
t_end = "SOC_t20"  # ADDED: last timepoint for total change

out_folder = (
    r"D:\TerraCarbon\2026_projects\MARS\proposal\mock_dsm_outputs"
)  # output folder

pixel_size_m = 10.0  # output resolution (meters)

gauss_corr_m = 25.0  # smoothness (meters): higher = smoother

field_sd_base = 2.0  # baseline within-field SD (tCO2e/ha)

field_sd_frac = 0.15  # additional SD = fraction * abs(base SOC)

min_soc = 0.0  # clamp SOC to >= 0 for SOC rasters

nodata = -9999.0  # output nodata

write_png_previews = True  # write PNG previews alongside GeoTIFFs

random_seed = 42  # reproducible randomness


# ============================ HELPER FUNCTIONS ===============================

def _soc_sd(base_val, sd_base, sd_frac):
    """
    Compute within-field standard deviation from a base SOC value.
    """
    return float(sd_base + (abs(base_val) * sd_frac))


# ================================== MAIN ====================================

t0 = time.time()  # start timer

os.makedirs(out_folder, exist_ok=True)  # ensure output folder exists

fields = gpd.read_file(fields_path)  # read polygons
samples = gpd.read_file(samples_path)  # read points

if fields.crs is None or samples.crs is None:  # CRS required
    raise ValueError("Both inputs must have a CRS (UTM meters).")

if fields.crs != samples.crs:  # match CRS
    samples = samples.to_crs(fields.crs)  # reproject points to fields CRS

if id_field not in fields.columns:  # check join field
    raise ValueError(f"'{id_field}' not found in fields layer.")

if id_field not in samples.columns:  # check join field
    raise ValueError(f"'{id_field}' not found in samples layer.")

for tf in time_fields:  # check SOC fields exist
    if tf not in samples.columns:
        raise ValueError(f"'{tf}' not found in samples layer.")

# ADDED: verify start/end fields exist
if t_start not in samples.columns:
    raise ValueError(f"'{t_start}' not found in samples layer.")
if t_end not in samples.columns:
    raise ValueError(f"'{t_end}' not found in samples layer.")

fields = fields.reset_index(drop=True)  # clean index

# Build one global raster grid covering all fields (no padding).
minx, miny, maxx, maxy = fields.total_bounds  # overall bounds

width = int(np.ceil((maxx - minx) / pixel_size_m))  # columns
height = int(np.ceil((maxy - miny) / pixel_size_m))  # rows

transform = from_origin(minx, maxy, pixel_size_m, pixel_size_m)  # affine

rng = np.random.default_rng(random_seed)  # reproducible RNG

sigma_pix = gauss_corr_m / pixel_size_m  # smoothing in pixel units

# Build a lookup dict from id -> row index in samples for fast access.
samples_index = {}  # store first sample per id
for idx in range(len(samples)):  # loop all samples
    sid = samples.loc[idx, id_field]  # sample id
    if sid not in samples_index:  # keep first occurrence
        samples_index[sid] = idx  # store row index

# ADDED: store arrays so we can compute total change raster later
dsm_by_time = {}  # dict mapping time field -> DSM array

# Loop each timepoint and create one raster.
for tf in time_fields:
    dsm = np.full((height, width), nodata, dtype="float32")  # init output

    # Create one smooth random background for the entire extent.
    # This avoids tiny-window artifacts for very small fields.
    noise = rng.normal(0.0, 1.0, size=(height, width))  # white noise
    smooth = gaussian_filter(noise, sigma=sigma_pix)  # correlated field

    sm_mean = float(np.mean(smooth))  # mean
    sm_std = float(np.std(smooth))  # std
    if sm_std == 0.0:  # safety
        sm_std = 1.0  # avoid divide by zero

    z = (smooth - sm_mean) / sm_std  # mean 0, sd 1 surface

    # Process each field independently (different scaling per field).
    for i in range(len(fields)):
        poly = fields.loc[i, "geometry"]  # polygon geometry
        fid = fields.loc[i, id_field]  # polygon id

        if fid not in samples_index:  # must have matching sample
            raise ValueError(f"No sample point found for {id_field}={fid}.")

        srow = samples.loc[samples_index[fid]]  # sample row
        base_val = float(srow[tf])  # base SOC for this timepoint

        # Mask strictly by polygon (cell centers only; no edge inclusion).
        inside = geometry_mask(
            [poly],  # mask geometry
            out_shape=(height, width),  # raster shape
            transform=transform,  # raster transform
            invert=True,  # True where pixel center is inside
            all_touched=False,  # strict center-in-polygon behavior
        )

        if not np.any(inside):  # skip if polygon too small for 10 m grid
            continue

        # Scale the standardized surface to this field's mean and SD.
        sd_val = _soc_sd(base_val, field_sd_base, field_sd_frac)  # SD
        vals = base_val + (z * sd_val)  # field surface values
        vals = np.clip(vals, min_soc, None)  # clamp to >= 0

        # Write values only inside the field polygon.
        dsm[inside] = vals[inside].astype("float32")  # assign inside only

    # ADDED: store DSM array for change calculation later
    dsm_by_time[tf] = dsm.copy()  # keep a copy for change map

    # Write GeoTIFF for this timepoint.
    out_tif = os.path.join(out_folder, f"mock_DSM_{tf}_10m.tif")  # path

    with rasterio.open(
        out_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=fields.crs,
        transform=transform,
        nodata=nodata,
        compress="DEFLATE",
        predictor=3,
        zlevel=9,
    ) as dst:
        dst.write(dsm, 1)  # write band 1

    # Optional PNG preview.
    if write_png_previews:
        out_png = os.path.join(out_folder, f"mock_DSM_{tf}_10m.png")  # path
        arr = dsm.astype("float32")  # ensure float
        arr = np.where(arr == nodata, np.nan, arr)  # nodata -> nan

        plt.figure()  # new figure
        plt.imshow(arr, origin="upper")  # show raster
        plt.title(f"Mock DSM {tf} (tCO2e/ha)")  # title
        plt.colorbar(label="tCO2e/ha")  # colorbar
        plt.axis("off")  # hide axes
        plt.tight_layout()  # fit layout
        plt.savefig(out_png, dpi=250)  # save preview
        plt.close()  # close figure

# ADDED: compute total change raster (SOC_t20 - SOC_t1) per pixel
dsm_start = dsm_by_time[t_start]  # start DSM
dsm_end = dsm_by_time[t_end]  # end DSM

change = np.full((height, width), nodata, dtype="float32")  # init change

valid = (dsm_start != nodata) & (dsm_end != nodata)  # where both exist
change[valid] = (dsm_end[valid] - dsm_start[valid]).astype("float32")  # diff

# ADDED: write GeoTIFF for total change
out_change_tif = os.path.join(
    out_folder,
    f"mock_DSM_change_{t_end}_minus_{t_start}_10m.tif",
)

with rasterio.open(
    out_change_tif,
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=1,
    dtype="float32",
    crs=fields.crs,
    transform=transform,
    nodata=nodata,
    compress="DEFLATE",
    predictor=3,
    zlevel=9,
) as dst:
    dst.write(change, 1)  # write band 1

# ADDED: optional PNG preview for change
if write_png_previews:
    out_change_png = os.path.join(
        out_folder,
        f"mock_DSM_change_{t_end}_minus_{t_start}_10m.png",
    )
    arr = change.astype("float32")  # ensure float
    arr = np.where(arr == nodata, np.nan, arr)  # nodata -> nan

    plt.figure()  # new figure
    plt.imshow(arr, origin="upper")  # show raster
    plt.title(f"Mock DSM Change ({t_end} - {t_start}) (tCO2e/ha)")  # title
    plt.colorbar(label="tCO2e/ha")  # colorbar
    plt.axis("off")  # hide axes
    plt.tight_layout()  # fit layout
    plt.savefig(out_change_png, dpi=250)  # save preview
    plt.close()  # close figure

# Print runtime.
t1 = time.time()  # end timer
dt = t1 - t0  # total seconds
hh = int(dt // 3600)  # hours
mm = int((dt % 3600) // 60)  # minutes
ss = int(dt % 60)  # seconds
print(f"Total runtime: {hh:02d}:{mm:02d}:{ss:02d} (hh:mm:ss)")
