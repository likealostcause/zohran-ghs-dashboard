import os
import zipfile

import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Load school points
# ---------------------------------------------------------------------------
schools = gpd.read_file("data/processed_data/school_points_with_lcgms.shp")

# ---------------------------------------------------------------------------
# Join boroughs
# ---------------------------------------------------------------------------
boroughs = gpd.read_file("data/raw_data/NYC Planning/Boroughs/nybb_25c/nybb.shp")[
    ["BoroName", "geometry"]
].to_crs(schools.crs)
master_schools = gpd.sjoin(schools, boroughs, how="left", predicate="within").drop(
    columns=["index_right"]
)

# ---------------------------------------------------------------------------
# Join DACs
# ---------------------------------------------------------------------------
dacs = gpd.read_file("data/processed_data/dac_nyc_lite.geojson")

# Check that no schools sit exactly on a DAC border
assert (
    schools.geometry.apply(dacs.union_all().covers).sum()
    == schools.geometry.within(dacs.union_all()).sum()
)

master_schools = gpd.sjoin(schools, dacs, how="left", predicate="within")
master_schools.drop(columns=["index_right", "county", "geoid"], inplace=True)
master_schools["dac_designation"] = master_schools["dac_designation"].fillna(False)

# ---------------------------------------------------------------------------
# Join election results (nearest-neighbor fallback for unmatched schools)
# ---------------------------------------------------------------------------
primary_results = gpd.read_file("data/processed_data/zohran_first_round_frac.geojson")

master_schools_og_crs = master_schools.crs
primary_results_og_crs = primary_results.crs
master_schools = master_schools.to_crs("EPSG:3857")
primary_results = primary_results.to_crs("EPSG:3857")

master_schools = gpd.sjoin(
    master_schools, primary_results, how="left", predicate="within"
).drop(columns=["index_right"])

unmatched_mask = master_schools["ZohranFirstRoundFrac"].isna()
unmatched_schools = master_schools[unmatched_mask].copy()
print(
    f"Found {unmatched_mask.sum()} schools without polygon matches, "
    "using nearest neighbor..."
)

nearest_join = gpd.tools.sjoin_nearest(
    unmatched_schools.drop(columns="ZohranFirstRoundFrac"), primary_results, how="left"
)
master_schools.loc[unmatched_mask, "ZohranFirstRoundFrac"] = nearest_join[
    "ZohranFirstRoundFrac"
].values

assert not master_schools["ZohranFirstRoundFrac"].isna().any()

master_schools = master_schools.to_crs(master_schools_og_crs)
primary_results = primary_results.to_crs(primary_results_og_crs)

# ---------------------------------------------------------------------------
# Join A/C data
# ---------------------------------------------------------------------------
no_ac_summary = pd.read_csv("data/processed_data/no_ac_summary.csv")

ct_bldg_codes_missing_from_ac_data = (
    master_schools["Bldg_Code"].nunique() - no_ac_summary["BuildingCode"].nunique()
)

master_schools = master_schools.merge(
    no_ac_summary, left_on="Bldg_Code", right_on="BuildingCode", how="left"
).drop(columns=["BuildingCode"])

assert (
    master_schools.drop_duplicates(subset=["Bldg_Code"])["CLS_No_AC"].isna().sum()
    == ct_bldg_codes_missing_from_ac_data
)

# ---------------------------------------------------------------------------
# Join ventilation data
# ---------------------------------------------------------------------------
missing_ventilation_summary = pd.read_csv(
    "data/processed_data/missing_ventilation_summary.csv"
)

ct_bldg_codes_missing_from_vent_data = (
    master_schools["Bldg_Code"].nunique()
    - missing_ventilation_summary["BuildingCode"].nunique()
)

master_schools = master_schools.merge(
    missing_ventilation_summary,
    left_on="Bldg_Code",
    right_on="BuildingCode",
    how="left",
).drop(columns=["BuildingCode"])

assert (
    master_schools.drop_duplicates(subset=["Bldg_Code"])["CLS_No_VT"].isna().sum()
    == ct_bldg_codes_missing_from_vent_data
)

# ---------------------------------------------------------------------------
# Join building capacity + utilization
# ---------------------------------------------------------------------------
bldg_capacity_utilization = pd.read_csv(
    "data/processed_data/bldg_capacity_utilization.csv"
)
bldg_capacity_utilization.rename(
    columns={
        "Bldg ID": "Bldg_Code",
        "Bldg Enroll": "Bldg_Enroll",
        "Target Bldg Cap": "Bldg_Cap",
        "Target Bldg Util": "Bldg_Util",
        "Data As Of": "Util_As_Of",
    },
    inplace=True,
)
bldg_capacity_utilization["Util_As_Of"] = pd.to_datetime(
    bldg_capacity_utilization["Util_As_Of"], format="%Y-%m-%d"
)

master_schools = master_schools.merge(
    bldg_capacity_utilization[
        ["Bldg_Code", "Bldg_Enroll", "Bldg_Cap", "Bldg_Util", "Util_As_Of"]
    ],
    on="Bldg_Code",
    how="left",
)

# ---------------------------------------------------------------------------
# Join BAP (Building Accessibility Profile)
# ---------------------------------------------------------------------------
# TODO: there's 1 single school with "No Information Available" for the description.
# Remove that and make it null
# TODO: fill nulls with "No Data" so that the Esri dashboard category filter can deal
# with the nulls appropriately
bap = pd.read_csv("data/processed_data/bap_with_school_codes.csv")
bap.drop(columns=["Location Code"], inplace=True)
bap.drop_duplicates(subset=["Building Code"], inplace=True)

# TODO: undo all the 10-char column names and export as GPKG
master_schools = master_schools.merge(
    bap, left_on="Bldg_Code", right_on="Building Code", how="left"
).drop(columns=["Building Code"])

# ---------------------------------------------------------------------------
# Join IBO School Barriers data
# ---------------------------------------------------------------------------
# NOTE: IBO only included schools that appeared in all their source datasets
# (effectively an inner join). Going to primary sources may yield better coverage.
# TODO: go back and get the original sources of all the data in IBO dataset to see if
# we can get better coverage.
ibo_barriers = pd.read_excel(
    "data/raw_data/IBO/IBO-barriers-to-learning-data-file.xlsx", sheet_name="DATA"
)
print(
    "Pct match from IBO to master_schools:",
    ibo_barriers["building_code"].isin(master_schools["Bldg_Code"]).sum()
    / len(ibo_barriers),
)

ibo_barriers["central_ac"] = ibo_barriers["central_ac"].map({"Y": 1, "N": 0})

ibo_barriers = ibo_barriers[
    ["building_code", "building_ownership_description", "yearbuilt", "age"]
]

master_schools = master_schools.merge(
    ibo_barriers, left_on="Bldg_Code", right_on="building_code", how="left"
).drop(columns=["building_code"])

# ---------------------------------------------------------------------------
# Join solar-readiness data
# ---------------------------------------------------------------------------
solar_readiness = pd.read_parquet(
    "data/processed_data/solar_readiness_assessment_doe_buildings_2024.parquet"
)
solar_readiness.rename(
    columns={
        "Site": "Solar_Site",
        "Status": "Solar_Status",
        "Year of Report": "Solar_Year_of_Report",
    },
    inplace=True,
)

master_schools = master_schools.merge(
    solar_readiness, left_on="Bldg_Code", right_on="Solar_Site", how="left"
)

# ---------------------------------------------------------------------------
# Join city council districts
# ---------------------------------------------------------------------------
council_districts = gpd.read_file(
    "data/processed_data/city_council_districts.geojson"
).to_crs(master_schools.crs)
master_schools = gpd.sjoin(
    master_schools, council_districts, how="left", predicate="within"
).drop(columns=["index_right", "BOROUGH", "Shape_Leng", "Shape_Area"])

# ---------------------------------------------------------------------------
# Join school districts
# ---------------------------------------------------------------------------
school_districts = gpd.read_file(
    "data/raw_data/NYC Planning/School Districts/nysd_26a/nysd.shp"
).to_crs(master_schools.crs)
school_districts.drop(columns=["Shape_Leng", "Shape_Area"], inplace=True)

master_schools = master_schools.sjoin(school_districts).drop(columns=["index_right"])

# ---------------------------------------------------------------------------
# Join LL84 energy data
# ---------------------------------------------------------------------------
ll84 = gpd.read_file("data/processed_data/ll84.geojson")
master_schools = master_schools.merge(
    ll84,
    left_on=["Bldg_Code", "Loc_Code"],
    right_on=["Building Code", "Location Code"],
    how="left",
    suffixes=("", "_right"),
).drop(columns=["Location Code", "Building Code", "geometry_right"])

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
master_schools.fillna(value=pd.NA, inplace=True)

shortened_cols = {
    # DAC columns
    "dac_designation": "in_dac",
    "combined_score": "comb_score",
    "percentile_rank_combined_nyc": "pctl_comb",
    "burden_score": "burd_score",
    "burden_score_percentile": "pctl_burd",
    "vulnerability_score": "vuln_score",
    "vulnerability_score_percentile": "pctl_vuln",
    # Primary results columns
    "ZohranFirstRoundFrac": "ZohrPrimR1",
    # Building Accessibility Profile columns
    "BAP Rating": "BAP_Rating",
    "Accessibility Description": "AccessDesc",
    # IBO columns
    "age": "Bldg_Age",
    "building_ownership_description": "Bldg_Owner",
    "Accessibility_Description": "Accessible",
    # Council District columns
    "NAME": "CouncName",
    "POLITICAL PARTY": "CouncParty",
    "DISTRICT OFFICE ADDRESS": "CouncAddr",
    "DISTRICT OFFICE PHONE": "CouncPhone",
    # LL84 columns
    "ENERGY STAR Score": "eng_star",
    "Site EUI (kBtu/ft²)": "eui_norm",
    "Site Energy Use (kBtu)": "eui_raw",
    "Percent Electricity": "pct_elec",
    "Direct GHG Emissions (Metric Tons CO2e)": "ghg_raw",
    "Direct GHG Emissions Intensity (kgCO2e/ft²)": "ghg_norm",
    "Water Use (All Water Sources) (kgal)": "water_use",
    "Weather Normalized Site EUI (kBtu/ft²)": "WN_SiteEUI",
    "Weather Normalized Site Energy Use (kBtu)": "WN_SiteEn",
    "Fuel Oil #1 Use (kBtu)": "FO1_kBtu",
    "Fuel Oil #2 Use (kBtu)": "FO2_kBtu",
    "Fuel Oil #4 Use (kBtu)": "FO4_kBtu",
    "Fuel Oil #5 & 6 Use (kBtu)": "FO56_kBtu",
    "Diesel #2 Use (kBtu)": "Diesel2",
    "Propane Use (kBtu)": "Propane",
    "Kerosene Use (kBtu)": "Kerosene",
    "District Steam Use (kBtu)": "DistSteam",
    "District Hot Water Use (kBtu)": "DistHotW",
    "District Chilled Water Use (kBtu)": "DistChill",
    "Natural Gas Use (kBtu)": "NatGas",
    "Electricity Use - Grid Purchase (kBtu)": "Elec_kBtu",
    "Electricity Use - Grid Purchase (kWh)": "Elec_kWh",
    "Electricity Use – Generated from Onsite Renewable Systems (kWh)": "OnsiteGen",
    "Electricity Use – Generated from Onsite Renewable Systems and Exported (kWh)": (
        "OnGenExp"
    ),
    "Green Power - Onsite (kWh)": "GreenPwr",
    "Avoided Emissions - Onsite Green Power (Metric Tons CO2e)": "AvoidCO2",
    "Percent of Electricity that is Green Power": "PctGreen",
    "Percent of Total Electricity Generated from Onsite Renewable Systems": "PctOnGen",
    "Report Submission Date": "RptDate",
    # Capacity Utilization columns
    "Bldg_Enroll": "Bldg_Enrl",
    # Solar-Readiness columns
    "Solar_Status": "Sol_Stat",
    "Solar_Year_of_Report": "Sol_Yr_Rep",
    "Capacity (kW)": "Sol_Capac",
    "Solar-Readiness Assessment": "Sol_Rd_Ass",
    "Percentage of Max Peak Demand": "SolPctDemd",
    "Estimated Annual Production (kWh)": "SolEstProd",
    "Percentage of Annual Electricity Consumption": "SolPctCnsm",
    "Estimated Annual Emissions Reduction (MT CO2)": "SolEmisRed",
    "Estimated Social Cost of Carbon Value": "SolSocCost",
    "Estimated Annual Energy Savings": "SolEnrgSav",
    "Installation Date": "SolInstDt",
    "Financing Mechanism": "SolFinMech",
    "Upfront Project Cost": "Sol_Cost",
    "Total Gross Square Footage": "SolTotSqFt",
    "Roof Condition": "Sol_Rf_Con",
    "Roof Age": "Sol_Rf_Age",
    "Other Sustainability Projects": "Sol_Ot_Prj",
}

for col in master_schools.rename(columns=shortened_cols).columns:
    if len(col) > 10:
        print(f"{col} too long: currently {len(col)} chars")

master_schools = master_schools.rename(columns=shortened_cols)

shp_path = "data/processed_data/master_schools.shp"
master_schools.sort_values("Loc_Code").to_file(shp_path, driver="ESRI Shapefile")

zip_path = "data/processed_data/master_schools.zip"
base_name = "data/processed_data/master_schools"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
        file_path = base_name + ext
        if os.path.exists(file_path):
            zipf.write(file_path, os.path.basename(file_path))
            print(f"Added {os.path.basename(file_path)} to zip")
print(f"Shapefile saved as zip: {zip_path}")

master_schools.sort_values("Loc_Code").to_file(
    "data/processed_data/master_schools.geojson", driver="GeoJSON"
)
