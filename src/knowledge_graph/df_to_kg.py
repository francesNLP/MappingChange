import pandas as pd
from rdflib import Namespace, URIRef, RDF, Literal, XSD, RDFS, FOAF, PROV, Graph
import re
from tqdm import tqdm

import pickle
import random


NON_AZ_REGEXP = re.compile("[^A-Za-z0-9]")
hto = Namespace("https://w3id.org/hto#")

# load hto ontology
graph = Graph()
# Load hto ontology file into the graph
ontology_file = "hto.ttl"
graph.parse(ontology_file, format="turtle")

# create agents
mapping_change = URIRef("https://github.com/francesNLP/MappingChange")
graph.add((mapping_change, RDF.type, hto.SoftwareAgent))
graph.add((mapping_change, FOAF.name, Literal("francesNLP-MappingChange", datatype=XSD.string)))

nls = URIRef("https://w3id.org/hto/Organization/NLS")
graph.add((nls, RDF.type, hto.Organization))
graph.add((nls, FOAF.homepage, URIRef("https://www.nls.uk")))
graph.add((nls, FOAF.name, Literal("National Library of Scotland", datatype=XSD.string)))

# Create a function to generate unique ID for an entity based on the name, same ID should be generated for same name.
# We later use this ID to construct the URI for the entity. Special characters (such as Greek letters) might appear in the name, and uris with such characters are difficult to query, so we need digital ID over names.
MAX_SIZE_NAMES = 10000000000
name_map = {}
def name_to_uri_name(name):
    """
    Convert a name to a format which will be shown in the uri of a resource. This format (uri name) is digits based,
    which means  a sequence of digits are used to represent the name in the uri. Same name should have the
    same uri name.
    :param name: name of a resource
    :return: string as uri name (digits based).
    """
    if name in name_map:
        return name_map[name]

    name_id = random.randint(0, MAX_SIZE_NAMES)
    while str(name_id) in name_map.values():
        name_id = random.randint(0, MAX_SIZE_NAMES)
    name_map[name] = str(name_id)
    return str(name_id)


def save_name_map(filepath):
    """
    Save the name map into a pickle file, so it can be used to convert names to uri names, thus the form of uri
    can be consistent - same name should have the same uri name.
    :param filepath: where the file will be stored.
    :return:
    """
    with open(filepath, 'wb') as f:
        pickle.dump(name_map, f)


def load_name_map(filepath):
    """
    Load the name map from a pickle file, so it can be used to convert names to uri names, thus the form of uri
    can be consistent - same name should have the same uri name.
    :param filepath: where the file will be stored.
    :return:
    """
    try:
        with open(filepath, 'rb') as f:
            global name_map
            name_map = pickle.load(f)
    except FileNotFoundError:
        print("file not found")
        name_map = {}


def create_collection(collection_name, id_name):
    collection = URIRef("https://w3id.org/hto/WorkCollection/" + id_name)
    graph.add((collection, RDF.type, hto.WorkCollection))
    collection_name = collection_name + " Collection"
    graph.add((collection, hto.name, Literal(collection_name, datatype=XSD.string)))
    return collection


def series2rdf(series_info, collection):
    # create triples with general datatype
    series = URIRef("https://w3id.org/hto/Series/" + str(series_info["MMSID"]))
    series_title = str(series_info["serieTitle"])
    graph.add((series, RDF.type, hto.Series))
    graph.add((collection, hto.hadMember, series))
    graph.add((series, hto.number, Literal(int(series_info["serieNum"]), datatype=XSD.integer)))
    graph.add((series, hto.title, Literal(series_title, datatype=XSD.string)))
    series_sub_title = str(series_info["serieSubTitle"])
    if series_sub_title != "0":
        graph.add((series, hto.subtitle, Literal(series_sub_title, datatype=XSD.string)))

    publish_year = int(series_info["year"])
    graph.add((series, hto.yearPublished, Literal(publish_year, datatype=XSD.int)))
    # create a Location instance for printing place
    place_name = str(series_info["place"])
    if place_name != "0":
        place_uri_name = name_to_uri_name(place_name)
        place = URIRef("https://w3id.org/hto/Location/" + place_uri_name)
        graph.add((place, RDF.type, hto.Location))
        graph.add((place, RDFS.label, Literal(place_name, datatype=XSD.string)))
        graph.add((series, hto.printedAt, place))

    graph.add((series, hto.mmsid, Literal(str(series_info["MMSID"]), datatype=XSD.string)))
    graph.add((series, hto.physicalDescription, Literal(series_info["physicalDescription"], datatype=XSD.string)))
    graph.add((series, hto.genre, Literal(series_info["genre"], datatype=XSD.string)))
    graph.add((series, hto.language, Literal(series_info["language"], datatype=XSD.language)))

    # create a Location instance for shelf locator
    shelf_locator_name = str(series_info["shelfLocator"])
    shelf_locator_uri_name = name_to_uri_name(shelf_locator_name)
    shelf_locator = URIRef("https://w3id.org/hto/Location/" + shelf_locator_uri_name)
    graph.add((shelf_locator, RDF.type, hto.Location))
    graph.add((shelf_locator, RDFS.label, Literal(shelf_locator_name, datatype=XSD.string)))
    graph.add((series, hto.shelfLocator, shelf_locator))

    ## Editor
    if series_info["editor"] != 0:
        editor_name = str(series_info["editor"])
        editor_uri_name = name_to_uri_name(editor_name)
        if editor_name != "":
            editor = URIRef("https://w3id.org/hto/Person/" + str(editor_uri_name))
            graph.add((editor, RDF.type, hto.Person))
            graph.add((editor, FOAF.name, Literal(editor_name, datatype=XSD.string)))

            if series_info["editor_date"] != 0:
                editor_date = str(series_info["editor_date"]).replace("?", "")
                if editor_date.find("-") != -1:
                    tmpDate = editor_date.split("-")

                    birthYear = tmpDate[0]
                    deathYear = tmpDate[1]

                    if birthYear.isnumeric():
                        graph.add((editor, hto.birthYear, Literal(int(birthYear), datatype=XSD.int)))
                    if deathYear.isnumeric():
                        graph.add((editor, hto.deathYear, Literal(int(deathYear), datatype=XSD.int)))
                else:
                    print(f"date {editor_date} cannot be parsed!")

            if series_info["termsOfAddress"] != 0:
                graph.add((editor, hto.termsOfAddress, Literal(series_info["termsOfAddress"], datatype=XSD.string)))

            graph.add((series, hto.editor, editor))

    # Publishers Persons
    if series_info["publisherPersons"] != 0 and len(series_info["publisherPersons"]) > 0:
        publisherPersons = series_info["publisherPersons"]
        #print(publisherPersons)
        if len(publisherPersons) == 1:
            publisher_name = publisherPersons[0]
            iri_publisher_name = name_to_uri_name(publisher_name)
            if iri_publisher_name != "":
                publisher = URIRef("https://w3id.org/hto/Person/" + iri_publisher_name)
                graph.add((publisher, RDF.type, hto.Person))
                graph.add((publisher, FOAF.name, Literal(publisher_name, datatype=XSD.string)))
                graph.add((series, hto.publisher, publisher))
        else:
            iri_publisher_name = ""
            publisher_name = ""
            for p in publisherPersons:
                publisher_name = publisher_name + ", " + p
                iri_publisher_name = name_to_uri_name(publisher_name)
                if iri_publisher_name == "":
                    break
            publisher = URIRef("https://w3id.org/hto/Organization/" + iri_publisher_name)
            graph.add((publisher, RDF.type, hto.Organization))
            graph.add((publisher, FOAF.name, Literal(publisher_name, datatype=XSD.string)))
            graph.add((series, hto.publisher, publisher))

        # Creat an instance of publicationActivity
        # publication_activity = URIRef("https://w3id.org/hto/Activity/"+ "publication" + str(series_info["MMSID"]))
        # graph.add((publication_activity, RDF.type, PROV.Activity))
        # graph.add((publication_activity, PROV.generated, series))
        #  if publish_year != "0":
        # graph.add((publication_activity, PROV.endedAtTime, Literal(publish_year, datatype=XSD.dateTime)))
        # graph.add((publication_activity, PROV.wasEndedBy, publisher))

        # graph.add((series, PROV.wasGeneratedBy, publication_activity))

    return series


def volume2rdf(volume_info, series):
    volume_id = str(volume_info["volumeId"])
    volume = URIRef("https://w3id.org/hto/Volume/" + str(volume_info["MMSID"]) + "_" + str(volume_id))
    graph.add((volume, RDF.type, hto.Volume))
    graph.add((volume, hto.number, Literal(volume_info["volumeNum"], datatype=XSD.integer)))
    graph.add((volume, hto.volumeId, Literal(volume_id, datatype=XSD.string)))
    graph.add((volume, hto.title, Literal(volume_info["volumeTitle"], datatype=XSD.string)))

    if volume_info["part"] != 0:
        graph.add((volume, hto.part, Literal(volume_info["part"], datatype=XSD.integer)))

    permanentURL = URIRef(str(volume_info["permanentURL"]))
    graph.add((permanentURL, RDF.type, hto.Location))
    graph.add((volume, hto.permanentURL, permanentURL))
    graph.add((volume, hto.numberOfPages, Literal(volume_info["numberOfPages"], datatype=XSD.integer)))
    graph.add((series, RDF.type, hto.WorkCollection))
    graph.add((series, hto.hadMember, volume))
    graph.add((volume, hto.wasMemberOf, series))

    return volume


def create_dataset(collection_id_name, agent_uri, agent_short_name):
    dataset = URIRef("https://w3id.org/hto/Collection/" + agent_short_name + "_" + collection_id_name + "_dataset")
    if (dataset, RDF.type, PROV.Collection) in graph:
        return dataset
    graph.add((dataset, RDF.type, PROV.Collection))
    graph.add((dataset, PROV.wasAttributedTo, agent_uri))

    # Create digitalising activity
    digitalising_activity = URIRef("https://w3id.org/hto/Activity/" + agent_short_name + "_digitalising_activity")
    graph.add((digitalising_activity, RDF.type, hto.Activity))
    graph.add((digitalising_activity, PROV.generated, dataset))
    graph.add((digitalising_activity, PROV.wasAssociatedWith, agent_uri))
    graph.add((dataset, PROV.wasGeneratedBy, digitalising_activity))
    return dataset


def dataframe_to_rdf(collection, dataframe, gazetteer_dataset):
    dataframe = dataframe.fillna(0)
    dataframe["id"] = dataframe.index
    # create triples
    series_mmsids = dataframe["MMSID"].unique()
    for mmsid in series_mmsids:
        df_series = dataframe[dataframe["MMSID"] == mmsid].reset_index(drop=True)
        series_info = df_series.loc[0]
        #print(edition_info["serieTitle"])
        series_ref = series2rdf(series_info, collection)

        # VOLUMES
        vol_numbers = df_series["volumeNum"].unique()
        # graph.add((edition_ref, hto.numberOfVolumes, Literal(len(vol_numbers), datatype=XSD.integer)))
        for vol_number in vol_numbers:
            df_vol = df_series[df_series["volumeNum"] == vol_number].reset_index(drop=True)
            volume_info = df_vol.loc[0]
            volume_ref = volume2rdf(volume_info, series_ref)
            # print(volume_info)
            df_vol_by_entry = df_vol.groupby(['name'], )["name"].count().reset_index(name='counts')
            # print(df_vol_by_entry)

            # Location Entries
            for entry_index in range(0, len(df_vol_by_entry)):
                df_article = df_vol_by_entry.loc[entry_index]
                entry_name = df_vol_by_entry.loc[entry_index]["name"]
                entry_counts = df_vol_by_entry.loc[entry_index]["counts"]
                entry_uri_name = name_to_uri_name(entry_name)
                # print(entry_uri_name)
                # All entries in one volume with name equals to value of entry_name
                df_entries = df_vol[df_vol["name"] == entry_name].reset_index(drop=True)
                for t_count in range(0, entry_counts):
                    df_entry = df_entries.loc[t_count]
                    entry_id = str(mmsid) + "_" + str(df_entry["volumeId"]) + "_" + entry_uri_name + "_" + str(t_count)
                    entry_ref = URIRef("https://w3id.org/hto/LocationRecord/" + entry_id)
                    graph.add((entry_ref, RDF.type, hto.LocationRecord))
                    graph.add((entry_ref, hto.name, Literal(entry_name, datatype=XSD.string)))

                    if "alter_names" in df_entry:
                        alter_names = df_entry["alter_names"]
                        for alter_name in alter_names:
                            graph.add((entry_ref, RDFS.label, Literal(alter_name, datatype=XSD.string)))

                    # Add the term_ref to dataframe
                    dataframe_equal = (dataframe['id'] == df_entry['id'])
                    dataframe.loc[dataframe_equal, "uri"] = entry_ref

                    # Create original description instance
                    description = df_entry["text"]
                    entry_original_description = URIRef(
                        "https://w3id.org/hto/OriginalDescription/" + str(df_entry["MMSID"]) + "_" + str(
                            df_entry["volumeId"]) + "_" + entry_uri_name + "_" + str(t_count) + "NLS")
                    graph.add((entry_original_description, RDF.type, hto.OriginalDescription))
                    text_quality = hto.Low
                    graph.add((entry_original_description, hto.hasTextQuality, text_quality))
                    graph.add(
                        (entry_original_description, hto.text, Literal(description, datatype=XSD.string)))

                    graph.add((entry_ref, hto.hasOriginalDescription, entry_original_description))
                    # graph.add((entry_ref, hto.position, Literal(df_entry["position"], datatype=XSD.int)))

                    # link description with software agent
                    graph.add((entry_original_description, PROV.wasAttributedTo, mapping_change))

                    # Create source entity where original description was extracted
                    # source location
                    # source_path_name = df_entry["altoXML"]
                    # source_path_ref = URIRef("https://w3id.org/eb/Location/" + source_path_name)
                    # graph.add((source_path_ref, RDF.type, PROV.Location))
                    # source
                    file_path = str(df_entry["altoXML"])
                    source_uri_name = file_path.replace("/", "_").replace(".", "_")
                    source_ref = URIRef("https://w3id.org/hto/InformationResource/" + source_uri_name)
                    graph.add((source_ref, RDF.type, hto.InformationResource))
                    graph.add((source_ref, PROV.value, Literal(file_path, datatype=XSD.string)))
                    graph.add((gazetteer_dataset, hto.hadMember, source_ref))
                    graph.add((source_ref, PROV.wasAttributedTo, nls))

                    # related agent and activity

                    """
                    source_digitalising_activity = URIRef("https://w3id.org/eb/Activity/nls_digitalising_activity" + source_name)
                    graph.add((source_digitalising_activity, RDF.type, PROV.Activity))
                    graph.add((source_digitalising_activity, PROV.generated, source_ref))
                    graph.add((source_digitalising_activity, PROV.wasAssociatedWith, nls))
                    graph.add((source_ref, PROV.wasGeneratedBy, source_digitalising_activity))
                    """
                    graph.add((entry_original_description, hto.wasExtractedFrom, source_ref))

                    ## startsAt
                    page_startsAt = URIRef("https://w3id.org/hto/Page/" + str(df_entry["MMSID"]) + "_" + str(
                        df_entry["volumeId"]) + "_" + str(df_entry["starts_at_page"]))
                    graph.add((page_startsAt, RDF.type, hto.Page))
                    graph.add((page_startsAt, hto.number, Literal(df_entry["starts_at_page"], datatype=XSD.int)))

                    graph.add((volume_ref, RDF.type, hto.WorkCollection))
                    graph.add((volume_ref, hto.hadMember, page_startsAt))
                    graph.add((entry_ref, hto.startsAtPage, page_startsAt))
                    graph.add((page_startsAt, RDF.type, hto.WorkCollection))
                    graph.add((page_startsAt, hto.hadMember, entry_ref))

                    ## endsAt
                    page_endsAt = URIRef("https://w3id.org/hto/Page/" + str(df_entry["MMSID"]) + "_" + str(
                        df_entry["volumeId"]) + "_" + str(df_entry["ends_at_page"]))
                    graph.add((page_endsAt, RDF.type, hto.Page))
                    graph.add((page_endsAt, hto.number, Literal(df_entry["ends_at_page"], datatype=XSD.int)))
                    graph.add((volume_ref, hto.hadMember, page_endsAt))
                    graph.add((entry_ref, hto.endsAtPage, page_endsAt))
                    graph.add((page_endsAt, RDF.type, hto.WorkCollection))
                    graph.add((page_endsAt, hto.hadMember, entry_ref))
    return dataframe


def is_record_match(mmsid, reference_name, record):
    record_mmsid = record['MMSID']
    record_names = []
    record_names.append(record['name'])
    record_names.extend(record['alter_names'])
    for index, record_name in enumerate(record_names):
        record_name = re.sub("[\s\-\.\(\)]", "", record_name)
        record_name = record_name.upper()
        record_names[index] = record_name
    reference_name = re.sub("[\s\s\-\.\(\)]", "", reference_name)
    reference_name = reference_name.upper()
    if mmsid == record_mmsid and reference_name in record_names:
        return True
    return False


def link_references(dataframe, graph):
    """
    Given a dataframe and a graph, return the graph with triples that links a term with its reference terms/article using refersTo property. the dataframe should have the column called reference_terms, a list of strings representing term/article names, uris.
    :param dataframe: dataframe with uris of current collection.
    :param graph: graph of current collection.
    :return: a graph with triples that links terms using refersTo property.
    """
    # 1. In dataframe, find all records that have non-empty reference-terms
    # 2. For each record, find the term URI in graph.
    # 3. then find all URIs of records in graph that have names which appears in reference-terms
    # 4. create triples with refersTo relation for record uri and reference uri.
    compare_df = dataframe
    df_with_references = dataframe[dataframe["reference_terms"].apply(
        lambda references: len(references) > 0 and references[0] != '')].reset_index(drop=True)
    total_unlinked_refs = 0
    total_linked_refs = 0
    for df_index in tqdm(range(0, len(df_with_references)), desc="Processing", unit="item"):
        # find the term URI in graph
        df_record = df_with_references.loc[df_index]
        record_uri = URIRef(str(df_record["uri"]))
        mmsid = df_record["MMSID"]
        references = df_record["reference_terms"]
        for reference in references:
            if reference == "":
                continue
            reference = reference
            references_df = compare_df[compare_df.apply(lambda row: is_record_match(mmsid, reference, row), axis=1)].reset_index(drop=True)
            if len(references_df) > 0:
                # One term should have only one reference term with specific name. If there are more than one terms have such name, then in theory, we should only take the term which is talking about the same topic. However, some term has no meaningful description except alternative names, or "See Term". In this case, there is no way to identify the topic, so we always take the first reference term found.
                refers_to = URIRef(str(references_df.loc[0]["uri"]))
                #print(references_df.loc[0]["name"], reference)
                total_linked_refs += 1
                # print(f"link {term_uri} in {edition_mmsid} to {refers_to}")
                graph.add((record_uri, hto.refersTo, refers_to))
            else:
                total_unlinked_refs += 1
                #print("Cannot find reference: " + reference)
    print(f"{total_unlinked_refs} unlinked references found, {total_linked_refs} linked references found")
    return graph


if __name__ == "__main__":
    print(f"Loading entity name pairs mapping file")
    name_map_file = "name_map.pickle"
    load_name_map(name_map_file)
    print(f"{len(name_map)} names pairs loaded")
    # create collection
    collection_name = "Gazetteers of Scotland"
    collection_id_name = "GazetteersofScotland"
    gaz_collection = create_collection(collection_name, collection_id_name)
    # create dataset entity
    gazetteer_dataset = create_dataset(collection_id_name, nls, "NLS")

    # load dataframe
    dataframe_files = ["sources/gaz_dataframe_1803",
                       "sources/gaz_dataframe_1806",
                       "sources/gaz_dataframe_1825",
                       "sources/gaz_dataframe_1838",
                       "sources/gaz_dataframe_1842",
                       "sources/gaz_dataframe_1846"]
    for dataframe_file in dataframe_files:
        print(f"Loading dataframe file {dataframe_file}....")
        gaz_df = pd.read_json(dataframe_file, orient='index')
        print(f"Loaded {len(gaz_df)} records loaded")

        print("Creating RDF triples....")
        # create main triples
        dataframe_with_uris = dataframe_to_rdf(gaz_collection, gaz_df, gazetteer_dataset)
        print("Linking see references....")
        link_references(dataframe_with_uris, graph)

    result_file = "results/gaz.ttl"
    print(f"Saving graph to {result_file}")
    graph.serialize(destination=result_file, format='turtle')

    print("Saving name pairs mapping file")
    save_name_map(name_map_file)

    print("Done")
