# app.py

import streamlit as st
import geopandas as gpd
import pandas as pd
import json
import pydeck as pdk
import altair as alt
from shapely.geometry import MultiPolygon
from datetime import datetime

# Paths
TRIP_PINGS_GEOJSON_PATH = "assets/trip_pings.geojson"
PARKS_GEOJSON_PATH = "assets/boulder_openspace_data.geojson"
PARK_INFO_JSON_PATH = "assets/park_info.json"

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

# Load park metadata
@st.cache_data
def load_park_info():
    with open(PARK_INFO_JSON_PATH, "r") as f:
        park_info = json.load(f)
    return park_info

# ---- App ----

st.set_page_config(layout="wide", page_title="Park Occupancy & Use Demo")

st.markdown("""
    <style>
    div.block-container {
    padding-top: 1rem !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0rem !important;
    }
    /* Sidebar labels → white */
    section[data-testid="stSidebar"] label {
        color: white !important;
    }

    /* Sidebar expander header → white */
    section[data-testid="stSidebar"] .st-expanderHeader {
        color: white !important;
    }

    /* Expander header headings → white */
    section[data-testid="stSidebar"] .st-expanderHeader h1,
    section[data-testid="stSidebar"] .st-expanderHeader h2,
    section[data-testid="stSidebar"] .st-expanderHeader h3,
    section[data-testid="stSidebar"] .st-expanderHeader h4,
    section[data-testid="stSidebar"] .st-expanderHeader h5,
    section[data-testid="stSidebar"] .st-expanderHeader h6 {
        color: white !important;
    }

    /* Sidebar expander content (Park Details) → white */
    section[data-testid="stSidebar"] .stMarkdown {
        color: white !important;
    }

    /* Brighten pydeck tooltip */
    .deck-tooltip {
        background-color: rgba(255, 255, 255, 0.9) !important;
        color: black !important;
        font-size: 13px;
        border-radius: 4px;
        padding: 6px 10px;
        box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.3);
    }
    </style>
""", unsafe_allow_html=True)






# Sidebar logo with link
# sidebar logo
# Load image as base64
import base64

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()
    return encoded

img_base64 = get_base64_image("assets/aktiv_wordmark.png")

# Sidebar logo with clickable link
st.sidebar.markdown(
    f"""
    <a href="https://www.aktiv-insights.dev" target="_blank">
        <img src="data:image/png;base64,{img_base64}" style="width: 100%; border-radius: 5px;" />
    </a>
    """,
    unsafe_allow_html=True
)

st.title("🏞️ Park Occupancy and Use Demo")

# Load data
gdf = load_trip_pings()
parks_gdf = load_parks()
park_info = load_park_info()

# Sidebar - Park selection
available_parks = sorted(gdf["park_name"].dropna().unique())

selected_parks = st.sidebar.multiselect(
    "Select Parks:",
    options=available_parks,
    default=available_parks
)

# Sidebar - Visitor type
# visitor_options = ["All", "Visitor", "Non-Visitor"]
# selected_visitor_type = st.sidebar.radio(
#     "Visitor Type:",
#     options=visitor_options,
#     index=0
# )

# Sidebar - Date range
min_date = gdf["utc_timestamp"].min().date()
max_date = gdf["utc_timestamp"].max().date()

selected_date_range = st.sidebar.date_input(
    "Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if selected_date_range and len(selected_date_range) == 2 and all(selected_date_range):
    start_date, end_date = selected_date_range
else:
    st.info("Please select both a start and end date.")
    st.stop()

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
selected_visitor_type = "Visitor"  # Default to Visitor for now
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

# Clean geometries (buffer(0))
# filtered_parks_gdf["geometry"] = filtered_parks_gdf["geometry"].buffer(0)

# # Explode polygons
# exploded_parks_gdf = filtered_parks_gdf.explode(index_parts=True).reset_index(drop=True)

# ---- Apply Active Park Focus ----

# # Capture polygon click and update active_park if clicked
# clicked_park = st.session_state.get("clicked_park")
# if "clicked_park" in st.session_state:
#     active_park = st.session_state["clicked_park"]

if active_park != "All":
    focus_parks_gdf = filtered_parks_gdf[filtered_parks_gdf["ParkGroupDescription"] == active_park]
    focus_gdf = filtered_gdf[filtered_gdf["park_name"] == active_park]
else:
    focus_parks_gdf = filtered_parks_gdf
    focus_gdf = filtered_gdf

# ---- Park Details Expander ----

with st.sidebar.expander("ℹ️", expanded=False):

    if active_park != "All":
        # Get park row from GeoDataFrame
        park_row = filtered_parks_gdf[filtered_parks_gdf["ParkGroupDescription"] == active_park]

        if not park_row.empty:
            row = park_row.iloc[0]
            global_id = row.get("GlobalID", "")

            # Lookup in park_info
            info = park_info.get(global_id, None)

            if info:
                st.markdown(f"**Park Name:** {info['ParkName']}")
                st.markdown(f"**Acreage:** {info['Acreage']} acres")
                st.markdown(f"**Contact:** [Link]({info['Contact']})")
                st.markdown(f"**Allows Dogs:** {info['AllowsDogs']}")
                st.markdown(f"**Activities:** {', '.join(info['Activities'])}")
                st.markdown(f"**Restrooms:** {'Yes' if info['Restrooms'] else 'No'}")
                st.markdown(f"**ADA Access:** {'Yes' if info['ADA_Access'] else 'No'}")
                st.markdown(f"**Parking Spots:** {info['NumParkingSpots']}")

                # Trails
                st.markdown("**Trails:**")
                for trail in info.get("Trails", []):
                    st.markdown(f"- {trail['TrailName']} ({trail['TrailRating']}, {trail['MilesTrail']} mi)")

            else:
                st.warning("No rich info available for this park.")
        else:
            st.info("No data available for selected park.")
    else:
        st.info("Select a park to view details.")

# ---- Map ----

st.subheader("📍 Trip Pings + Park Polygons Map")

polygon_layer = pdk.Layer(
    "GeoJsonLayer",
    data=json.loads(focus_parks_gdf.to_json()),
    stroked=True,
    filled=True,
    get_fill_color=[255, 140, 0, 180],
    get_line_color=[255, 140, 0, 180],
    line_width_min_pixels=1,
    pickable=True,
    auto_highlight=True
)


points_layer = pdk.Layer(
    "ScatterplotLayer",
    data=focus_gdf,
    get_position=["lon", "lat"],
    get_color="[20, 185, 255, 255]",
    get_radius=10,
    pickable=True
)

if not focus_gdf.empty:
    view_state = pdk.ViewState(
        latitude=focus_gdf["lat"].mean(),
        longitude=focus_gdf["lon"].mean(),
        zoom=14 if active_park != "All" else 10,
        pitch=0
    )
else:
    view_state = pdk.ViewState(latitude=40.0, longitude=-105.3, zoom=9)

st.pydeck_chart(pdk.Deck(
    initial_view_state=view_state,
    layers=[polygon_layer, points_layer],
    map_style="mapbox://styles/mapbox/satellite-streets-v12",
    tooltip={
        "html": "{ParkGroupDescription}",
        "style": {"color": "black"}
    }
))

# ---- Split layout: tables on left, graphs on right ----

col1, col2 = st.columns([2, 1])  # left wider, right smaller

# ---- LEFT COLUMN: Tables ----

with col1:
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
    park_summary["first_ping"] = park_summary["first_ping"].dt.strftime("%Y-%m-%d %H:%M")
    park_summary["last_ping"] = park_summary["last_ping"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(park_summary)

    st.subheader("📊 Trip Statistics Table")

    trip_stats = (
        focus_gdf
        .groupby(["ad_id", "park_name"])
        .agg(
            num_pings=("utc_timestamp", "count"),
            first_ping=("utc_timestamp", "min"),
            last_ping=("utc_timestamp", "max")
        )
        .reset_index()
    )
    trip_stats["first_ping"] = trip_stats["first_ping"].dt.strftime("%Y-%m-%d %H:%M")
    trip_stats["last_ping"] = trip_stats["last_ping"].dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(trip_stats)



# ---- RIGHT COLUMN: Graphs ----

with col2:
# Seasonal Use — this is working
    st.subheader("📈 Seasonal Use, 2024")

    if active_park != "All" and "VisitStats" in info:
        seasonal_df = pd.DataFrame({
            "Season": ["Winter", "Spring", "Summer", "Fall"],
            "Visits": [
                info["VisitStats"]["Winter"],
                info["VisitStats"]["Spring"],
                info["VisitStats"]["Summer"],
                info["VisitStats"]["Fall"]
            ]
        })

        bar_chart = alt.Chart(seasonal_df).mark_bar(color="#FFBB33").encode(
            x=alt.X("Season", sort=["Winter", "Spring", "Summer", "Fall"]),
            y="Visits"
        ).properties(width=250, height=200)

        st.altair_chart(bar_chart, use_container_width=True)

    else:
        st.info("Select a park to view seasonal graph.")

    # ---- NEW container ----

    st.subheader("📈 Annual Use, YoY")

    if active_park != "All" and "VisitStats" in info:
        annual_df = pd.DataFrame({
            "Year": [2022, 2023, 2024],  # integers           
            "Visits": [
                info["VisitStats"]["Total_2022"],
                info["VisitStats"]["Total_2023"],
                info["VisitStats"]["Total_2024"]
            ]
        })

        print(annual_df)

        line_chart = alt.Chart(annual_df).mark_line(point=True, color="#14B9FF").encode(
            x=alt.X("Year:O", title="Year"),
            y=alt.Y("Visits", title="Estimated Visits", scale=alt.Scale(zero=False))
        ).properties(width=250, height=250)  # Force height a bit larger

        st.altair_chart(line_chart, use_container_width=True)

    else:
        st.info("Select a park to view annual graph.")

# ---- Footer ----
st.markdown("---")

with st.expander("📚 Sources & Notes"):
    st.markdown("""
    - This demo uses synthetic location/visitation data for demonstration purposes.
    - Park geometries: Boulder County Open Space GIS
    - Visit statistics: Publicly reported counter data (https://assets.bouldercounty.gov/wp-content/uploads/2025/04/annual-visitation-report-2024.pdf).
    - Synthetic mobility traces generated by reprocessor script.
    """)

st.markdown(
    "Demo App • Synthetic Data • Reprocessor Pipeline • Streamlit + Pydeck + GeoPandas + Altair"
)