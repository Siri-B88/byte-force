import ee
import random

# Initialize GEE
ee.Initialize()

# Function to get average temperature (Heat Map)
def get_heatmap(lat, lon):
    point = ee.Geometry.Point([lon, lat])
    # Example using MODIS LST
    lst = ee.ImageCollection("MODIS/006/MOD11A1") \
          .select("LST_Day_1km") \
          .filterDate('2025-01-01', '2025-01-31') \
          .mean() \
          .sample(region=point, scale=1000).first() \
          .get('LST_Day_1km').getInfo()
    return {"avg_temp": lst/10}  # Convert to °C

# Function to get green cover (NDVI)
def get_ndvi(lat, lon):
    point = ee.Geometry.Point([lon, lat])
    ndvi = ee.ImageCollection("COPERNICUS/S2") \
           .filterBounds(point) \
           .filterDate('2025-01-01', '2025-01-31') \
           .map(lambda img: img.normalizedDifference(['B8','B4']).rename('NDVI')) \
           .mean() \
           .sample(region=point, scale=10).first() \
           .get('NDVI').getInfo()
    return {"green_pct": ndvi*100}

# Function to get flood risk
def get_flood_risk(lat, lon):
    # Simplified demo: combine DEM + rainfall
    return {"flood_score": random.uniform(0,1)}
