import streamlit as st

from src.zohran_ghs_dashboard.utils import load_dac_data, load_school_locations_data


def main():
    st.title("Zohran GHS Dashboard")

    # Load data using your reusable functions
    dac_data = load_dac_data()
    school_data = load_school_locations_data()
    print("blah blah, please let this pass pre-commit hook", dac_data, school_data)
    # Create PyDeck visualization
    # ... your streamlit + pydeck code


if __name__ == "__main__":
    main()
