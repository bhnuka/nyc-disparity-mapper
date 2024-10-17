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

# Function to create a folium map
def create_map(name, columns):
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

    # Function to create a choropleth layer
    def create_choropleth(column):
        choro = folium.Choropleth(
            geo_data=zipcodes,
            name=column.replace('_', ' ').title(),
            data=zipcodes,
            columns=['zip', column],
            key_on='feature.properties.modzcta',
            fill_color='YlOrRd',
            fill_opacity=1,
            line_opacity=0,
            overlay=False,
            show=False  # Ensure the overlay is turned off by default
        )
        for key in choro._children:
            if key.startswith('color_map'):
                del (choro._children[key])
        return choro

    # Create and add choropleth layers
    for column in columns:
        create_choropleth(column).add_to(m)

    # Add layer control with exclusive groups for choropleth layers
    folium.LayerControl(collapsed=False, exclusiveGroups=columns).add_to(m)

    # Save the map to an HTML file
    html_file = os.path.join(os.getcwd(), f'{name}.html')
    m.save(html_file)

# Define two sets of columns for two different maps
columns_map = ['home_value', 'gentrifying_rate', 'age_median', 'commute_time', 'education_college_or_above',
           'family_size', 'income_household_median', 'male', 'married',
           'race_white', 'race_black', 'race_asian']

# Create two maps
create_map('map1', columns_map)
create_map('map2', columns_map)

# Create a combined HTML file
combined_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NYC Demographics and Precincts</title>
    <style>
        .container {
            display: flex;
        }
        .map {
            width: 50%;
            height: 600px;
        }
        iframe {
            width: 100%;
            height: 100%;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="map">
            <iframe src="map1.html" frameborder="0"></iframe>
        </div>
        <div class="map">
            <iframe src="map2.html" frameborder="0"></iframe>
        </div>
    </div>
</body>
</html>
"""

# Save the combined HTML file
with open('combined_maps.html', 'w') as f:
    f.write(combined_html)

# Automatically open the combined HTML file in the default web browser
webbrowser.open('file://' + os.path.join(os.getcwd(), 'combined_maps.html'))





