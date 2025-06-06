# app.py

import streamlit as st
import geopandas as gpd
import pandas as pd
import json
import pydeck as pdk
from shapely.geometry import MultiPolygon
from datetime import datetime

# Paths
TRIP_PINGS_GEOJSON_PATH = "assets/trip_pings.geojson"
PARKS_GEOJSON_PATH = "assets/boulder_openspace_data.geojson"

# Load trip pings
@st.cache_data
def load_trip_pings():
    gdf = gpd.read_file(TRIP_PINGS_GEOJSON_PATH)
    gdf["utc_timestamp"] = pd.to_datetime(gdf["utc_timestamp"])
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    return gdf

# Load parks polygons
@st.cache_data
def load_parks():
    return gpd.read_file(PARKS_GEOJSON_PATH)

# ---- App ----

st.set_page_config(layout="wide", page_title="Park Occupancy & Use Demo")
st.title("🏞️ Park Occupancy and Use Demo")

# Load data
gdf = load_trip_pings()
parks_gdf = load_parks()

# Sidebar - Park selection
available_parks = sorted(gdf["park_name"].dropna().unique())

selected_parks = st.sidebar.multiselect(
    "Select Parks:",
    options=available_parks,
    default=available_parks
)

# Sidebar - Visitor type
visitor_options = ["All", "Visitor", "Non-Visitor"]
selected_visitor_type = st.sidebar.radio(
    "Visitor Type:",
    options=visitor_options,
    index=0
)

# Sidebar - Date range
min_date = gdf["utc_timestamp"].min().date()
max_date = gdf["utc_timestamp"].max().date()

selected_date_range = st.sidebar.date_input(
    "Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Sidebar - Active Park selector (focus + zoom)
active_park = st.sidebar.selectbox(
    "Active Park (zoom + focus):",
    options=["All"] + selected_parks,
    index=0
)

# ---- Filtering ----

# Filter by parks
filtered_gdf = gdf[gdf["park_name"].isin(selected_parks)]
filtered_parks_gdf = parks_gdf[parks_gdf["ParkGroupDescription"].isin(selected_parks)].copy()

# Filter by visitor type
if selected_visitor_type == "Visitor":
    filtered_gdf = filtered_gdf[filtered_gdf["visited_park"] == True]
elif selected_visitor_type == "Non-Visitor":
    filtered_gdf = filtered_gdf[filtered_gdf["visited_park"] == False]

# Filter by date
start_date, end_date = selected_date_range
filtered_gdf = filtered_gdf[
    (filtered_gdf["utc_timestamp"].dt.date >= start_date) &
    (filtered_gdf["utc_timestamp"].dt.date <= end_date)
]

# ---- Prepare parks polygons ----

# # Clean geometries (buffer(0))
# filtered_parks_gdf["geometry"] = filtered_parks_gdf["geometry"].buffer(0)

# # Force all to MultiPolygon
# filtered_parks_gdf["geometry"] = filtered_parks_gdf["geometry"].apply(
#     lambda geom: MultiPolygon([geom]) if geom.geom_type == "Polygon" else geom
# )

# ---- Apply Active Park Focus ----

if active_park != "All":
    focus_parks_gdf = filtered_parks_gdf[filtered_parks_gdf["ParkGroupDescription"] == active_park]
    focus_gdf = filtered_gdf[filtered_gdf["park_name"] == active_park]
else:
    focus_parks_gdf = filtered_parks_gdf
    focus_gdf = filtered_gdf

# ---- Park Details Expander ----

with st.sidebar.expander("ℹ️ Park Details", expanded=False):

    if active_park != "All":
        # Show info for the active park
        park_row = filtered_parks_gdf[filtered_parks_gdf["ParkGroupDescription"] == active_park]

        if not park_row.empty:
            row = park_row.iloc[0]
            st.markdown(f"**Park Name:** {row['ParkGroupDescription']}")
            st.markdown(f"**Acreage:** {row.get('Acreage', 'Unknown')} acres")
            st.markdown(f"**Contact:** [Link]({row.get('Contact', '#')})")
            st.markdown(f"**GlobalID:** `{row.get('GlobalID', '')}`")
            # You can add more fields here as needed!
        else:
            st.info("No data available for selected park.")
    else:
        st.info("Select a park to view details.")

# ---- Map ----

st.subheader("📍 Trip Pings + Park Polygons Map")

# Park polygons layer
polygon_layer = pdk.Layer(
    "GeoJsonLayer",
    data=json.loads(focus_parks_gdf.to_json()),
    stroked=True,
    filled=True,
    get_fill_color=[120, 200, 120, 120],
    get_line_color=[0, 100, 0, 200],
    line_width_min_pixels=1,
    pickable=True
)

# Trip points layer
points_layer = pdk.Layer(
    "ScatterplotLayer",
    data=focus_gdf,
    get_position=["lon", "lat"],
    get_color="[255, 140, 0, 180]",
    get_radius=50,
    pickable=True
)

# Initial view
if not focus_gdf.empty:
    view_state = pdk.ViewState(
        latitude=focus_gdf["lat"].mean(),
        longitude=focus_gdf["lon"].mean(),
        zoom=12 if active_park != "All" else 10,
        pitch=0
    )
else:
    view_state = pdk.ViewState(latitude=40.0, longitude=-105.3, zoom=9)

# Render map
st.pydeck_chart(pdk.Deck(
    initial_view_state=view_state,
    layers=[polygon_layer, points_layer],
    map_style="mapbox://styles/mapbox/light-v9",
    tooltip={
        "html": "<b>Park:</b> {ParkGroupDescription}",
        "style": {"color": "black"}
    }
))

# ---- Trip statistics table ----

st.subheader("📊 Trip Statistics Table")

trip_stats = (
    focus_gdf
    .groupby(["ad_id", "park_name", "visited_park"])
    .agg(
        num_pings=("utc_timestamp", "count"),
        first_ping=("utc_timestamp", "min"),
        last_ping=("utc_timestamp", "max")
    )
    .reset_index()
)

st.dataframe(trip_stats)

# ---- Park Summary Table ----

st.subheader("🏞️ Park Summary Table")

park_summary = (
    focus_gdf
    .groupby("park_name")
    .agg(
        num_visitors=("ad_id", "nunique"),
        num_pings=("utc_timestamp", "count"),
        first_ping=("utc_timestamp", "min"),
        last_ping=("utc_timestamp", "max")
    )
    .reset_index()
    .sort_values("num_visitors", ascending=False)
)

st.dataframe(park_summary)

# ---- Footer ----
st.markdown("---")
st.markdown(
    "Demo App • Synthetic Data • Reprocessor Pipeline • Streamlit + Pydeck + GeoPandas"
)
