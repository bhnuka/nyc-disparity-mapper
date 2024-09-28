import sys
import os
import geopandas as gpd
import folium
import webbrowser
import pandas as pd

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Use the resource_path function for all your data files
precincts = gpd.read_file(resource_path('Police Precincts/geo_export_285d695e-252a-4bd6-b18d-ab8f95aa63f9.shp'))
data = pd.read_csv(resource_path('nyc-data.csv'))
zipcodes = gpd.read_file(resource_path('MODZCTA/geo_export_953eebb2-7abd-4e3f-9628-39d0237055a1.shp'))

# Convert 'modzcta' in zipcodes and 'zip' in data to strings
zipcodes['modzcta'] = zipcodes['modzcta'].astype(str)
data['zip'] = data['zip'].astype(str)

# Merge the zipcode shapefile with your data
zipcodes = zipcodes.merge(data, left_on='modzcta', right_on='zip', how='left')

# Create a base map centered on NYC with white background
m = folium.Map(location=[40.7128, -74.0060], zoom_start=11, tiles=None)
folium.TileLayer('cartodbpositron', name='Light Map', overlay=False, control=False).add_to(m)

# Create a mask for the five boroughs
nyc_boundary = zipcodes.dissolve()

# Add the mask to the map
folium.GeoJson(
    nyc_boundary,
    style_function=lambda x: {
        'fillColor': 'white',
        'color': 'white',
        'weight': 1,
        'fillOpacity': 1,
    },
    overlay=False,
    control=False
).add_to(m)

# List of columns to create choropleth layers for
columns = ['home_value', 'gentrifying_rate', 'age_median', 'commute_time', 'education_college_or_above',
           'family_size', 'income_household_median', 'male', 'married',
           'race_white', 'race_black', 'race_asian']


# Function to create a choropleth layer
def create_choropleth(column):
    return folium.Choropleth(
        geo_data=zipcodes,
        name=column.replace('_', ' ').title(),
        data=zipcodes,
        columns=['zip', column],
        key_on='feature.properties.modzcta',
        fill_color='YlOrRd',
        fill_opacity=0.3,
        line_opacity=0,
        legendname=column.replace('', ' ').title()
    )


# Create and add choropleth layers
for column in columns:
    create_choropleth(column).add_to(m)

# Add precincts to the map as a permanent top layer
folium.GeoJson(
    precincts,
    name='Police Precincts',
    tooltip=folium.GeoJsonTooltip(fields=['precinct'], aliases=['Precinct:'], sticky=True),
    style_function=lambda feature: {
        'fillColor': 'transparent',
        'color': 'black',  # Changed to black for precinct boundaries
        'weight': 0.5,  # Increased weight to make boundaries more visible
        'fillOpacity': 0,
    }
).add_to(m)

# Add layer control for choropleth layers
folium.LayerControl().add_to(m)

# Save the map to an HTML file in a location accessible to the executable
html_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(), 'nyc_demographics_and_precincts.html')
m.save(html_file)

# Automatically open the HTML file in the default web browser
webbrowser.open('file://' + html_file)
