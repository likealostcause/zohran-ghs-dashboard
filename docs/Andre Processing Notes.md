**Processing notes for aligning workflow**

- ***All code has been added to** [andre\_working](https://github.com/likealostcause/zohran-ghs-dashboard/tree/main/notebooks/andre_working) **folder in the notebooks directory of the github.***
- ***The following section is not in any particular order.***

1. Alignment of school points that belong to the same building.
   1. I noticed that some school points that belong to the same building were not in the same location, giving the appearance of multiple buildings. To fix this I did:
      1. Code: Ran [*snap\_points\_by\_BuildingCode.py*](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/snap_points_by_BuildingCode.py)
         1. Code uses *Bldg\_Code* field to align all points that share the same code and update their lat & long fields.

	\* Priority. Future master\_schools should have this updated geometry before I update

2. School Districts
   1. Downloaded School Districts (Clipped to Shoreline) from [NYC OpenData](https://www.nyc.gov/content/planning/pages/resources/datasets/school-districts) (nysd\_25d)
      1. Reprojected *nysd* layer to 4326 and saved as a geojson for adding to dashboard
      2. Ran *Fix geometries*  (repair method: structure) on school district layer
      3. Ran a Join By Location to add the *SchoolDist* attribute to master schools
      4. Uploaded layer to [drive](https://drive.google.com/file/d/1eUMwS8chRQwdB8VCjPXysNXzVQR5NNJG/view?usp=drive_link), and added as a layer in the dashboard map called school\_districts.geojson

	\* I realized when doing this that there’s a more updated version of school districts, so I redid this. Also I realize this may actually already be what you did for school districts, so you might not need to update this.

3. State Assembly Districts
   1. Downloaded State Assembly Districts (Clipped to Shoreline) from [NYC OpenData](https://www.nyc.gov/content/planning/pages/resources/datasets/state-assembly) (nyad\_25d)
      1. Reprojected *nyad* layer to 4326 and saved as a geojson for adding to dashboard
      2. Ran *Fix geometries*  (repair method: structure) on nyad layer
      3. Ran a Join By Location to add the *AssemDist* attribute to master schools
      4. Uploaded layer to [drive](https://drive.google.com/file/d/1ODub1-6BuXA5KclBsC6WnvE57cFvMYkr/view?usp=drive_link), and added as a layer in the dashboard map called ny\_assembly\_district.geojson

4. State Senate Districts
   1. Downloaded State Assembly Districts (Clipped to Shoreline) from [NYC OpenData](https://www.nyc.gov/content/planning/pages/resources/datasets/state-senate) (nyss\_25d)
      1. Reprojected *nyss* layer to 4326 and saved as a geojson for adding to dashboard
      2. Ran *Fix geometries*  (repair method: structure) on nyss layer
      3. Ran a Join By Location to add the *StSenDist* attribute to master schools
      4. Uploaded layer to [drive](https://drive.google.com/file/d/1ODub1-6BuXA5KclBsC6WnvE57cFvMYkr/view?usp=drive_link), and added as a layer in the dashboard map called NY\_State\_Senate\_Districts.geojson

5. Distance from peaker plants
   1. Downloaded all peaker plants from this tool: [https://www.cleanegroup.org/initiatives/phase-out-peakers/maps/](https://www.cleanegroup.org/initiatives/phase-out-peakers/maps/)
   2. Clipped peaker plants to plants 5 miles from NYC schools
      1. Buffer school layer by 5 miles
      2. Use buffer to Clip peaker plants
   3. Calculate the distance in miles from school points to the nearest peaker plant and add that as a field to the master schools layer
      1. See [EvacCenters distance code](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/hurricaneEvac_HeatIndex_distEvacCenters_distCoolingCenters.py)

6. On an open street
   1. Abhi actually did this one, check in with him
   2. According to the guide the datasource is this: [https://data.cityofnewyork.us/Health/Open-Streets-Locations/uiay-nctu/about\_data](https://data.cityofnewyork.us/Health/Open-Streets-Locations/uiay-nctu/about_data)
   3. I believe he did a buffer of 300 ft around open street locations and did an intersect with that.
   4. Resulting field is boolean, yes or no on an open street.

7. walking distance from subway
   1. First the layer was found on [ArcGIS online](https://ecosocialists.maps.arcgis.com/home/item.html?id=abfdf749f2104b8c952bd59bf004b8b6) (need account). *\[this is step does not need to be added to your work flow, i just included for reference\]*
   2. From the ArcGIS online page we find the Feature server link: [https://services1.arcgis.com/HmwnYiJTBZ4UkySc/arcgis/rest/services/Walking\_Distance/FeatureServer](https://services1.arcgis.com/HmwnYiJTBZ4UkySc/arcgis/rest/services/Walking_Distance/FeatureServer)
   3. The feature service link can be used to get the json of the layer and make a geojson from that.
      1. This [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/download_geojson_from_arc_server.py) will create the geojson from the feature server URL
   4. Once I have the walking distance geojson:
      1. I used this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/dist_to_subway_processing.py) to get the *subway\_dist* field on the school layer
         1. Spatially joined polygons to points to bring over the *WalkingB\_1* field.
         2. Created a new text field *subway\_dist* on the schools layer.
         3. Cleaned/standardized the joined values: removed spaces around the dash, added " min", and set null joins to "\>10 min".

8. hurricane evacuation zone, heat exposure index, distance from evac center, distance from cooling center
   1. The steps for these 4 fields has been consolidated in this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/hurricaneEvac_HeatIndex_distEvacCenters_distCoolingCenters.py)
   2. Field name : Data source:
      1. hurricane\_evacZone : [Hurricane Evac Zones](https://data.cityofnewyork.us/City-Government/Hurricane-Evacuation-Zones/epne-qv9x/about_data)
      2. OHEI : [Outdoor Heat Exposure Index](https://urbanheat.nyc/#/download)
      3. evacCenters\_distance\_mi : [Distance from Evac centers](https://data.cityofnewyork.us/Public-Safety/Hurricane-Evacuation-Centers/p5md-weyf/about_data)
      4. Cooling\_centers\_distance\_mi : [Distance from Cooling Centers](https://www.arcgis.com/home/item.html?id=a0643f21b5e24d1ea3ba1406775c4e52)
         1. To download as a geojson, use the feature service url in this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/download_geojson_from_arc_server.py)
            1. https://services6.arcgis.com/yG5s3afENB5iO9fj/arcgis/rest/services/CoolingCenters\_PROD\_view/FeatureServer
   3. Steps:
      1. Evac Zones and OHEI were a simple join attribute by location
      2. The distance fields were a distance in mile from each school to the nearest evac center/cooling center

9. avg pm2.5 & avg no2
   1. Download the NYCCAS Air Pollution Rasters [here](https://data.cityofnewyork.us/Environment/NYCCAS-Air-Pollution-Rasters/q68s-8qxv/about_data)
   2. Run this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/process_air_pollution_and_join.py) for processing the rasters and extracting the fields.
      1. Direct the script to the unzipped AnnAvg\_1\_15\_300m folder. It will find the required rasters:
         1.    aa14\_pm300m (PM2.5)
         2.    aa14\_no2300m (NO2)
      2. The script then samples the rasters with the school points and creates these fields:
         1. pm25\_2022
         2. No2\_2022

   \* Note that these field outputs are continuous, they will be converted into percentile in a diff step.

10. stormwater flood risks (3 fields)
    1. The data was downloaded [here](https://data.cityofnewyork.us/Environment/NYC-Stormwater-Flood-Maps/9i7c-xyvv/about_data)
       1. The downloaded zip file has issues opening since the file names are too long to unzip.
          1. Might be easier to just use the preprocessed layer in the [drive](https://drive.google.com/file/d/1jW7XCrHZTDRmH9V3aRIhn0HgzfR1FYL6/view?usp=drive_link) and skip steps *a* to *f*
    2. We only used the current sea level layers:
       1. NYC Stormwater Flood Map \- Limited Flood (1.77 inches per hr) with Current Sea Levels
       2. NYC Stormwater Flood Map \- Moderate Flood (2.13 inches per hr) with Current Sea Levels
    3. Create a field called *Flood\_Scenario* and populate it based on the file name and this [table](https://experience.arcgis.com/experience/e83a49daef8a472da4a7e34dc25ac445/).  See table below for the created field values
    4. Create a field called *Flood\_Category* populate it using the *Flooding\_C* field,
    5. Once downloaded I merged the two current sea level layers using Union. See table below for the created field values.
    6. Then I did a dissolve by the *Flood\_Scenario* and *Flood\_Category* fields
       1. Make sure that fields from the union are combined
       2. You should end up with four entries
       3. I created an integer field called *Stormwater\_Flood\_Risk* and then manually added values according to the table below. 1 being the greatest risk of the most likely occurence:

| Flood\_Scenario | Flood\_Category | Stormwater\_Flood\_Risk |
| :---- | :---- | :---- |
| Limited Flood: 1.77in/hr with current sea level (20% chance of yearly occurence) | Deep and Contiguous Flooding (1 ft. and greater) | 1 |
| Limited Flood: 1.77in/hr with current sea level (20% chance of yearly occurence) | Nuisance Flooding (greater or equal to 4 in. and less than 1 ft.) | 2 |
| Moderate Flood: 2.13in/hr with current sea level (10% chance of yearly occurence) | Deep and Contiguous Flooding (1 ft. and greater) | 3 |
| Moderate Flood: 2.13in/hr with current sea level (10% chance of yearly occurence) | Nuisance Flooding (greater or equal to 4 in. and less than 1 ft.) | 4 |

       4. After creating these fields, I used this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/storm_water_ranked_join.py) to do a ranked join with the school points layer
          1. School points are buffered by 300 feet and then they join the attribute of the polygon that they overlap with the highest rank (1 being the highest rank)
             1. So if a school buffer overlaps risks 3 and 4, it gets the attribute of risk 3

11. Converting continuous fields to percentile fields
    1. The following fields were converted into quartiles in order to make categorical filters:
       1.    "no2\_2022",
       2.     "pm25\_2022",
       3.     "ENERGY\_STAR\_Score",
       4.     "Direct\_GHG\_Emissions\_\_Metric\_Tons\_CO2e\_",
       5.     "Site\_EUI\_\_kBtu\_ft²\_",
       6.     "Percent\_Electricity",
       7.     "Electricity\_Use\_–\_Generated\_from\_Onsite\_Renewable\_Systems\_\_kWh\_",
       8.     "Fuel\_Oil\_\_2\_Use\_\_kBtu\_",
       9.     "Fuel\_Oil\_\_4\_Use\_\_kBtu\_",
       10.     "District\_Steam\_Use\_\_kBtu\_",
       11.     "District\_Hot\_Water\_Use\_\_kBtu\_",
       12.     "Natural\_Gas\_Use\_\_kBtu\_",
       13.     "Diesel\_\_2\_Use\_\_kBtu\_"
    2. This was done using this [script](https://github.com/likealostcause/zohran-ghs-dashboard/blob/main/notebooks/andre_working/convert_continous_to_percentile_class.py)
       1. The script replaces every *NULL* value with the string “No data”

A

\_pct

*\* Note that this doesn’t yet make the A/C fields into percentiles, I have not gotten to that.*
