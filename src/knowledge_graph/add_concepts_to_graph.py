import pandas as pd
from rdflib import Graph, Namespace, RDF, URIRef, SKOS, RDFS, Literal, XSD
from tqdm import tqdm
import re
import string

# Load the existing graph
graph = Graph()
graph.parse(location="hto.ttl", format="turtle")

hto = Namespace("https://w3id.org/hto#")

def record_links(kg_df_with_concept_uris):
    concept_uris = kg_df_with_concept_uris["concept_uri"].unique()
    for concept_uri in tqdm(concept_uris):
        if concept_uri:
            concept_records_df = kg_df_with_concept_uris[kg_df_with_concept_uris["concept_uri"] == concept_uri]
            concept_uriref = URIRef(concept_uri)
            graph.add((concept_uriref, RDF.type, SKOS.Concept))
            concept_label = ""
            for index, row in concept_records_df.iterrows():
                record_uri_ref = URIRef(row["record_uri"])
                if concept_label == "":
                    record_name = row["record_name"]
                    # normalise name
                    concept_label = re.sub("[\s\-\.\(\)]", "", record_name)
                    concept_label = string.capwords(concept_label)
                graph.add((concept_uriref, hto.hasConceptRecord, record_uri_ref))
            if concept_label != "":
                graph.add((concept_uriref, RDFS.label, Literal(concept_label, datatype=XSD.string)))
        else:
            print("None")

def external_link(concept_item_df, type_uri):
    for index, row in concept_item_df.iterrows():
        concept_uris = row["concept_uri"]
        item_uri = row["item_uri"]
        for concept_uri in concept_uris:
            #print(concept_uri, item_uri)
            concept_uriref = URIRef(concept_uri)
            item_uriref = URIRef(item_uri)
            graph.add((item_uriref, RDF.type, hto.ExternalRecord))
            graph.add((item_uriref, RDF.type, hto.ConceptRecord))
            graph.add((item_uriref, hto.hasAuthorityType, type_uri))
            graph.add((concept_uriref, hto.hasConceptRecord, item_uriref))


if __name__ == "__main__":
    # add record links
    print("Loading the source dataframe gaz dataframe with concept uris .....")
    df_with_concept_uris = pd.read_json("results/gaz_kg_concepts_df", orient="index")
    print("Adding links from location records to concepts .....")
    record_links(df_with_concept_uris)
    #graph.serialize(format="turtle", destination="gaz_extra_concepts_records_link.ttl")

    # add wikidata links
    print("Loading the wikidata items dataframe .....")
    concept_wiki_df = pd.read_json("results/gaz_concept_wikidata_df", orient="index")
    print("Adding links from wikidata items to concepts .....")
    external_link(concept_wiki_df, hto.WikidataItem)
    #graph.serialize(format="turtle", destination="gaz_extra_concepts_wikidata_link.ttl")

    # add dbpedia links
    print("Loading the dbpedia items dataframe .....")
    concept_dbpedia_df = pd.read_json("results/gaz_concept_dbpedia_df", orient="index")
    print("Adding links from dbpedia items to concepts .....")
    external_link(concept_dbpedia_df, hto.DBpediaItem)

    result_graph_filepath = "results/gaz_extra_concepts_links.ttl"
    print(f"Saving the result graph to {result_graph_filepath} .....")
    graph.serialize(format="turtle", destination=result_graph_filepath)
    print("Done")
