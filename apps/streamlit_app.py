import geopandas as gpd
import pandas as pd
import pydeck as pdk
import streamlit as st

# from src.zohran_ghs_dashboard.utils import load_dac_data, load_school_locations_data

st.set_page_config(layout="wide")


@st.cache_data
def load_dac_data_pydeck(show_non_dac: bool = True) -> pdk.Layer:
    # Implement your data loading logic here
    # NOTE: not sure if it's more performant to load as dataframe and pass df to layer
    # or to load GeoJSON directly
    # For now, loading as pandas with the assumption that we'll need it for easy
    # filtering callbacks
    # NOTE: also not sure if we should load Geopandas and pass as GeoJSON or load
    # pandas, make sure there's lat/lon, and then pass it with non-GeoJSON layer type.
    dac_df = gpd.read_file("../data/processed_data/dac_nyc_full.geojson")

    # Filter data based on toggle
    if not show_non_dac:
        dac_df = dac_df[dac_df["dac_designation"]]

    dac_layer = pdk.Layer(
        "GeoJsonLayer",
        data=dac_df,
        # get_position=["longitude", "latitude"],
        get_fill_color=[100, 200, 250, 75],
        extruded=False,
        stroked=True,
        line_width_units="pixels",
        get_line_color=[150, 150, 150, 50],
        get_line_width=2,
        line_width_min_pixels=1,
        line_width_max_pixels=2.5,
        pickable=True,
        auto_highlight=True,
        # get_radius=1000,
    )
    return dac_layer


def load_school_locations_data():
    # Implement your data loading logic here
    pass


def get_deck(_layers: list[pdk.Layer]):
    # Set the initial view state for the map to NYC centroid
    view_state = pdk.ViewState(
        latitude=40.6976701,
        longitude=-73.9277866,
        zoom=9,
    )
    # These are the fields to be displayed when you hover over an object on the map.
    # TODO: need to figure out how to make this work with multiple layers
    FIELDS_FOR_TOOLTIP = [
        "geoid",
        "dac_designation",
        "combined_score",
        "percentile_rank_combined_nyc",
        # Add more fields as needed
    ]
    tooltip_html = """
    <table style='border-collapse:collapse; background:#fff; color:#222;'>
    <tr>
        <th style='text-align:left; border:1px solid #bbb; background:#fff;'>Field</th>
        <th style='text-align:left; border:1px solid #bbb; background:#fff;'>Value</th>
    </tr>
    """
    for i, field in enumerate(FIELDS_FOR_TOOLTIP):
        row_bg = "#f0f0f0" if i % 2 == 0 else "#fff"
        tooltip_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='border:1px solid #bbb; padding:2px 6px;'>{field}</td>"
            f"<td style='border:1px solid #bbb; padding:2px 6px;'>{{{field}}}</td>"
            "</tr>"
        )
    tooltip_html += "</table>"

    # Tooltip as an HTML table (excluding geometry)
    tooltip = {
        "html": tooltip_html,
        "style": {
            "backgroundColor": "#fff",
            "color": "#222",
            "fontSize": "12px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
            "borderRadius": "6px",
            "padding": "4px",
        },
    }
    deck = pdk.Deck(
        layers=_layers, initial_view_state=view_state, map_style=None, tooltip=tooltip
    )
    return deck


def render_legend(layer_states):
    # TODO: parameterize layer name and color so they update here automatically
    st.markdown("### Map Legend")
    row = st.container()
    with row:
        col1, col2, col3 = st.columns([0.1, 0.5, 0.4])
        with col1:
            st.markdown(
                "<div style='width:20px; height:20px; \
                    background:rgba(100,200,250,0.75); \
                    border:1px solid #333; border-radius:3px;'></div>",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown("**DAC Polygon**")
        with col3:
            dac_checked = st.checkbox(
                "",
                value=layer_states["dac"],
                key="legend_dac",
                label_visibility="hidden",
            )
    # Add more layers here as needed, following the same pattern
    return {"dac": dac_checked}


def main():
    # Remove extra vertical space above the title
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem !important; }
        </style>
    """,
        unsafe_allow_html=True,
    )
    st.title("Zohran GHS Dashboard")

    # Add toggle button for non-DAC areas
    with st.sidebar:
        st.markdown("## Filters")
        show_non_dac = st.checkbox("Show Non-DAC Areas", value=False)

    col_map, col_legend = st.columns([0.8, 0.2], width="stretch")

    # Layer toggle state
    if "layer_states" not in st.session_state:
        st.session_state.layer_states = {"dac": True}

    with col_legend:
        toggled = render_legend(st.session_state.layer_states)
        st.session_state.layer_states.update(toggled)

    with col_map:
        # Pydeck implementation
        layers = []
        if st.session_state.layer_states["dac"]:
            dac_layer = load_dac_data_pydeck(show_non_dac)
            layers.append(dac_layer)
        # Add more layers here as needed, e.g.:
        # if st.session_state.layer_states["schools"]:
        #     school_layer = load_school_locations_data()
        #     layers.append(school_layer)
        deck = get_deck(layers)
        # Display the map and capture click events
        map_data = st.pydeck_chart(
            deck,
            selection_mode="single-object",
            on_select="rerun",
            use_container_width=True,
            # height=700  # Increase map height as needed
        )

        # Display selected polygon data
        if (
            map_data
            and map_data.selection
            and hasattr(map_data.selection, "objects")
            and map_data.selection["objects"]
        ):
            print("Selected data:", map_data.selection)
            selected_object_row = list(map_data.selection["objects"].values())[0][0]
            row_no_geom = {
                k: v for k, v in selected_object_row.items() if k != "geometry"
            }
            df_display = pd.DataFrame(row_no_geom.items(), columns=["Field", "Value"])
            st.markdown("**Selected DAC Information:**")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Click on a polygon to see its details")


if __name__ == "__main__":
    main()
