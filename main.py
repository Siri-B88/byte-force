import ee
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- INITIALIZATION ---

# Load environment variables from .env file
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")

# Initialize the FastAPI app
app = FastAPI(title="HealthyCity API")

# Add CORS middleware to allow requests from your Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Authenticate and initialize Google Earth Engine
try:
    if not GOOGLE_CLOUD_PROJECT:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")
    ee.Initialize(project=GOOGLE_CLOUD_PROJECT)
    print("✅ Google Earth Engine Initialized Successfully.")
except Exception as e:
    print(f"❌ ERROR: Google Earth Engine failed to initialize. Details: {e}")
    # You might want to handle this more gracefully in a real app
    # For now, we print the error and continue, but GEE-dependent endpoints will fail.


# --- HELPER FUNCTIONS ---

def get_city_coords(city_name: str):
    """Get latitude and longitude for a city using OpenWeatherMap Geocoding API."""
    if not OPENWEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenWeatherMap API key is not configured on the server.")
    geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={OPENWEATHER_API_KEY}"
    response = requests.get(geo_url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to connect to Geocoding service.")
    
    data = response.json()
    if not data:
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found.")
    
    return data[0]["lat"], data[0]["lon"]


# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the HealthyCity API. See /docs for endpoint details."}


@app.get("/city/{city}/green")
def get_green_cover(city: str):
    """
    Calculates the average Normalized Difference Vegetation Index (NDVI) for a city
    using Sentinel-2 satellite imagery.
    """
    try:
        lat, lon = get_city_coords(city)
        point = ee.Geometry.Point(lon, lat)
        region = point.buffer(2000)  # 2km buffer around the city center

        # Use Sentinel-2 imagery, filter for recent, low-cloud images
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                      .filterBounds(region)
                      .filterDate('2023-01-01', '2023-12-31')
                      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                      .sort('CLOUDY_PIXEL_PERCENTAGE'))

        image = collection.first() # Get the clearest image

        # Calculate NDVI: (NIR - Red) / (NIR + Red)
        # For Sentinel-2, NIR is band B8, Red is band B4
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # Calculate the average NDVI in the region
        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=10,
            maxPixels=1e9
        )
        
        avg_ndvi = stats.get('NDVI').getInfo()
        if avg_ndvi is None:
            raise HTTPException(status_code=404, detail=f"Could not compute NDVI for {city}. No clear satellite imagery might be available.")
        
        # Simple conversion to a percentage-like score
        green_cover_percentage = (avg_ndvi + 1) * 50

        return {
            "city": city.title(),
            "location": {"lat": lat, "lon": lon},
            "avg_ndvi": avg_ndvi,
            "green_cover_percentage": green_cover_percentage,
            "data_source": "Copernicus Sentinel-2",
        }
    except HTTPException as e:
        raise e # Re-raise HTTPException from get_city_coords
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred with Google Earth Engine: {str(e)}")


@app.get("/city/{city}/heatmap")
def get_heat_map(city: str):
    """
    Calculates the average Land Surface Temperature (LST) for a city using Landsat 8.
    """
    try:
        lat, lon = get_city_coords(city)
        point = ee.Geometry.Point(lon, lat)
        region = point.buffer(2000)

        # Use Landsat 8 imagery
        collection = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                      .filterBounds(region)
                      .filterDate('2023-01-01', '2023-12-31')
                      .filter(ee.Filter.lt('CLOUD_COVER', 20))
                      .sort('CLOUD_COVER'))

        image = collection.first()
        
        # Select thermal band (Band 10), apply scale factor, and convert from Kelvin to Celsius
        lst = (image.select('ST_B10')
               .multiply(0.00341802)
               .add(149.0)
               .subtract(273.15)
               .rename('LST_Celsius'))

        stats = lst.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=30,
            maxPixels=1e9
        )
        
        avg_lst_celsius = stats.get('LST_Celsius').getInfo()
        if avg_lst_celsius is None:
            raise HTTPException(status_code=404, detail=f"Could not compute LST for {city}. No clear satellite imagery might be available.")

        return {
            "city": city.title(),
            "location": {"lat": lat, "lon": lon},
            "avg_lst_celsius": avg_lst_celsius,
            "data_source": "USGS Landsat 8",
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred with Google Earth Engine: {str(e)}")

