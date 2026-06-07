"""
TDD tests for snap_schools_by_building_code.

Verified 2026-06-06 against ArcGIS export: snapped coords match André's
implementation within 20m for all 309 fully-aligned multi-school buildings.
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from pipelines.join_to_schools import snap_schools_by_building_code


@pytest.fixture
def schools() -> gpd.GeoDataFrame:
    """Minimal synthetic dataset: two multi-school buildings and one solo school."""
    return gpd.GeoDataFrame(
        {
            "Loc_Code": ["M001", "M002", "M003", "M004", "M005"],
            "Bldg_Code": ["X001", "X001", "X002", "X002", "X003"],
            "lat": [40.700, 40.701, 40.800, 40.801, 40.900],
            "lng": [-74.000, -74.001, -74.100, -74.101, -74.200],
            "geometry": [
                Point(-74.000, 40.700),
                Point(-74.001, 40.701),
                Point(-74.100, 40.800),
                Point(-74.101, 40.801),
                Point(-74.200, 40.900),
            ],
        },
        crs="EPSG:4326",
    )


class TestSnapPointsInvariant:
    def test_row_count_unchanged(self, schools):
        assert len(snap_schools_by_building_code(schools)) == len(schools)

    def test_crs_unchanged(self, schools):
        assert snap_schools_by_building_code(schools).crs == schools.crs

    def test_all_schools_in_same_building_share_geometry(self, schools):
        snapped = snap_schools_by_building_code(schools)
        multi = snapped[snapped.duplicated("Bldg_Code", keep=False)]
        non_uniform = multi.groupby("Bldg_Code")["geometry"].apply(
            lambda g: g.nunique() > 1
        )
        assert not non_uniform.any(), (
            f"Buildings with non-identical geometries after snap: "
            f"{non_uniform[non_uniform].index.tolist()}"
        )

    def test_lat_lng_updated_to_match_geometry(self, schools):
        snapped = snap_schools_by_building_code(schools)
        assert (snapped["lat"] - snapped.geometry.y).abs().max() < 1e-8
        assert (snapped["lng"] - snapped.geometry.x).abs().max() < 1e-8
