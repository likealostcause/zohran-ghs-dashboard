"""
Assemble master_schools.geojson by joining all data layers onto school points.

Each join is a standalone function that takes a GeoDataFrame and returns one.
Call build_master_schools() to run the full pipeline.
"""

import os
import zipfile

import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Column rename map (shapefile-era 10-char names; deferred full rename to U10)
# ---------------------------------------------------------------------------
SHORTENED_COLS = {
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

# Columns produced internally that are not part of the ArcGIS schema.
# Dropped before export.
_INTERNAL_COLS = ["BoroName"]


# ---------------------------------------------------------------------------
# Geometry fix
# ---------------------------------------------------------------------------


def snap_schools_by_building_code(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Align schools that share a building to a shared centroid.

    Multiple schools in the same building can have slightly different point
    locations. Groups by Bldg_Code, replaces each group's geometries with the
    centroid of the group, and updates lat/lng to match.
    """
    crs = schools.crs
    centroid_by_bldg = (
        schools.groupby("Bldg_Code")["geometry"]
        .apply(lambda g: g.union_all().centroid)
        .rename("snapped_geom")
    )
    result = schools.join(centroid_by_bldg, on="Bldg_Code")
    result["lat"] = result["snapped_geom"].y
    result["lng"] = result["snapped_geom"].x
    return (
        result.set_geometry("snapped_geom", crs=crs)
        .drop(columns=["geometry"])
        .rename_geometry("geometry")
    )


# ---------------------------------------------------------------------------
# Join functions
# ---------------------------------------------------------------------------


def join_boroughs(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boroughs = gpd.read_file("data/raw_data/NYC Planning/Boroughs/nybb_25c/nybb.shp")[
        ["BoroName", "geometry"]
    ].to_crs(schools.crs)
    return gpd.sjoin(schools, boroughs, how="left", predicate="within").drop(
        columns=["index_right"]
    )


def join_dacs(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    dacs = gpd.read_file("data/processed_data/dac_nyc_lite.geojson")
    dac_union = dacs.union_all()
    assert (
        schools.geometry.apply(dac_union.covers).sum()
        == schools.geometry.within(dac_union).sum()
    ), "Some schools sit exactly on a DAC border — check geometry validity"
    result = gpd.sjoin(schools, dacs, how="left", predicate="within").drop(
        columns=["index_right", "county", "geoid"]
    )
    result["dac_designation"] = result["dac_designation"].fillna(False)
    return result


def join_election_results(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    primary_results = gpd.read_file(
        "data/processed_data/zohran_first_round_frac.geojson"
    )
    og_crs = schools.crs
    schools_proj = schools.to_crs("EPSG:3857")
    results_proj = primary_results.to_crs("EPSG:3857")

    joined = gpd.sjoin(schools_proj, results_proj, how="left", predicate="within").drop(
        columns=["index_right"]
    )

    unmatched = joined["ZohranFirstRoundFrac"].isna()
    print(
        f"Found {unmatched.sum()} schools without polygon matches, "
        "using nearest neighbor..."
    )
    nearest = gpd.tools.sjoin_nearest(
        joined[unmatched].drop(columns="ZohranFirstRoundFrac"),
        results_proj,
        how="left",
    )
    joined.loc[unmatched, "ZohranFirstRoundFrac"] = nearest[
        "ZohranFirstRoundFrac"
    ].values

    assert not joined["ZohranFirstRoundFrac"].isna().any()
    return joined.to_crs(og_crs)


def join_ac(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    no_ac = pd.read_csv("data/processed_data/no_ac_summary.csv")
    ct_missing = schools["Bldg_Code"].nunique() - no_ac["BuildingCode"].nunique()
    result = schools.merge(
        no_ac, left_on="Bldg_Code", right_on="BuildingCode", how="left"
    ).drop(columns=["BuildingCode"])
    assert (
        result.drop_duplicates(subset=["Bldg_Code"])["CLS_No_AC"].isna().sum()
        == ct_missing
    )
    return result


def join_ventilation(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    vent = pd.read_csv("data/processed_data/missing_ventilation_summary.csv")
    ct_missing = schools["Bldg_Code"].nunique() - vent["BuildingCode"].nunique()
    result = schools.merge(
        vent, left_on="Bldg_Code", right_on="BuildingCode", how="left"
    ).drop(columns=["BuildingCode"])
    assert (
        result.drop_duplicates(subset=["Bldg_Code"])["CLS_No_VT"].isna().sum()
        == ct_missing
    )
    return result


def join_capacity_utilization(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cap = pd.read_csv("data/processed_data/bldg_capacity_utilization.csv")
    cap.rename(
        columns={
            "Bldg ID": "Bldg_Code",
            "Bldg Enroll": "Bldg_Enroll",
            "Target Bldg Cap": "Bldg_Cap",
            "Target Bldg Util": "Bldg_Util",
            "Data As Of": "Util_As_Of",
        },
        inplace=True,
    )
    cap["Util_As_Of"] = pd.to_datetime(cap["Util_As_Of"], format="%Y-%m-%d")
    return schools.merge(
        cap[["Bldg_Code", "Bldg_Enroll", "Bldg_Cap", "Bldg_Util", "Util_As_Of"]],
        on="Bldg_Code",
        how="left",
    )


def join_bap(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # TODO: 1 school has "No Information Available" — remove and make null
    # TODO: fill nulls with "No Data" for Esri dashboard category filter
    bap = pd.read_csv("data/processed_data/bap_with_school_codes.csv")
    bap.drop(columns=["Location Code"], inplace=True)
    bap.drop_duplicates(subset=["Building Code"], inplace=True)
    return schools.merge(
        bap, left_on="Bldg_Code", right_on="Building Code", how="left"
    ).drop(columns=["Building Code"])


def join_ibo(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # NOTE: IBO only included schools appearing in all their source datasets
    # (effectively an inner join). Going to primary sources may yield better coverage.
    # TODO: go back and get the original sources of all the data in IBO dataset
    ibo = pd.read_excel(
        "data/raw_data/IBO/IBO-barriers-to-learning-data-file.xlsx", sheet_name="DATA"
    )
    print(
        "Pct match from IBO to master_schools:",
        ibo["building_code"].isin(schools["Bldg_Code"]).sum() / len(ibo),
    )
    ibo["central_ac"] = ibo["central_ac"].map({"Y": 1, "N": 0})
    ibo = ibo[["building_code", "building_ownership_description", "yearbuilt", "age"]]
    return schools.merge(
        ibo, left_on="Bldg_Code", right_on="building_code", how="left"
    ).drop(columns=["building_code"])


def join_solar(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    solar = pd.read_parquet(
        "data/processed_data/solar_readiness_assessment_doe_buildings_2024.parquet"
    )
    solar.rename(
        columns={
            "Site": "Solar_Site",
            "Status": "Solar_Status",
            "Year of Report": "Solar_Year_of_Report",
        },
        inplace=True,
    )
    return schools.merge(solar, left_on="Bldg_Code", right_on="Solar_Site", how="left")


def join_council_districts(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    council = gpd.read_file(
        "data/processed_data/city_council_districts.geojson"
    ).to_crs(schools.crs)
    return gpd.sjoin(schools, council, how="left", predicate="within").drop(
        columns=["index_right", "BOROUGH", "Shape_Leng", "Shape_Area"]
    )


def join_school_districts(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    districts = gpd.read_file(
        "data/raw_data/NYC Planning/School Districts/nysd_26a/nysd.shp"
    ).to_crs(schools.crs)
    districts.drop(columns=["Shape_Leng", "Shape_Area"], inplace=True)
    return schools.sjoin(districts).drop(columns=["index_right"])


def join_ll84(schools: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    ll84 = gpd.read_file("data/processed_data/ll84.geojson")
    return schools.merge(
        ll84,
        left_on=["Bldg_Code", "Loc_Code"],
        right_on=["Building Code", "Location Code"],
        how="left",
        suffixes=("", "_right"),
    ).drop(columns=["Location Code", "Building Code", "geometry_right"])


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_master_schools(
    schools_path: str = "data/processed_data/school_points_with_lcgms.shp",
) -> gpd.GeoDataFrame:
    schools = gpd.read_file(schools_path)
    schools = snap_schools_by_building_code(schools)
    master = join_boroughs(schools)
    master = join_dacs(master)
    master = join_election_results(master)
    master = join_ac(master)
    master = join_ventilation(master)
    master = join_capacity_utilization(master)
    master = join_bap(master)
    master = join_ibo(master)
    master = join_solar(master)
    master = join_council_districts(master)
    master = join_school_districts(master)
    master = join_ll84(master)

    master = master.fillna(value=pd.NA)
    master = master.drop(columns=[c for c in _INTERNAL_COLS if c in master.columns])
    master = master.rename(columns=SHORTENED_COLS)

    for col in master.columns:
        if len(col) > 10:
            print(f"WARNING: column name too long for shapefile export: {col!r}")

    return master


def export(master: gpd.GeoDataFrame) -> None:
    master = master.sort_values("Loc_Code")

    shp_path = "data/processed_data/master_schools.shp"
    master.to_file(shp_path, driver="ESRI Shapefile")

    zip_path = "data/processed_data/master_schools.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            fp = "data/processed_data/master_schools" + ext
            if os.path.exists(fp):
                zf.write(fp, os.path.basename(fp))
                print(f"Added {os.path.basename(fp)} to zip")
    print(f"Shapefile saved as zip: {zip_path}")

    master.to_file("data/processed_data/master_schools.geojson", driver="GeoJSON")


def main() -> None:
    master = build_master_schools()
    export(master)


if __name__ == "__main__":
    main()
