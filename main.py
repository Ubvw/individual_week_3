import os
import geopandas as gpd

print("Starting!")
# Get absolute path to this script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Build path to your shapefile
shapefile_path = os.path.join(script_dir, "Bataan", "PH030800000_FH_5yr.shp")

# Load the shapefile
gdf = gpd.read_file(shapefile_path)

# Reproject to WGS84 (EPSG:4326) for Leaflet
gdf = gdf.to_crs(epsg=4326)

# Path for the output GeoJSON — here, in the script's directory
output_path = os.path.join(script_dir, "flood_prone.geojson")
gdf.to_file(output_path, driver="GeoJSON")

print(f"✅ GeoJSON saved at: {output_path}")