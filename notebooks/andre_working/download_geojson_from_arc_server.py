# -*- coding: utf-8 -*-
"""
Created on 2026-02-15

Count features in an ArcGIS FeatureServer layer, download them as GeoJSON
(paged by maxRecordCount), and save a single merged GeoJSON file.

@author: André
"""

# =========================
# SECTION 1: IMPORTS & TIMER
# =========================

import os  # folder and path utilities
import time  # runtime measurement
import json  # write GeoJSON to disk
import requests  # make HTTP requests to ArcGIS REST

t0 = time.time()  # start timer

# =========================
# SECTION 2: USER VARIABLES
# =========================

base_service_url = (
    "https://services1.arcgis.com/HmwnYiJTBZ4UkySc/arcgis/rest/services/"
    "Walking_Distance/FeatureServer"
)  # FeatureServer base URL

layer_id = 0  # layer index shown on the service page

out_geojson_path = (
    r"D:\Andre\Ecosoc\schools\data\subway\Walking_Distance.geojson"
)  # output file path

where_clause = "1=1"  # all features
out_fields = "*"  # all attributes
out_sr = 4326  # WGS84 lon/lat for GeoJSON
batch_size = 2000  # must be <= maxRecordCount (yours is 2000)
token = None  # add token string here if service is secured

# =========================
# SECTION 3: BUILD ENDPOINTS
# =========================

layer_query_url = (  # build /0/query endpoint
    f"{base_service_url}/{layer_id}/query"
)

# =========================
# SECTION 4: PARAM BUILDERS
# =========================

def build_base_params():
    """Shared query parameters for this layer."""
    params = {}  # start empty parameter dict
    params["where"] = where_clause  # filter
    if token:  # only add token if provided
        params["token"] = token  # authentication token
    return params  # return param dict


def get_feature_count():
    """Get count of features matching where_clause."""
    params = build_base_params()  # start with shared params
    params["returnCountOnly"] = "true"  # request only the count
    params["f"] = "pjson"  # response format: JSON
    r = requests.get(layer_query_url, params=params, timeout=120)  # request
    r.raise_for_status()  # raise exception for HTTP errors
    data = r.json()  # parse response JSON
    return int(data.get("count", 0))  # return count safely


def fetch_geojson_page(offset):
    """Fetch one page of GeoJSON features using resultOffset paging."""
    params = build_base_params()  # start with shared params
    params["outFields"] = out_fields  # attributes to return
    params["returnGeometry"] = "true"  # include geometry
    params["outSR"] = out_sr  # output spatial reference
    params["f"] = "geojson"  # request GeoJSON directly
    params["resultRecordCount"] = batch_size  # page size
    params["resultOffset"] = offset  # page start
    r = requests.get(layer_query_url, params=params, timeout=300)  # request
    r.raise_for_status()  # raise exception for HTTP errors
    return r.json()  # parsed GeoJSON dict


# =========================
# SECTION 5: DOWNLOAD & SAVE
# =========================

total = get_feature_count()  # count total features
print(f"Total features: {total}")  # print for user visibility

all_features = []  # list to store all features
offset = 0  # first page offset

while offset < total:  # loop until all features fetched
    page = fetch_geojson_page(offset)  # fetch one page of GeoJSON
    features = page.get("features", [])  # read features list
    if not features:  # safety stop if empty response
        break  # exit loop
    all_features.extend(features)  # accumulate features
    offset += batch_size  # move offset to next page
    print(f"Downloaded {len(all_features)} / {total}")  # progress message

geojson_out = {  # build single FeatureCollection
    "type": "FeatureCollection",
    "features": all_features,
}

out_dir = os.path.dirname(out_geojson_path)  # output folder
if out_dir and not os.path.exists(out_dir):  # check if folder exists
    os.makedirs(out_dir)  # create folder if needed

with open(out_geojson_path, "w", encoding="utf-8") as f:  # open file
    json.dump(geojson_out, f, ensure_ascii=False)  # write GeoJSON

print(f"Saved GeoJSON to: {out_geojson_path}")  # confirm save location

# =========================
# SECTION 6: RUNTIME REPORT
# =========================

t1 = time.time()  # end timer
dt = int(round(t1 - t0))  # total seconds
hh = dt // 3600  # hours
mm = (dt % 3600) // 60  # minutes
ss = dt % 60  # seconds
print(f"Total runtime: {hh:02d}:{mm:02d}:{ss:02d}")  # print runtime
