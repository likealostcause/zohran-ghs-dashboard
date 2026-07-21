"""Tests for the check_join DQ assertion helper."""

import geopandas as gpd
import pytest
from shapely.geometry import Point

from pipelines.join_to_schools import check_join


def _gdf(loc_codes, bldg_codes, **extra):
    """Build a minimal GeoDataFrame for DQ tests."""
    n = len(loc_codes)
    data = {
        "Loc_Code": loc_codes,
        "Bldg_Code": bldg_codes,
        "geometry": [Point(0, i) for i in range(n)],
        **extra,
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


class TestCheckJoin:
    def test_passes_silently_when_all_conditions_met(self):
        before = _gdf(["A", "B"], ["X", "Y"])
        after = _gdf(["A", "B"], ["X", "Y"], score=[1.0, 2.0])
        check_join(
            before,
            after,
            "test",
            null_sentinel_cols=["Loc_Code", "Bldg_Code"],
            match_col="score",
            min_match_rate=1.0,
        )

    def test_raises_when_row_count_increases(self):
        before = _gdf(["A", "B"], ["X", "Y"])
        after = _gdf(["A", "B", "C"], ["X", "Y", "Z"])
        with pytest.raises(AssertionError, match="row count"):
            check_join(before, after, "test", null_sentinel_cols=["Loc_Code"])

    def test_raises_when_sentinel_col_gains_nulls(self):
        before = _gdf(["A", "B"], ["X", "Y"])
        after = _gdf([None, "B"], ["X", "Y"])
        with pytest.raises(AssertionError, match="null count increased"):
            check_join(before, after, "test", null_sentinel_cols=["Loc_Code"])

    def test_raises_when_duplicate_loc_codes(self):
        before = _gdf(["A", "B"], ["X", "Y"])
        after = _gdf(["A", "A"], ["X", "X"])
        with pytest.raises(AssertionError, match="duplicate Loc_Code"):
            check_join(before, after, "test", null_sentinel_cols=["Bldg_Code"])

    def test_raises_when_match_rate_below_threshold_with_actual_rate_in_message(self):
        before = _gdf(["A", "B", "C", "D"], ["W", "X", "Y", "Z"])
        after = _gdf(
            ["A", "B", "C", "D"],
            ["W", "X", "Y", "Z"],
            score=[1.0, None, None, None],
        )
        with pytest.raises(AssertionError, match="25.0%"):
            check_join(
                before,
                after,
                "test",
                null_sentinel_cols=["Loc_Code"],
                match_col="score",
                min_match_rate=0.80,
            )

    def test_logs_match_rate_to_stdout_even_when_above_threshold(self, capsys):
        before = _gdf(["A", "B"], ["X", "Y"])
        after = _gdf(["A", "B"], ["X", "Y"], score=[1.0, 2.0])
        check_join(
            before,
            after,
            "test",
            null_sentinel_cols=["Loc_Code"],
            match_col="score",
            min_match_rate=0.80,
        )
        captured = capsys.readouterr()
        assert "score" in captured.out
        assert "100.0%" in captured.out
