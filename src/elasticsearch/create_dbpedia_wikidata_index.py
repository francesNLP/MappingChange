from typing import Iterable, Dict

from elasticsearch import Elasticsearch, helpers
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


def actions_from_list(docs: Iterable[Dict]) -> Iterable[Dict]:
    for doc in docs:
        yield {
            "_index": index,
            "_id": doc["item_uri"],
            "_op_type": "index",  # use "create" to fail on dup ids instead
            "_source": doc,
        }


def refresh_quietly():
    try:
        client.indices.refresh(index=index)
    except Exception:
        pass


if __name__ == "__main__":
    # Load the dataframe
    concept_df = pd.read_json("../knowledge_graph/results/gaz_concept_wikidata_df", orient="index")
    concept_df.drop(columns=["max_score"], inplace=True)
    # Create the index with the defined mapping
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=mapping)

    items_list = concept_df.to_dict('records')
    total = len(items_list)

    thread_count = 4
    chunk_size = 100
    success = 0
    with tqdm(total=total, desc=f"Processing ingestion", unit="doc") as pbar:
        for ok, info in helpers.parallel_bulk(
                client,
                actions_from_list(items_list),
                thread_count=thread_count,
                chunk_size=chunk_size,
                raise_on_error=False,
                raise_on_exception=False,
        ):
            if ok:
                success += 1
            else:
                print('A document failed:', info)
            pbar.update(1)

    refresh_quietly()
