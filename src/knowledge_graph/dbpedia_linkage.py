import pickle

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
import sys
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

model = SentenceTransformer('all-mpnet-base-v2')
model._first_module().max_seq_length = 509


def invert_name(name: str) -> str:
    """
    Inverts a name from the format 'Last, Prefix' to 'Prefix Last'.

    Parameters:
    name (str): The name to be inverted.

    Returns:
    str: The inverted name.
    """
    # Split the name by ', ' to handle the inversion
    parts = name.split(', ')
    if len(parts) == 2:
        # Invert the order and join without a comma for cases like "Andrews, St"
        inverted_name = f"{parts[1]} {parts[0]}"
    else:
        # Return the original name if it doesn't match the expected pattern
        inverted_name = name

    return inverted_name


# Initialise a sparqlwrapper for dbpedia
user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
dbpedia_endpoint_url = "https://dbpedia.org/sparql/"
dbpedia_sparql = SPARQLWrapper(endpoint=dbpedia_endpoint_url, agent=user_agent)


def get_dbpedia_item_by_name(item_name):
    # Inverts a name from the format 'Last, Prefix' to 'Prefix Last'.
    items = []
    item_valid_names = [item_name.title(), item_name.lower()]
    inverted_name = invert_name(item_name)
    if inverted_name != item_name:
        item_valid_names.append(inverted_name.title())
        item_valid_names.append(inverted_name.lower())
    for item_valid_name in item_valid_names:
        wd_term_search_query = """
            SELECT * WHERE {
                ?item rdfs:label "%s"@en.
                ?item dbo:abstract ?abstract.
                FILTER (lang(?abstract) = "en")
            }
        """ % item_valid_name
        dbpedia_sparql.setQuery(wd_term_search_query)
        dbpedia_sparql.setReturnFormat(JSON)
        dbpedia_term_search_results = dbpedia_sparql.query().convert()
        for result in dbpedia_term_search_results["results"]["bindings"]:
            if "abstract" in result:
                items.append({
                    "uri": result['item']['value'],
                    "description": result['abstract']['value']
                })
    return items


def get_most_similar_item(query_embedding, dbpedia_items):
    item_embeddings = [item["embedding"] for item in dbpedia_items]
    similarities = cosine_similarity([query_embedding], item_embeddings)
    #print(similarities)
    # Find the index of the most similar item
    most_similar_index = np.argmax(similarities)
    score = similarities[0][most_similar_index]
    #print(score)
    return score, dbpedia_items[most_similar_index]


def link_dbpedia_with_concept(df):
    concept_uris = df["concept_uri"].unique()
    all_searched_dbpedia_items = {}
    concept_dbpedia_items = {}
    exception_concept_uris = []
    for concept_uri in tqdm(concept_uris):
        records_df = df[df["concept_uri"] == concept_uri]
        records_df = records_df.sort_values(by="year_published", ascending=False)
        # get the latest (the largest year) term info
        latest_record_df = records_df.iloc[0]
        record_name = latest_record_df["record_name"]
        embedding = latest_record_df["embedding"]
        dbpedia_items = []
        if record_name in all_searched_dbpedia_items:
            dbpedia_items = all_searched_dbpedia_items[record_name]
        else:
            try:
                dbpedia_items = get_dbpedia_item_by_name(record_name)
                # get embeddings for each item
                items_descriptions = [item["description"] for item in dbpedia_items]
                #print(items_descriptions)
                item_embeddings = model.encode(items_descriptions).tolist()
                # Add each embedding to its corresponding item
                for dbpedia_item, dbpedia_embedding in zip(dbpedia_items, item_embeddings):
                    dbpedia_item['embedding'] = dbpedia_embedding
                all_searched_dbpedia_items[record_name] = dbpedia_items
            except:
                exception_concept_uris.append(concept_uri)
        if len(dbpedia_items) > 0:
            score, most_similar_dbpedia_item = get_most_similar_item(embedding, dbpedia_items)
            #print(most_similar_wiki_item["description"])
            item_uri = most_similar_dbpedia_item["uri"]
            if score > 0.4:
                # check if dbpedia item has been added
                if item_uri in concept_dbpedia_items:
                    existing_dbpedia_item_record = concept_dbpedia_items[item_uri]
                    if existing_dbpedia_item_record["max_score"] < score:
                        concept_dbpedia_items[item_uri] = {
                            "concept_uri": concept_uri,
                            "item_uri": item_uri,
                            "item_description": most_similar_dbpedia_item["description"],
                            "max_score": score,
                            "embedding": most_similar_dbpedia_item["embedding"]
                        }
                else:
                    concept_dbpedia_items[item_uri] = {
                        "concept_uri": concept_uri,
                        "item_uri": item_uri,
                        "item_description": most_similar_dbpedia_item["description"],
                        "max_score": score,
                        "embedding": most_similar_dbpedia_item["embedding"]
                    }

    return exception_concept_uris, concept_dbpedia_items


if __name__ == "__main__":
    print("Loading the source dataframe .....")
    kg_df_filename = "results/gaz_kg_concepts_df"
    kg_df = pd.read_json(kg_df_filename, orient="index")
    print("Linking dbpedia items.......")
    exception_concept_uris, concept_dbpedia_items = link_dbpedia_with_concept(kg_df)
    concept_dbpedia_item_list = list(concept_dbpedia_items.values())
    concept_dbpedia_item_df = pd.DataFrame(concept_dbpedia_item_list)
    result_dbpedia_df_filename = "results/gaz_concept_dbpedia_df"
    print(f"Saving the dbpedia linking result to file: {result_dbpedia_df_filename}")
    concept_dbpedia_item_df.to_json(result_dbpedia_df_filename, orient="index")
    if len(exception_concept_uris) > 0:
        exception_concept_uris_file = "dbpedia_exception_concept_uris.pkl"
        print(f"Saving the exception concept uris to file: {exception_concept_uris_file}")
        with open(exception_concept_uris_file, 'wb') as f:
            pickle.dump(exception_concept_uris, f)



