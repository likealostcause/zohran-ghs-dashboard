# -*- coding: utf-8 -*-
"""
Created on 2026-01-30

Read a school point GeoJSON, compute percentile-based categorical versions of
selected continuous fuel-use fields, and write an updated GeoJSON.

Rules
- 0 stays 0 (exact zeros remain in the 0 category)
- 25/50/75 are quartile cutoffs computed from values > 0 (non-zero users)
- 100 is the top bin (includes the maximum observed value)
- Null inputs become the string 'No data' in the new categorical fields

@author: André
"""

# ================================ IMPORTS ====================================

import time  # runtime tracking
import numpy as np  # numeric helpers (nan, quantiles)
import geopandas as gpd  # read/write spatial vector data


# ============================== USER VARIABLES ===============================

in_path = (
    r"D:\Andre\Ecosoc\schools\data\LL84\ll84.gdb"
)  # input GeoJSON path

out_path = (
    r"D:\Andre\Ecosoc\schools\data\LL84\ll84_wPct.gdb"
)  # output GeoJSON path (change to in_path to overwrite)

fields_to_bin = [
    "no2_2022",
    "pm25_2022",
    "ENERGY_STAR_Score",
    "Direct_GHG_Emissions__Metric_Tons_CO2e_",
    "Site_EUI__kBtu_ft²_",
    "Percent_Electricity",
    "Electricity_Use_–_Generated_from_Onsite_Renewable_Systems__kWh_",
    "Fuel_Oil__2_Use__kBtu_",
    "Fuel_Oil__4_Use__kBtu_",
    "District_Steam_Use__kBtu_",
    "District_Hot_Water_Use__kBtu_",
    "Natural_Gas_Use__kBtu_",
    "Diesel__2_Use__kBtu_"
    
    
]  # continuous fields to convert

no_data_string = "No data"  # ADDED


# ============================== HELPER FUNCTION ==============================

def make_percentile_category(series, missing_text):
    """
    Convert a numeric Series into categorical quartile percent labels
    - 0 -> "0"
    - >0 -> "25" "50" "75" "100" based on quartiles of values > 0
    - null -> missing_text
    """
    s = series.copy()  # copy so we do not mutate the original series
    s = gpd.pd.to_numeric(s, errors="coerce")  # coerce bad values to NaN

    out = gpd.pd.Series(index=s.index, dtype="object")  # ADDED

    is_null = s.isna()  # True where input is null/NaN
    is_zero = (s == 0) & (~is_null)  # True where value is exactly 0
    is_pos = (s > 0) & (~is_null)  # True where value is positive

    out.loc[is_null] = missing_text  # ADDED
    out.loc[is_zero] = "0"  # ADDED

    pos_vals = s.loc[is_pos]  # subset to positive values (non-zero users)

    if pos_vals.empty:  # if there are no positive values, return as-is
        return out  # return with zeros and missing_text already assigned
    
    # If there's only one positive value (or all positives are identical),
    # treat them as the top bin so they don't get trapped in the <= q25 rule.
    if pos_vals.nunique(dropna=True) == 1:
        out.loc[is_pos] = "100"
        return out

    q25 = float(pos_vals.quantile(0.25))  # 25th percentile among >0 values
    q50 = float(pos_vals.quantile(0.50))  # 50th percentile among >0 values
    q75 = float(pos_vals.quantile(0.75))  # 75th percentile among >0 values

    pos_mask = is_pos  # alias for readability

    out.loc[pos_mask & (s <= q25)] = "25"  # ADDED
    out.loc[pos_mask & (s > q25) & (s <= q50)] = "50"  # ADDED
    out.loc[pos_mask & (s > q50) & (s <= q75)] = "75"  # ADDED
    out.loc[pos_mask & (s > q75)] = "100"  # ADDED

    return out  # return categorical text series


# ================================ MAIN =======================================

t0 = time.time()  # start timer

gdf = gpd.read_file(in_path)  # read the input point layer

for fld in fields_to_bin:  # loop through requested continuous fields
    if fld not in gdf.columns:  # skip if the field is missing
        print(f"Field not found, skipping: {fld}")  # user feedback
        continue  # move to the next field

    new_fld = f"{fld}_pct"  # add percentile abbreviation at the end

    gdf[new_fld] = make_percentile_category(  # ADDED
        gdf[fld],  # ADDED
        no_data_string,  # ADDED
    )  # ADDED

gdf.to_file(out_path, driver="GeoJSON")  # write updated layer to GeoJSON

t1 = time.time()  # end timer
elapsed = int(round(t1 - t0))  # elapsed seconds as integer

hrs = elapsed // 3600  # hours component
mins = (elapsed % 3600) // 60  # minutes component
secs = elapsed % 60  # seconds component

print(f"Saved: {out_path}")  # confirm output path
print(f"Total runtime: {hrs:02d}:{mins:02d}:{secs:02d}")  # runtime report
