from elasticsearch import Elasticsearch
import pandas as pd
from tqdm import tqdm

import config

client = Elasticsearch(
    config.ELASTIC_HOST,
    ca_certs=config.CA_CERT,
    api_key=config.ELASTIC_API_KEY
)

index = "test_gazetteers"

settings = {
    "analysis": {
            "analyzer": {
                "default": {
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "kstem",
                        "stop"
                    ]
                },
                "default_search": {
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "kstem",
                        "stop"
                        # synonym_graph
                    ]
                }
            }
        }
}

mappings = {
    "properties": {
        "embedding": {
            "type": "dense_vector",
            "similarity": "cosine"
        },
        "collection": {"type": "constant_keyword", "value": "Gazetteers of Scotland"},
        "series_uri": {"type": "keyword"},
        "vol_num": {"type": "integer"},
        "vol_title": {"type": "keyword"},
        "genre": {"type": "keyword"},
        "print_location": {"type": "keyword"},
        "year_published": {"type": "integer"},
        "series_num": {"type": "integer"},
        "name": {"type": "text",
                 "fields": {
                     "keyword": {
                         "type": "keyword"
                     }
            }
        },
        "alter_names": {"type": "text"},
        "start_page_num": {"type": "integer"},
        "end_page_num": {"type": "integer"},
        "references": {
            "type": "nested",
            "properties": {
                "uri": {"type": "keyword"},
                "name": {"type": "text"}
            }
        },
        "concept_uri": {"type": "keyword"},
        "description": {"type": "text"},
        "description_uri": {"type": "keyword"},
    }
}


if __name__ == "__main__":
    # Load the dataframe
    gazetteers_dataframe = pd.read_json("../knowledge_graph/results/gaz_concepts_df", orient="index")
    gazetteers_dataframe["year_published"] = gazetteers_dataframe["year_published"].fillna(-1)
    gazetteers_dataframe.rename(columns={"record_name": "name"}, inplace=True)
    gazetteers_dataframe['collection'] = 'Gazetteers of Scotland'
    # Create the index with the defined mapping
    if not client.indices.exists(index=index):
        client.indices.create(index=index, mappings=mappings, settings=settings)

    record_list = gazetteers_dataframe.to_dict('records')
    total = len(record_list)
    count = 0
    with tqdm(total=total, desc="Ingestion Progress", unit="step") as pbar:
        for doc in record_list:
            count += 1
            pbar.update(1)
            client.index(index=index, id=doc["record_uri"], document=doc)
