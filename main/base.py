import sys
import json
import os
import geopandas as gpd
import folium
import webbrowser
import pandas as pd
from jinja2 import Template


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Load the combined redline JSON
with open('redlining/combined_nyc_redline.json', 'r') as f:
    redline_data = json.load(f)

# Use the resource_path function for all your data files
precincts = gpd.read_file(resource_path('Police Precincts/geo_export_285d695e-252a-4bd6-b18d-ab8f95aa63f9.shp'))
data_2011 = pd.read_csv(resource_path('nyc-data-2011.csv'))
data_2016 = pd.read_csv(resource_path('nyc-data-2016.csv'))
data_2022 = pd.read_csv(resource_path('nyc-data-2022.csv'))
zipcodes = gpd.read_file(resource_path('MODZCTA/geo_export_953eebb2-7abd-4e3f-9628-39d0237055a1.shp'))

# Load Stop and Frisk data
stop_frisk_2011 = pd.read_csv('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2011.csv')
stop_frisk_2016 = pd.read_csv('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2016.csv')
stop_frisk_2022 = pd.read_csv('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2022.csv')


# Function to clean and convert 'Precinct' column
def clean_precinct(df):
    # Convert to float first (to handle NaN values), then to int
    df['Precinct'] = pd.to_numeric(df['Precinct'], errors='coerce').astype('Int64')

    # Drop rows with NaN values in 'Precinct'
    df = df.dropna(subset=['Precinct'])

    return df


# Clean and convert 'Precinct' column for all datasets
stop_frisk_2011 = clean_precinct(stop_frisk_2011)
stop_frisk_2016 = clean_precinct(stop_frisk_2016)
stop_frisk_2022 = clean_precinct(stop_frisk_2022)

# Convert 'precinct' column in precincts to integer
precincts['precinct'] = pd.to_numeric(precincts['precinct'], errors='coerce').astype('Int64')

# Merge Stop and Frisk data with precincts
precincts = precincts.merge(stop_frisk_2011, left_on='precinct', right_on='Precinct', how='left')
precincts = precincts.merge(stop_frisk_2016, left_on='precinct', right_on='Precinct', how='left',
                            suffixes=('_2011', '_2016'))
precincts = precincts.merge(stop_frisk_2022, left_on='precinct', right_on='Precinct', how='left')
precincts = precincts.rename(columns={'Black Stopped Rate': 'Black Stopped Rate_2022'})

# Convert 'modzcta' in zipcodes and 'ZCTA' in data to strings
zipcodes['modzcta'] = zipcodes['modzcta'].astype(str)
data_2011['ZCTA'] = data_2011['ZCTA'].astype(str)
data_2016['ZCTA'] = data_2016['ZCTA'].astype(str)
data_2022['ZCTA'] = data_2022['ZCTA'].astype(str)

# Merge the zipcode shapefile with your data
zipcodes_2011 = zipcodes.merge(data_2011, left_on='modzcta', right_on='ZCTA', how='left')
zipcodes_2016 = zipcodes.merge(data_2016, left_on='modzcta', right_on='ZCTA', how='left')
zipcodes_2022 = zipcodes.merge(data_2022, left_on='modzcta', right_on='ZCTA', how='left')


# Function to create a folium map and return its HTML
def create_map_html(columns, zipcodes_data, precincts_data, year):
    # Create a base map centered on NYC with white background
    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=11,
        tiles=None,
        control_scale=True,
        width="50vw",
        height="100vh"
    )

    # Set map size to 100%
    m._size = ("50vw", "100vh")

    folium.TileLayer(
        'cartodbpositron',
        name='Light Map',
        overlay=False,
        control=False
    ).add_to(m)

    # Create a mask for the five boroughs
    nyc_boundary = zipcodes_data.dissolve()

    # Add the mask to the map
    folium.GeoJson(
        nyc_boundary,
        style_function=lambda x: {
            'fillColor': 'white',
            'color': 'white',
            'weight': 1,
            'fillOpacity': 0,
        },
        overlay=False,
        control=False
    ).add_to(m)

    # Create a custom pane for Redlining Overlay
    redlining_pane = folium.map.CustomPane("redliningPane", z_index=650)
    m.add_child(redlining_pane)

    # Add the redline JSON data as an overlay to the custom pane
    folium.GeoJson(
        redline_data,
        name='Redlining Overlay',
        style_function=lambda feature: {
            'fillColor': feature['properties'].get('fill', '#ff0000'),
            'color': 'black',
            'weight': 0,
            'fillOpacity': 0.7,
        },
        pane="redliningPane"  # Assign to the custom pane
    ).add_to(m)

    # Function to create a choropleth layer
    def create_choropleth(column, data, is_precinct=False):

        if is_precinct:
            geo_data = precincts_data
            key_on = 'feature.properties.precinct'
            if column.startswith('Black Stopped Rate'):
                layer_name = f"Black Stopped Rate"
            elif column == 'Public Schools':
                layer_name = f"Public Schools"
            elif column == 'Parks':
                layer_name = f"Parks"
            else:
                layer_name = f"{column.replace('_', ' ').title()}"
        else:
            geo_data = zipcodes_data
            key_on = 'feature.properties.modzcta'
            layer_name = f"{column.replace('_', ' ').title()}"

        choro = folium.Choropleth(
            geo_data=geo_data,
            name=layer_name,
            data=data,
            columns=['ZCTA' if not is_precinct else 'Precinct', column],
            key_on=key_on,
            fill_color='YlOrRd',
            fill_opacity=0.5,
            line_opacity=0,
            overlay=False,
            show=False  # Ensure the overlay is turned off by default
        ).add_to(m)

        # Remove the color map added by folium's Choropleth
        for key in choro._children:
            if key.startswith('color_map'):
                del (choro._children[key])

        return choro

    # Create and add choropleth layers
    for column in columns:
        if column.startswith('Black Stopped Rate') or column in ['Public Schools', 'Parks']:
            create_choropleth(column, precincts_data, is_precinct=True).add_to(m)
        else:
            create_choropleth(column, zipcodes_data).add_to(m)

    # Add layer control with exclusive groups for choropleth layers
    folium.LayerControl(collapsed=False, exclusiveGroups=columns).add_to(m)

    # Get the HTML but modify it to use relative sizing
    html = m.get_root().render()
    # Remove any fixed width/height settings that might be injected
    html = html.replace('width: 100.0%', 'width: 50vw')
    html = html.replace('height: 100.0%', 'height: 100vh')
    return html



# Define columns for the maps
base_columns = ['Median Home Value', "Bachelors degree or higher", 'Population', 'White',
                'Black or African American', 'Asian', 'Median Household Income']

# Define year-specific columns
columns_2011 = base_columns + ['Black Stopped Rate_2011', 'Public Schools', 'Parks']
columns_2016 = base_columns + ['Black Stopped Rate_2016', 'Public Schools', 'Parks']
columns_2022 = base_columns + ['Black Stopped Rate_2022', 'Public Schools', 'Parks']

# Create the maps' HTML
map_html_2011 = create_map_html(columns_2011, zipcodes_2011, precincts, '2011')
map_html_2016 = create_map_html(columns_2016, zipcodes_2016, precincts, '2016')
map_html_2022 = create_map_html(columns_2022, zipcodes_2022, precincts, '2022')

# Template for the combined HTML file
combined_html_template = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            display: flex;
        }

        .map-container {
            width: 50vw;
            height: 100vh;
            position: relative;
        }

        .header-container {
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background-color: white;
            padding: 5px 15px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            font-family: Arial, sans-serif;
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .year-label {
            font-size: 16px;
            font-weight: bold;
        }

        .active-layer {
            font-size: 14px;
            color: #666;
            font-style: italic;
        }

        .legend-container {
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background-color: white;
            padding: 5px; /* Smaller padding */
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            font-family: Arial, sans-serif;
            font-size: 12px; /* Smaller font size */
            text-align: center; /* Center the text */
            max-width: 300px; /* Limit the width */
        }

        .legend-container img {
            background-color: transparent; /* Ensure transparent background */
            width: 100%; /* Scale down further */
            height: auto;
            display: block;
            margin: 5px auto; /* Center the image and reduce margin */
        }

        .leaflet-container {
            width: 50vw !important;
            height: 100vh !important;
        }

        /* Move layer control to top left */
        .leaflet-top.leaflet-right {
            right: auto !important;
            left: 10px !important;
        }
    </style>
</head>
<body>
    <div class="map-container">
        <div class="header-container">
            <span class="year-label">2011</span>
            <span class="active-layer" id="activeLayer2011">No overlay selected</span>
        </div>
        <div class="legend-container" id="legend2011">
            Legend
        </div>
        <div id="map2011">{{ map_html_2011 }}</div>
    </div>
    <div class="map-container">
        <div class="header-container">
            <span class="year-label">2022</span>
            <span class="active-layer" id="activeLayer2022">No overlay selected</span>
        </div>
        <div class="legend-container" id="legend2022">
            Legend
        </div>
        <div id="map2022">{{ map_html_2022 }}</div>
    </div>
    <script>
        function setupMapListeners() {
    document.querySelectorAll('.map-container').forEach(container => {
        const year = container.querySelector('.year-label').textContent;
        const activeLayerElement = container.querySelector('.active-layer');
        const legendContainer = container.querySelector('.legend-container');

        // Define the mapping between overlays and SVG paths
        const svgMapping = {
            2011: {
                'Parks': 'svgs/2011/parks.svg',
                'Redlining': 'svgs/2011/redlining.svg'
            },
            2022: {
                'Parks': 'svgs/2022/parks.svg',
                'Redlining': 'svgs/2022/redlining.svg'
            }
        };

        // Function to update the legend
        function updateLegend(labelText, year) {
            const svgPath = svgMapping[year]?.[labelText];
            if (svgPath) {
                legendContainer.innerHTML = `<strong>Legend</strong><br><img src="${svgPath}" alt="Legend for ${labelText}" style="max-width: 100%; height: auto;">`;
            } else {
                legendContainer.innerHTML = `<strong>Legend</strong>`;
            }
        }

        // Find all radio inputs in the layer control for this map
        const layerInputs = container.querySelectorAll('.leaflet-control-layers-selector[type="radio"]');

        layerInputs.forEach(input => {
            input.addEventListener('change', function () {
                if (this.checked) {
                    // Get the label text associated with this radio input
                    const labelText = this.nextElementSibling.textContent.trim();
                    activeLayerElement.textContent = labelText;

                    // Update the legend with the selected overlay
                    updateLegend(labelText, year);
                }
            });
        });

        // Handle the redlining overlay checkbox
        const redliningCheckbox = container.querySelector('.leaflet-control-layers-selector[type="checkbox"]');
        if (redliningCheckbox) {
            redliningCheckbox.addEventListener('change', function () {
                const redliningLabel = 'Redlining';
                if (this.checked) {
                    // Add Redlining SVG to the legend without replacing the current legend
                    const redliningSvgPath = svgMapping[year]?.[redliningLabel];
                    if (redliningSvgPath && !legendContainer.innerHTML.includes(redliningSvgPath)) {
                        legendContainer.innerHTML += `<br><img src="${redliningSvgPath}" alt="Legend for Redlining Overlay" style="max-width: 100%; height: auto;">`;
                    }
                } else {
                    // Remove Redlining SVG from the legend if unchecked
                    const redliningSvgPath = svgMapping[year]?.[redliningLabel];
                    if (redliningSvgPath) {
                        const redliningHtml = `<br><img src="${redliningSvgPath}" alt="Legend for Redlining Overlay" style="max-width: 100%; height: auto;">`;
                        legendContainer.innerHTML = legendContainer.innerHTML.replace(redliningHtml, '');
                    }
                }
            });
        }
    });
}


        // Wait for Leaflet controls to be fully loaded
        window.addEventListener('load', () => {
            // Give a small delay to ensure all Leaflet elements are rendered
            setTimeout(setupMapListeners, 1000);
        });
    </script>
</body>
</html>
"""

# Render the combined HTML
template = Template(combined_html_template)
combined_html = template.render(map_html_2011=map_html_2011, map_html_2016=map_html_2016, map_html_2022=map_html_2022)

# Save the combined HTML file
with open('nyc-disparity-map.html', 'w') as f:
    f.write(combined_html)

# Automatically open the combined HTML file in the default web browser
webbrowser.open('file://' + os.path.join(os.getcwd(), 'nyc-disparity-map.html'))
