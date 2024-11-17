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
            'fillOpacity': 0.6,
        },
        pane="redliningPane",  # Assign to the custom pane
        show=False
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
        top: 260px; /* Adjust to place below the layer control */
        left: 10px; /* Align with the layer control */
        z-index: 1000;
        background-color: white;
        padding: 5px; /* Smaller padding */
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        font-family: Arial, sans-serif;
        font-size: 12px; /* Smaller font size */
        text-align: center; /* Center the text */
        max-width: 270px; /* Limit the width */
        word-wrap: break-word; /* Allow long text to break to the next line */
        white-space: normal; /* Ensure text wraps */
    }

    .legend-container img {
        background-color: transparent; /* Ensure transparent background */
        width: 80%; /* Scale down further */
        height: auto;
        display: block;
        margin: 5px auto; /* Center the image and reduce margin */
    }

    .redlining-legend-container {
        position: absolute;
        top: 350px; /* Adjust to place below the main legend container */
        left: 10px; /* Align with the layer control */
        z-index: 1000;
        background-color: white;
        padding: 5px; /* Smaller padding */
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        font-family: Arial, sans-serif;
        font-size: 12px; /* Smaller font size */
        text-align: center; /* Center the text */
        max-width: 270px; /* Limit the width */
        display: none; /* Initially hidden */
    }

    .redlining-legend-container img {
        background-color: transparent; /* Ensure transparent background */
        width: 80%; /* Scale down further */
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
        
        .help-button {
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }

        .help-button:hover {
            background-color: #0056b3;
        }

        .help-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        }

        .help-modal-content {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            text-align: center;
            font-family: Arial, sans-serif;
            max-width: 500px;
        }

        .close-button {
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 10px;
            cursor: pointer;
            font-size: 14px;
        }

        .close-button:hover {
            background-color: #a71d2a;
        }
        
        .help-link {
            color: #007bff;
            text-decoration: none;
            font-weight: bold;
        }

        .help-link:hover {
            text-decoration: underline;
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
            <strong>Legend</strong>
        </div>
        <div class="redlining-legend-container" id="redliningLegend2011">
            <strong> Redlining </strong>
            <svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
            <defs>
                <linearGradient id="branca-gradient-redlining-2011-inline" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color: #b8d1af;" />
                    <stop offset="33%" style="stop-color: #b2cfd3;" />
                    <stop offset="66%" style="stop-color: #fdfd7c;" />
                    <stop offset="100%" style="stop-color: #eabfc3;" />
                </linearGradient>
            </defs>
            <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-redlining-2011-inline)" stroke="black" stroke-width="1" />
            <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Least</text>
            <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Most</text>
            <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Amount of Redlining</text>
        </svg>
        </div>
        <div id="map2011">{{ map_html_2011 }}</div>
    </div>
    <div class="map-container">
        <div class="header-container">
            <span class="year-label">2022</span>
            <span class="active-layer" id="activeLayer2022">No overlay selected</span>
        </div>
        <div class="legend-container" id="legend2022">
            <strong>Legend</strong>
        </div>
        <div class="redlining-legend-container" id="redliningLegend2022">
            <strong> Redlining </strong>
            <svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
            <defs>
                <linearGradient id="branca-gradient-redlining-2022-inline" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color: #b8d1af;" />
                    <stop offset="33%" style="stop-color: #b2cfd3;" />
                    <stop offset="66%" style="stop-color: #fdfd7c;" />
                    <stop offset="100%" style="stop-color: #eabfc3;" />
                </linearGradient>
            </defs>
            <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-redlining-2022-inline)" stroke="black" stroke-width="1" />
            <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Least</text>
            <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Most</text>
            <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Amount of Redlining</text>
        </svg>
        </div>
        <div id="map2022">{{ map_html_2022 }}</div>
    </div>
    <!-- Help Button -->
    <button class="help-button" id="helpButton">Help</button>

    <!-- Help Modal -->
    <div class="help-modal" id="helpModal">
        <div class="help-modal-content">
            <p>
                Please note that if an area is black, there is no available data for that area <br><br>
                
                For more details on the project, including references, overlay overviews and more, please go to
                <a class="help-link" href="https://github.com/bhnuka/nyc-disparity-mapper" target="_blank">
                    this link
                </a>
            </p>
            <button class="close-button" id="closeButton">Close</button>
        </div>
    </div>
    <script>
        // Get modal elements
        const helpButton = document.getElementById('helpButton');
        const helpModal = document.getElementById('helpModal');
        const closeButton = document.getElementById('closeButton');

        // Show the modal when the Help button is clicked
        helpButton.addEventListener('click', () => {
            helpModal.style.display = 'flex';
        });

        // Close the modal when the Close button is clicked
        closeButton.addEventListener('click', () => {
            helpModal.style.display = 'none';
        });

        // Close the modal when clicking outside the modal content
        window.addEventListener('click', (event) => {
            if (event.target === helpModal) {
                helpModal.style.display = 'none';
            }
        });
    </script>
    <script>
    function setupMapListeners() {
        const svgTemplates = {
        asian2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-asian-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-asian-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">0</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">28087</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">56173</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Asian</text>
    </svg>`,
        
        bachelors2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
    <defs>
        <linearGradient id="branca-gradient-bachelors-2011" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" style="stop-color: #fdfdd5;" />
            <stop offset="25%" style="stop-color: #fceab7;" />
            <stop offset="50%" style="stop-color: #edc794;" />
            <stop offset="75%" style="stop-color: #f59b8c;" />
            <stop offset="100%" style="stop-color: #dc7d8f;" />
        </linearGradient>
    </defs>
    <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-bachelors-2011)" stroke="black" stroke-width="1" />
    <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">585</text>
    <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">23941</text>
    <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">47297</text>
    <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Bachelor's Degree or Higher</text>
</svg>`,

black2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-black-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-black-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">4</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">39874</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">79744</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Black</text>
    </svg>`,

    blackstopped2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-blackstopped-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-blackstopped-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">5</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">48</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">91</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Black Stopped Rate (%)</text>
    </svg>`,

    homevalue2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-homevalue-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-homevalue-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">100000</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">500000</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">1000000</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Median Home Value</text>
    </svg>`,

    income2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-income-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-income-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">0</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">4516</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">9032</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Income (Above $200000)</text>
    </svg>`,
    
    parks2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-parks-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-parks-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">1</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">11</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">21</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Number of Parks</text>
    </svg>`,

    population2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-population-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-population-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">1</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">11</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">21</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Population</text>
    </svg>`,

    redlining2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-redlining-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #b8d1af;" />
                <stop offset="33%" style="stop-color: #b2cfd3;" />
                <stop offset="66%" style="stop-color: #fdfd7c;" />
                <stop offset="100%" style="stop-color: #eabfc3;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-redlining-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Least</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Most</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Amount of Redlining</text>
    </svg>`,

    schools2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-schools-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-schools-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">4</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">28</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">52</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Public Schools</text>
    </svg>`,

    white2011: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-white-2011" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-white-2011)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">484</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">39661</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">78838</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">White</text>
    </svg>`,
    
    asian2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-asian-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-asian-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">44</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">28897</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">57749</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Asian</text>
    </svg>`,

    bachelors2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-bachelors-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-bachelors-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">1026</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">32514</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">49094</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Bachelor's Degree or Higher</text>
    </svg>`,

    black2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-black-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-black-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">9</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">40809</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">81608</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Black</text>
    </svg>`,

    blackstopped2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-blackstopped-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-blackstopped-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">10</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">52</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">93</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Black Stopped Rate (%)</text>
    </svg>`,
    
    homevalue2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-homevalue-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-homevalue-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">100000</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">500000</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">2000000</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Median Home Value</text>
    </svg>`,

    income2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-income-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-income-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">116</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">7093</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">14069</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Income (Above $200000)</text>
    </svg>`,

    parks2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-parks-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-parks-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">1</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">11</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">21</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Number of Parks</text>
    </svg>`,

    population2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-population-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-population-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">3736</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">58243</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">112750</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Population</text>
    </svg>`,

    redlining2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-redlining-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #b8d1af;" />
                <stop offset="33%" style="stop-color: #b2cfd3;" />
                <stop offset="66%" style="stop-color: #fdfd7c;" />
                <stop offset="100%" style="stop-color: #eabfc3;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-redlining-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Least</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Most</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Amount of Redlining</text>
    </svg>`,

    schools2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-schools-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-schools-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">4</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">28</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">52</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">Public Schools</text>
    </svg>`,

    white2022: `<svg xmlns="http://www.w3.org/2000/svg" width="250" height="50" style="background-color: transparent;">
        <defs>
            <linearGradient id="branca-gradient-white-2022" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: #fdfdd5;" />
                <stop offset="25%" style="stop-color: #fceab7;" />
                <stop offset="50%" style="stop-color: #edc794;" />
                <stop offset="75%" style="stop-color: #f59b8c;" />
                <stop offset="100%" style="stop-color: #dc7d8f;" />
            </linearGradient>
        </defs>
        <rect x="25" y="20" width="200" height="10" fill="url(#branca-gradient-white-2022)" stroke="black" stroke-width="1" />
        <text x="25" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">734</text>
        <text x="125" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">32514</text>
        <text x="225" y="15" font-family="Arial" font-size="12" text-anchor="middle" fill="black">64293</text>
        <text x="125" y="45" font-family="Arial" font-size="12" text-anchor="middle" fill="black">White</text>
    </svg>`
    };
        
        document.querySelectorAll('.map-container').forEach(container => {
            const year = container.querySelector('.year-label').textContent;
            const activeLayerElement = container.querySelector('.active-layer');
            const legendContainer = container.querySelector('.legend-container');
            const redliningLegendContainer = container.querySelector(`#redliningLegend${year}`);

            // Define the mapping between layers and their SVG templates
            const svgMapping = {
                2011: {
                    'Asian': svgTemplates.asian2011,
                    'Bachelors Degree Or Higher': svgTemplates.bachelors2011,
                    'Black Or African American': svgTemplates.black2011,
                    'Black Stopped Rate': svgTemplates.blackstopped2011,
                    'Median Home Value': svgTemplates.homevalue2011,
                    'Median Household Income': svgTemplates.income2011,
                    'Parks': svgTemplates.parks2011,
                    'Population': svgTemplates.population2011,
                    'Public Schools': svgTemplates.schools2011,
                    'White': svgTemplates.white2011
                },
                2022: {
                    'Asian': svgTemplates.asian2022,
                    'Bachelors Degree Or Higher': svgTemplates.bachelors2022,
                    'Black Or African American': svgTemplates.black2022,
                    'Black Stopped Rate': svgTemplates.blackstopped2022,
                    'Median Home Value': svgTemplates.homevalue2022,
                    'Median Household Income': svgTemplates.income2022,
                    'Parks': svgTemplates.parks2022,
                    'Population': svgTemplates.population2022,
                    'Public Schools': svgTemplates.schools2022,
                    'White': svgTemplates.white2022
                }
            };

            // Keep track of active overlays
            const activeOverlays = new Set();

            // Function to refresh the legend based on active overlays
            function refreshLegend() {
                let legendHtml = `<strong>Legend</strong>`;
                activeOverlays.forEach(overlay => {
                    const svgContent = svgMapping[year]?.[overlay];
                    if (svgContent) {
                        legendHtml += `<br>${svgContent}`;
                    }
                });
                legendContainer.innerHTML = legendHtml;
            }

            // Function to toggle the Redlining Legend
            function toggleRedliningLegend(visible) {
                redliningLegendContainer.style.display = visible ? 'block' : 'none';
            }

            // Handle radio button changes
            const radioInputs = container.querySelectorAll('.leaflet-control-layers-selector[type="radio"]');
            radioInputs.forEach(input => {
                input.addEventListener('change', function () {
                    if (this.checked) {
                        const labelText = this.nextElementSibling.textContent.trim();
                        activeOverlays.clear();
                        activeOverlays.add(labelText);
                        activeLayerElement.textContent = labelText;
                        refreshLegend();
                    }
                });
            });

            // Handle checkbox changes
            const checkboxInputs = container.querySelectorAll('.leaflet-control-layers-selector[type="checkbox"]');
            checkboxInputs.forEach(input => {
                input.addEventListener('change', function () {
                    const labelText = this.nextElementSibling.textContent.trim();
                    
                    if (this.checked) {
                        activeOverlays.add(labelText);
                    } else {
                        activeOverlays.delete(labelText);
                    }

                    if (labelText === 'Redlining Overlay') {
                        toggleRedliningLegend(this.checked);
                    }

                    refreshLegend();
                });
            });
        });
    }

    // Wait for Leaflet controls to be fully loaded
    window.addEventListener('load', () => {
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
