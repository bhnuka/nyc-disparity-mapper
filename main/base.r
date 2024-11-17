library(sf)
library(leaflet)
library(dplyr)
library(jsonlite)
library(htmltools)

# Function to get resource path
resource_path <- function(relative_path) {
  file.path(getwd(), relative_path)
}

# Load the combined redline JSON
redline_data <- fromJSON(resource_path('redlining/combined_nyc_redline.json'))

# Read spatial and tabular data
precincts <- st_read(resource_path('Police Precincts/geo_export_285d695e-252a-4bd6-b18d-ab8f95aa63f9.shp'))
data_2011 <- read.csv(resource_path('nyc-data-2011.csv'))
data_2016 <- read.csv(resource_path('nyc-data-2016.csv'))
data_2022 <- read.csv(resource_path('nyc-data-2022.csv'))
zipcodes <- st_read(resource_path('MODZCTA/geo_export_953eebb2-7abd-4e3f-9628-39d0237055a1.shp'))

stop_frisk_2011 <- read.csv(resource_path('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2011.csv'))
stop_frisk_2016 <- read.csv(resource_path('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2016.csv'))
stop_frisk_2022 <- read.csv(resource_path('stopandfrisk/Stop_and_Frisk_Data_by_Precinct-2022.csv'))

# Function to clean and convert 'Precinct' column
clean_precinct <- function(df) {
  df <- df %>%
    mutate(Precinct = as.numeric(as.character(Precinct))) %>%
    drop_na(Precinct)
  return(df)
}

# Clean 'Precinct' column for all datasets
stop_frisk_2011 <- clean_precinct(stop_frisk_2011)
stop_frisk_2016 <- clean_precinct(stop_frisk_2016)
stop_frisk_2022 <- clean_precinct(stop_frisk_2022)

# Merge Stop and Frisk data with precincts
precincts <- precincts %>%
  left_join(stop_frisk_2011, by = c("precinct" = "Precinct")) %>%
  left_join(stop_frisk_2016, by = c("precinct" = "Precinct"), suffix = c("_2011", "_2016")) %>%
  left_join(stop_frisk_2022, by = c("precinct" = "Precinct"))

# Convert and merge zipcodes with demographic data
zipcodes_2011 <- zipcodes %>%
  left_join(data_2011, by = c("modzcta" = "ZCTA"))
zipcodes_2016 <- zipcodes %>%
  left_join(data_2016, by = c("modzcta" = "ZCTA"))
zipcodes_2022 <- zipcodes %>%
  left_join(data_2022, by = c("modzcta" = "ZCTA"))

# Function to create an interactive map
create_map_html <- function(columns, zipcodes_data, precincts_data, year) {
  m <- leaflet() %>%
    addTiles(group = "Base Map") %>%
    addPolygons(
      data = zipcodes_data,
      fillColor = "white",
      color = "black",
      fillOpacity = 0,
      group = "Zipcodes"
    ) %>%
    addGeoJSON(data = redline_data, 
               group = "Redlining Overlay", 
               style = list(
                 fillColor = ~fill,
                 color = "black",
                 weight = 0,
                 fillOpacity = 0.5)) %>%
    addLayersControl(
      baseGroups = c("Base Map"),
      overlayGroups = c("Zipcodes", "Redlining Overlay")
    )
  
  for (column in columns) {
    m <- m %>%
      addPolygons(
        data = precincts_data,
        fillColor = ~pal(column),
        group = column,
        label = ~as.character(column)
      )
  }
  return(m)
}

# Define columns for the maps
base_columns <- c("Median Home Value", "Bachelors degree or higher", "Population", 
                  "White", "Black or African American", "Asian", "Median Household Income")

columns_2011 <- c(base_columns, "Black Stopped Rate_2011", "Public Schools", "Parks")
columns_2016 <- c(base_columns, "Black Stopped Rate_2016", "Public Schools", "Parks")
columns_2022 <- c(base_columns, "Black Stopped Rate_2022", "Public Schools", "Parks")

# Create interactive maps
map_2011 <- create_map_html(columns_2011, zipcodes_2011, precincts, "2011")
map_2016 <- create_map_html(columns_2016, zipcodes_2016, precincts, "2016")
map_2022 <- create_map_html(columns_2022, zipcodes_2022, precincts, "2022")

# Save maps as HTML files
saveWidget(map_2011, file = "map_2011.html")
saveWidget(map_2016, file = "map_2016.html")
saveWidget(map_2022, file = "map_2022.html")
