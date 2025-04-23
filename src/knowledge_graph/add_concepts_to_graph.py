import pandas as pd
from rdflib import URIRef, RDF, Literal, XSD
from tqdm import tqdm

# load the graph
from rdflib import Graph, Namespace, RDF

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
            graph.add((concept_uriref, RDF.type, hto.Concept))
            for index, row in concept_records_df.iterrows():
                record_uri_ref = URIRef(row["record_uri"])
                graph.add((concept_uriref, hto.hadConceptRecord, record_uri_ref))

        else:
            print("None")

def external_link(concept_item_df):
    for index, row in concept_item_df.iterrows():
        concept_uri = row["concept_uri"]
        item_uri = row["item_uri"]
        print(concept_uri, item_uri)
        concept_uriref = URIRef(concept_uri)
        item_uriref = URIRef(item_uri)
        graph.add((item_uriref, RDF.type, hto.ExternalRecord))
        graph.add((concept_uriref, hto.hadConceptRecord, item_uriref))


if __name__ == "__main__":
    # add record links
    df_with_concept_uris = pd.read_json("gaz_kg_concepts_df", orient="index")
    record_links(df_with_concept_uris)
    graph.serialize(format="turtle", destination="gaz_extra_concepts_records_link.ttl")

    # add wikidata links
    # concept_wiki_df = pd.read_json("gaz_concept_wikidata_df", orient="index")
    # external_link(concept_wiki_df)
    # graph.serialize(format="turtle", destination="gaz_extra_concepts_wikidata_link.ttl")


    # add dbpedia links
    # concept_dbpedia_df = pd.read_json("gaz_concept_dbpedia_df", orient="index")
    # external_link(concept_dbpedia_df)
    # graph.serialize(format="turtle", destination="gaz_extra_concepts_dbpedia_link.ttl")
