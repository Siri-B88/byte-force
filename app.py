import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="HealthyCity Dashboard",
    page_icon="🌍",
    layout="wide",
)

# --- BACKEND API URL ---
# This is the address of your running FastAPI server.
API_BASE_URL = "http://127.0.0.1:8000"


# --- HELPER FUNCTIONS ---
def get_city_data(city, analysis_type):
    """
    Calls the backend API to fetch the requested data for a city.
    'analysis_type' can be 'green' or 'heatmap'.
    """
    endpoint_map = {
        "Green Cover": "green",
        "Heat Map": "heatmap",
    }
    endpoint = endpoint_map.get(analysis_type)
    if not endpoint:
        return {"error": "Invalid analysis type selected."}

    try:
        url = f"{API_BASE_URL}/city/{city}/{endpoint}"
        # Set a long timeout because Google Earth Engine can be slow
        response = requests.get(url, timeout=120)
        response.raise_for_status()  # This will raise an exception for 4XX/5XX errors
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": f"Connection Error: Could not connect to the backend at {API_BASE_URL}. Please ensure the server is running."}
    except requests.exceptions.Timeout:
        return {"error": "The request to the backend timed out. The server might be busy or the request is complex."}
    except requests.exceptions.RequestException as e:
        # For other errors, like 404 Not Found if the city isn't in OpenWeatherMap
        error_data = e.response.json() if e.response else {}
        detail = error_data.get("detail", str(e))
        return {"error": f"API Error: {detail}"}

# --- UI & STATE MANAGEMENT ---

# Initialize session state variables if they don't exist to hold data
if 'city' not in st.session_state:
    st.session_state.city = ""
if 'analysis_type' not in st.session_state:
    st.session_state.analysis_type = "Green Cover"
if 'map_data' not in st.session_state:
    st.session_state.map_data = None
if 'metrics' not in st.session_state:
    st.session_state.metrics = None
if 'error' not in st.session_state:
    st.session_state.error = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("🌍 HealthyCity Dashboard")
    st.info(
        "Real-time environmental insights for global cities, "
        "powered by Google Earth Engine."
    )

    # Use a form to group the input and button for a cleaner look
    with st.form("city_form"):
        city_input = st.text_input("Enter a city:", value=st.session_state.city)
        submitted = st.form_submit_button("Analyze City")

    st.session_state.analysis_type = st.radio(
        "Select an Analysis",
        ("Green Cover", "Heat Map", "Flood Risk", "Air Quality", "Report Card"),
    )

# --- DATA FETCHING LOGIC ---
# If the form was submitted, update the city and fetch new data
if submitted and city_input:
    st.session_state.city = city_input
    st.session_state.map_data = None # Clear old data
    st.session_state.metrics = None
    st.session_state.error = None

    # Show a spinner while the data is being fetched
    with st.spinner(f"Analyzing {st.session_state.analysis_type} for {st.session_state.city}... This may take a moment."):
        data = get_city_data(st.session_state.city, st.session_state.analysis_type)
        if "error" in data:
            st.session_state.error = data["error"]
        else:
            # Store the fetched data in the session state
            st.session_state.metrics = data
            st.session_state.map_data = data.get("location")


# --- MAIN PAGE CONTENT ---

# Set the title based on the selected analysis
if st.session_state.analysis_type == "Green Cover":
    st.header("🌳 Urban Green Cover")
    st.markdown("Analyzing Normalized Difference Vegetation Index (NDVI) to assess vegetation health and coverage using Sentinel-2 satellite imagery.")
elif st.session_state.analysis_type == "Heat Map":
    st.header("🔥 Urban Heat Map")
    st.markdown("Analyzing Land Surface Temperature (LST) to identify heat islands using thermal bands from Landsat 8 satellite.")
else:
    # For pages that are not built yet
    st.header(f"📊 {st.session_state.analysis_type}")
    st.warning("This feature is under construction. Please check back later!")
    st.stop() # Stop the script for placeholder pages

# Display an error message on the main page if one occurred
if st.session_state.error:
    st.error(st.session_state.error)

# --- METRICS & MAP DISPLAY ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Metrics")
    # Show metrics only if they have been successfully fetched
    if st.session_state.metrics:
        if st.session_state.analysis_type == "Green Cover":
            st.metric(
                label="Average Green Cover",
                value=f"{st.session_state.metrics.get('green_cover_percentage', 0):.2f}%"
            )
            st.metric(
                label="Average NDVI",
                value=f"{st.session_state.metrics.get('avg_ndvi', 0):.4f}"
            )
        elif st.session_state.analysis_type == "Heat Map":
            st.metric(
                label="Average Surface Temp.",
                value=f"{st.session_state.metrics.get('avg_lst_celsius', 0):.2f} °C"
            )
    else:
        st.info("Search for a city to see its metrics.")

with col2:
    st.subheader("City Location")
    # Show the map only if location data exists
    if st.session_state.map_data:
        lat = st.session_state.map_data['lat']
        lon = st.session_state.map_data['lon']

        # Create the Folium map object
        m = folium.Map(location=[lat, lon], zoom_start=12)
        folium.Marker(
            [lat, lon],
            popup=f"{st.session_state.city.title()}",
            tooltip=f"{st.session_state.city.title()}"
        ).add_to(m)

        # Display the map in the Streamlit app
        st_folium(m, width=700, height=450, returned_objects=[])
    else:
        st.info("Map will be displayed here once data is loaded.")

