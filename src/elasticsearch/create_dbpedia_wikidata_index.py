from elasticsearch import Elasticsearch
import pandas as pd
from tqdm import tqdm
import config

client = Elasticsearch(
    config.ELASTIC_HOST,
    ca_certs=config.CA_CERT,
    api_key=config.ELASTIC_API_KEY
)

index = "wikidata_items"

mapping = {
    "mappings": {
        "properties": {
            "embedding": {
                "type": "dense_vector",
                "similarity": "cosine"
            },
            "item_uri": {"type": "keyword"},
            "concept_uri": {"type": "keyword"},
            "item_description": {"type": "text"}
        }
    }
}


if __name__ == "__main__":
    # Load the dataframe
    concept_df = pd.read_json("../knowledge_graph/results/gaz_concept_wikidata_df", orient="index")
    concept_df.drop(columns=["max_score"], inplace=True)
    # Create the index with the defined mapping
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=mapping)

    items_list = concept_df.to_dict('records')
    total = len(items_list)
    count = 0
    with tqdm(total=total, desc="Ingestion Progress", unit="step") as pbar:
        for doc in items_list:
            count += 1
            pbar.update(1)
            client.index(index=index, id=doc["item_uri"], document=doc)
