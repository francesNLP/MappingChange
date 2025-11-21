import pandas as pd
from rdflib.namespace import GEO, SDO

from utils import load_name_map, save_name_map, name_to_uri_name, normalize_entity_name
from rdflib import Graph, Namespace, URIRef, RDF, Literal, RDFS, XSD, PROV
from tqdm import tqdm


# define namespaces
hto = Namespace("https://w3id.org/hto#")
crm = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
crmgeo = Namespace("http://www.ics.forth.gr/isl/CRMgeo/")
oa = Namespace("http://www.w3.org/ns/oa#")

print("Load base hto ontology...")
graph = Graph()
graph_filepath = "hto.ttl"
graph.parse(graph_filepath, format="turtle")

# create agents
mapping_change = URIRef("https://github.com/francesNLP/MappingChange")

stanza = URIRef("https://github.com/stanfordnlp/stanza")
graph.add((stanza, RDF.type, PROV.SoftwareAgent))
graph.add((stanza, RDFS.label, Literal("Stanza", datatype=XSD.string)))

edinburgh_geoparser = URIRef("https://www.ltg.ed.ac.uk/software/geoparser/")
graph.add((stanza, RDF.type, PROV.SoftwareAgent))
graph.add((stanza, RDFS.label, Literal("Edinburgh Geoparser", datatype=XSD.string)))


# convert all coordinates in locations to float type
def convert_coordinates_type(geo_df):
    all_locations = []
    latitudes_values =[]
    longitudes_values =[]
    for index, row in geo_df.iterrows():
        locations = row["locations"]
        for location in locations:
            coordinate = [None, None]
            if location["latitude"] != "":
                coordinate[0] = float(location["latitude"])
                coordinate[1] = float(location["longitude"])
            location["latitude"] = coordinate[0]
            location["longitude"] = coordinate[1]
        all_locations.append(locations)
        latitude = None
        longitude = None
        if row["latitude"] != "":
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
        latitudes_values.append(latitude)
        longitudes_values.append(longitude)

    geo_df["locations"] = all_locations
    geo_df["latitude"] = latitudes_values
    geo_df["longitude"] = longitudes_values


def get_location_id(location):
    normalized_name = normalize_entity_name(location["name"])
    location_id = name_to_uri_name(normalized_name)
    if "latitude" in location and location["latitude"] and pd.notna(location["latitude"]):
        latitude = location["latitude"]
        longitude = location["longitude"]
        latitude = round(latitude, 5)
        longitude = round(longitude, 5)
        lat_str = str(latitude).replace('.', 'd')
        lon_str = str(longitude).replace('.', 'd')
        location_id += (""
                        "_") + lat_str + "_" + lon_str
    return location_id


def get_all_unique_locations(geo_df):
    """
    This function adds all the locations mentioned in the articles_with_geo to unique_locations.
    :param geo_df: input dataframe with articles and geographical information
    :return: contemporary_unique_locations: dict objects of contemporarylocations with location id as key, location details as value.
    """
    contemporary_unique_locations = {}
    for index, row in geo_df.iterrows():
        contemporary_locations = row["locations"]
        contemporary_locations.append({
                    "name": row["name"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "gazetteer_ref": row["gazetteer_ref"],
                    "population": row["population"],
                    "in_country": row["in_country"],
                    "feature_type": row["feature_type"]
                })

        for location in contemporary_locations:
            #print(index, location)
            location_id = get_location_id(location)
            if location_id not in contemporary_unique_locations:
                contemporary_unique_locations[location_id] = location

    return contemporary_unique_locations

def add_centroid(location, location_id, target_graph):
    centroid_uri = URIRef("https://w3id.org/hto/SP6_Declarative_Place/" + location_id)
    target_graph.add((centroid_uri, RDF.type, GEO.Geometry))
    target_graph.add((centroid_uri, RDF.type, crmgeo.SP6_Declarative_Place))
    geojson = Literal(
        '''{"type": "Point", "coordinates": [%s, %s]}''' % (location["longitude"], location["latitude"]),
        datatype=GEO.geoJSONLiteral)
    target_graph.add((centroid_uri, GEO.asGeoJSON, geojson))
    wkt = Literal(
        '''POINT(%s %s)''' % (location["latitude"], location["longitude"]),
        datatype=GEO.wktLiteral)
    target_graph.add((centroid_uri, GEO.asWKT, wkt))
    return centroid_uri

def add_phenomenal_place(location, added_locations_uris, target_graph):
    """
    This function constructs phenomenal place for location and add to graph if it does not exist in added_locations. It also creates the centroid and links the centroid with the phenomenal place if coordinates provided. It adds the location to added_locations if not already. It returns the uri of the added phenomenal place.
    :param location: location details used to construct phenomenal place and centroid.
    :param added_locations_uris: uris of locations which have been added to target_graph.
    :param target_graph: the targe knowledge graph.
    :return: location_id, location_uri: an id and an URIRef of the added phenomenal place.
    """
    # check if this location is already in the target graph
    # this check might not be necessary if uri is constructed based on name and coordinates.
    normalized_name = normalize_entity_name(location["name"])
    location_id = get_location_id(location)

    if location_id in added_locations_uris:
        return location_id, added_locations_uris[location_id]

    location_uri = URIRef("https://w3id.org/hto/SP2_Phenomenal_Place/" + location_id)
    location["uri"] = location_uri
    added_locations_uris[location_id] = location["uri"]
    target_graph.add((location_uri, RDF.type, GEO.Feature))
    target_graph.add((location_uri, RDF.type, crm.E53_Place))
    target_graph.add((location_uri, RDF.type, crmgeo.SP2_Phenomenal_Place))
    target_graph.add((location_uri, RDFS.label, Literal(normalized_name, datatype=XSD.string)))

    # link location type
    if "feature_type" in location:
        location_type = location["feature_type"]
        location_type_map = {
            "country": hto.Country,
            "continent": hto.Continent,
            "rgn": hto.Region
        }
        if location_type in ["country", "continent", "region"]:
            target_graph.add((location_uri, hto.hasFeatureType, location_type_map[location_type]))
        if location_type not in ["country", "continent"] and "in_country" in location and location["in_country"] != "":
            # link the location to its country
            #print(f"linked to country {location['in_country']}")
            linked_country_uri = countries_codes_uris_map[location["in_country"]]
            target_graph.add((location_uri, crm.P89_falls_within, linked_country_uri))

    # add centroid
    if "latitude" in location and location["latitude"] and pd.notna(location["latitude"]):
        centroid_uri = add_centroid(location, location_id, target_graph)
        target_graph.add((location_uri, GEO.hasCentroid, centroid_uri))

    return location_id, location_uri


def add_locations_to_graph(unique_locations, added_locations_uris, time_span, target_graph):
    for location_key in unique_locations:
        # construct and add a phenomenal place for this location to the graph and return the URIRef of the phenomenal place.
        # also add location uri to added_locations_uris if not already
        location = unique_locations[location_key]
        location_id, location_uri = add_phenomenal_place(location, added_locations_uris, target_graph)

        # construct and add spacetime volume
        spacetime_volume_uri = URIRef("https://w3id.org/hto/E92_Spacetime_Volume/" + location_id + "_" + time_span["label"])
        target_graph.add((spacetime_volume_uri, RDF.type, crm.E92_Spacetime_Volume))
        target_graph.add((spacetime_volume_uri, crm.P161_has_spatial_projection, location_uri))
        target_graph.add((spacetime_volume_uri, crm.P160_has_temporal_projection, time_span["uri"]))


def add_location_annotation(location, term_uri_str, desc_uri_str, added_locations_uris, target_graph):
    # create an oa:TextPositionSelector
    if "start" not in location:
        return
    start_index = location["start"]
    end_index = location["end"]
    if start_index < 0:
        return
    text_position_selector_uri = URIRef(f"https://w3id.org/hto/TextPositionSelector/{start_index}_{end_index}")
    target_graph.add((text_position_selector_uri, RDF.type, oa.TextPositionSelector))
    target_graph.add((text_position_selector_uri, oa.start, Literal(str(start_index), datatype=XSD.nonNegativeInteger)))
    target_graph.add((text_position_selector_uri, oa.end, Literal(str(end_index), datatype=XSD.nonNegativeInteger)))

    # create an oa:SpecificResource
    desc_uri = URIRef(desc_uri_str)
    desc_id = desc_uri_str.split("https://w3id.org/hto/OriginalDescription/")[1]
    specific_words_id = desc_id + str(start_index) + "_" + str(end_index)
    specific_words_uri = URIRef(f"https://w3id.org/hto/TextSegment/{specific_words_id}")
    target_graph.add((specific_words_uri, RDF.type, hto.TextSegment))
    target_graph.add((specific_words_uri, oa.hasSource, desc_uri))
    target_graph.add((specific_words_uri, oa.hasSelector, text_position_selector_uri))

    # get location_uri
    location_id = get_location_id(location)
    location_uri = added_locations_uris[location_id]

    # create an annotation
    location_annotation_uri = URIRef(f"https://w3id.org/hto/Annotation/{specific_words_id}")
    target_graph.add((location_annotation_uri, RDF.type, oa.Annotation))
    target_graph.add((desc_uri, hto.hasAnnotation, location_annotation_uri))
    target_graph.add((specific_words_uri, hto.hasAnnotation, location_annotation_uri))
    target_graph.add((location_annotation_uri, oa.hasTarget, specific_words_uri))
    target_graph.add((location_annotation_uri, oa.hasBody, location_uri))

    # software used to generate the annotation
    target_graph.add((location_annotation_uri, PROV.wasAttributedTo, stanza))
    target_graph.add((location_annotation_uri, PROV.wasAttributedTo, edinburgh_geoparser))
    target_graph.add((location_annotation_uri, PROV.wasAttributedTo, mapping_change))

    return location_annotation_uri


def annotate(geo_df, target_graph):
    for index, row in tqdm(geo_df.iterrows(), total=len(geo_df)):
        record_uri_str = row["record_uri"]
        record_uri = URIRef(record_uri_str)
        location_name = normalize_entity_name(row["name"])
        c_location = {
            "name": location_name,
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }
        c_location_id = get_location_id(c_location)
        c_location_uri = added_locations_uris[c_location_id]
        #graph.add((record_uri, RDF.type, hto.LocationRecord))
        target_graph.add((record_uri, hto.refersToModernPlace, c_location_uri))

        desc_uri_str = row["description_uri"]
        locations = row["locations"]
        for location in locations:
            add_location_annotation(location, record_uri_str, desc_uri_str, added_locations_uris, target_graph)


if __name__ == "__main__":
    # Load the geo dataframe
    print("Loading georesolved articles...")
    input_gaz_georesolved_articles_filename = "../geoparse/results/georesolved_df.json"
    articles_with_geo = pd.read_json(input_gaz_georesolved_articles_filename, orient="records", lines=True)
    print(f"loaded {len(articles_with_geo)} articles")

    print("Loading name map pairs....")
    name_map_file = "name_map.pickle"
    load_name_map(name_map_file)
    from utils import name_map
    print(f"loaded {len(name_map)} pairs")


    convert_coordinates_type(articles_with_geo)
    print("Get unique locations....")
    c_unique_locations = get_all_unique_locations(articles_with_geo)

    # Loading countries info
    print("Loading countries info....")
    countries_info_filename = "sources/countries_info.json"
    countries_info_df = pd.read_json(countries_info_filename, orient="records", lines=True)
    print(f"loaded {len(countries_info_df)} countries")

    # add counties uris to added_locations_uris
    added_locations_uris = {}
    for index, country in countries_info_df.iterrows():
        country_id = get_location_id(country)
        added_locations_uris[country_id] = URIRef(country["uri"])

    # add counties codes to countries_codes_uris_map
    countries_codes_uris_map = {}
    for index, country in countries_info_df.iterrows():
        countries_codes_uris_map[country['code']] = URIRef(country["uri"])

    # create time-spans
    current_time_label = "2025"
    time_span_current = {
        "label": current_time_label,
        "uri": URIRef("https://w3id.org/hto/E52_Time-Span/" + current_time_label)
    }
    graph.add((time_span_current["uri"], RDF.type, URIRef("http://www.cidoc-crm.org/cidoc-crm/E52_Time-Span")))
    graph.add((time_span_current["uri"], RDFS.label, Literal(current_time_label, datatype=XSD.string)))

    # add current time locations
    print("Adding all locations to graph")
    add_locations_to_graph(c_unique_locations, added_locations_uris, time_span_current, graph)

    print("Adding location annotations to graph")
    # adding annotations
    annotate(articles_with_geo, graph)

    graph_result_filename = "results/gaz_locations_annotations.ttl"
    print(f"Saving graph to {graph_result_filename}...")
    # save graph
    graph.serialize(destination=graph_result_filename, format="turtle")

    print("Save name maps")
    # save name maps
    save_name_map(name_map_file)
    print("Done")




