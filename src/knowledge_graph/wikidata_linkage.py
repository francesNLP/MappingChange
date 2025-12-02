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


# Initialise a sparqlwrapper for Wikidata
user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
wikidata_endpoint_url = "https://query.wikidata.org/sparql"
wikidata_sparql = SPARQLWrapper(endpoint=wikidata_endpoint_url, agent=user_agent)


def get_wikidata_item_by_name(item_name):
    # Inverts a name from the format 'Last, Prefix' to 'Prefix Last'.
    items = []
    item_valid_names = [item_name.title(), item_name.lower()]
    inverted_name = invert_name(item_name)
    if inverted_name != item_name:
        item_valid_names.append(inverted_name.title())
        item_valid_names.append(inverted_name.lower())
    for item_valid_name in item_valid_names:
        wd_term_search_query = """
        SELECT distinct ?item ?itemDescription WHERE{
          ?item ?label "%s"@en.
          FILTER (?label = rdfs:label || ?label = skos:altLabel)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """ % item_valid_name
        wikidata_sparql.setQuery(wd_term_search_query)
        wikidata_sparql.setReturnFormat(JSON)
        wd_term_search_results = wikidata_sparql.query().convert()
        for result in wd_term_search_results["results"]["bindings"]:
            if "itemDescription" in result:
                items.append({
                    "uri": result['item']['value'],
                    "description": result['itemDescription']['value']
                })
    return items


def get_most_similar_item(query_embedding, wiki_items):
    item_embeddings = [item["embedding"] for item in wiki_items]
    similarities = cosine_similarity([query_embedding], item_embeddings)
    #print(similarities)
    # Find the index of the most similar item
    most_similar_index = np.argmax(similarities)
    score = similarities[0][most_similar_index]
    #print(score)
    return score, wiki_items[most_similar_index]


def link_wikidata_with_concept(df):
    concept_uris = df["concept_uri"].unique()
    all_searched_wiki_items = {}
    concept_wiki_items = {}
    exception_concept_uris = []
    for concept_uri in tqdm(concept_uris):
        records_df = df[df["concept_uri"] == concept_uri]
        records_df = records_df.sort_values(by="year_published", ascending=False)
        # get the latest (the largest year) record info
        latest_record_df = records_df.iloc[0]
        record_name = latest_record_df["record_name"]
        embedding = latest_record_df["embedding"]
        #print(record_name)
        #print(latest_record_df["description"])
        # get wiki items, and their embeddings
        wiki_items = []
        if record_name in all_searched_wiki_items:
            wiki_items = all_searched_wiki_items[record_name]
        else:
            try:
                wiki_items = get_wikidata_item_by_name(record_name)
                # get embeddings for each item
                items_descriptions = [item["description"] for item in wiki_items]
                #print(items_descriptions)
                item_embeddings = model.encode(items_descriptions).tolist()
                # Add each embedding to its corresponding item
                for wiki_item, wiki_embedding in zip(wiki_items, item_embeddings):
                    wiki_item['embedding'] = wiki_embedding
                all_searched_wiki_items[record_name] = wiki_items
            except:
                exception_concept_uris.append(concept_uri)
        if len(wiki_items) > 0:
            score, most_similar_wiki_item = get_most_similar_item(embedding, wiki_items)
            #print(most_similar_wiki_item["description"])
            item_uri = most_similar_wiki_item["uri"]
            if score > 0.4:
                # check if wikidata item has been added
                if item_uri in concept_wiki_items:
                    concept_wiki_items[item_uri]["concept_uri"].append(concept_uri)
                else:
                    concept_wiki_items[item_uri] = {
                        "concept_uri": [concept_uri],
                        "item_uri": item_uri,
                        "item_description": most_similar_wiki_item["description"],
                        "embedding": most_similar_wiki_item["embedding"]
                    }

    return exception_concept_uris, concept_wiki_items


if __name__ == "__main__":
    kg_df_filename = "results/gaz_kg_concepts_df"
    print(f"Loading the source dataframe {kg_df_filename} .....")
    kg_df = pd.read_json(kg_df_filename, orient="index")
    print("Linking wikidata items.......")
    exception_concept_uris, concept_wiki_items = link_wikidata_with_concept(kg_df)
    concept_wiki_item_list = list(concept_wiki_items.values())
    concept_wiki_item_df = pd.DataFrame(concept_wiki_item_list)
    result_wiki_df_filename = "results/gaz_concept_wikidata_df"
    print(f"Saving the wikidata linking result to file: {result_wiki_df_filename}")
    concept_wiki_item_df.to_json(result_wiki_df_filename, orient="index")
    if len(exception_concept_uris) > 0:
        exception_concept_uris_file = "wiki_exception_concept_uris.pkl"
        print(f"Saving the exception concept uris to file: {exception_concept_uris_file}")
        with open(exception_concept_uris_file, 'wb') as f:
            pickle.dump(exception_concept_uris, f)



