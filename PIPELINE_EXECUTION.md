# 🚀 Pipeline Execution Walkthrough

This document introduces all the details needed to run the pipeline mentioned above. All the scripts used are in [src](./src). In order to follow this guide, you will need to have:

* Required python environment and libraries installed, see [set up instructions](https://github.com/francesNLP/MappingChange?tab=readme-ov-file#%EF%B8%8F-setup-instructions).
* OpenAI API key.
* Fuseki Server hostname, credential (username and password) to login.
* Elasticsearch Server hostname, credential (certificate file, api key) to login.
* Base input dataframe of this collection, drop us an email for access.
* Edinburgh Geoparser library in this location: `src/geoparser/georesolve`, contact us for this resource.
* [Countries knowledge graph](https://doi.org/10.5281/zenodo.15361108), a knowledge graph based on HTO ontology for countries geo information.

Note: In our local enviroment we have created a  `files` folder where we placed the ouput data, as well as the [gazetteers_dataframe](https://drive.google.com/file/d/1J6TxdKImw2rNgmdUBN19h202gl-iYupn/view?usp=share_link) (dataframe with all extracted pages text across all gazetteers). We recommend to download the gazetters_dataframe from the previous link and place it in a `files` folder (inside `src` folder).

```shell
cd MappingChange/src
mkdir files
cd files
# place the dataframe in files folder
```

## LLM-based Multi-page Batched Article Extraction

**Script**: [extract_gaz_1803.py](./src/extract_gaz_1803.py), [extract_gaz_1806.py](./src/extract_gaz_1806.py) ....

**Input**: `src/files/gazatteers_dataframe` (json format): the base input dataframe of this collection, includes metadata and page level texts.

**Configuration**: 
```python
client = OpenAI(api_key="XXX") # change the api_key
```
**Execution**:
```shell
cd src
mkdir files/1803
mkdir files/1803/main
# take extract_gaz_1803.py for example
python extract_gaz_1803.py
# you need to run other extract_gaz_*.py scripts
```

**Output**: 
* A list of `src/files/1803/raw_extracted_articles_*_*.json` (json format): raw article segmentation result for various page ranges.
* A list of `src/files/1803/cleaned_articles_*_*.json` (json format): cleaned article segmentation result for various page ranges.


## Merging Articles Per Edition

**Script**: [merge_cleaned_articles.py](./src/merge_cleaned_articles.py)

**Input**: A list of `src/files/1803/cleaned_articles_*_*.json` (json format): cleaned article segmentation result for various page ranges (from [Extraction Scripts](#llm-based-multi-page-batched-article-extraction)).

**Configuration**: 
```python
INPUT_DIR = "./1803/json_final/" # Set your input directory of cleaned article segmentation json files
OUTPUT_FILE = "./1803/gazetteer_articles_merged_1803.json" # Set your output filepath
```

**Execution**:
```shell
cd src
mkdir 1803/json_final
cp files/1803/cleaned_articles* 1803/json_final/.
python merge_cleaned_articles.py
# You need change the INPUT_DIR and OUTPUT_FILE in the script for each different input folder, 
# and rerun this script
```
**Output**: 
* `src/files/1803/gazetteer_articles_merged_1803.json` (json format): merged results of all cleaned articles in the given input folder.


## Adding Metadata

**Script**: [dataframe_articles.py](./src/dataframe_articles.py)

**Input**:
* `src/files/gazatteers_dataframe` (json format): the base input dataframe of this collection, includes metadata and page level texts.
* `src/files/1803/gazetteer_articles_merged_1803.json` (json format): merged results of all cleaned articles in the given folder.

**Configuration**:

```python
client = OpenAI(api_key="XXX")  # change the api_key
...... 
json_path = "1803/gazetteer_articles_merged_1803.json" # change to the filepath of your merged articles result
......
g_df_fix.to_json(r'1803/gaz_dataframe_1803', orient="index") # change to the filepath for the result
```
**Execution**:
```shell
cd src
python dataframe_articles.py
# You need change the json_path and to_json output path in the script for each different input folder, 
# and rerun this script
```

**Output**: `src/files/1825/gaz_dataframe_1825` (json format): dataframe of further cleaned articles with associated metadata from page-level dataframe. 
You can access these dataframes that we have produced from [this section](README.md). 
Note that these dataframes are used for the knowledge graph generation scripts below.


## Combining Dataframes from different volumnes

If a gazetteer has more than 1 volume (e.g. 1838, 1842, etc ...) we need to combine the dataframes generated at the volumen level (with the steps from 1.1 to 1.3) into a single one.
In order to do that, we have the following script: 

**Script**: [combine_vol_dataframes.py](./src/combine_vol_dataframes.py)

**Input**:
* `src/files/1838_vol1/gaz_dataframe_1838_vol1` (json format): dataframe of further cleaned articles. 
* `src/files/1838_vol2/gaz_dataframe_1838_vol2` (json format): dataframe of further cleaned articles. 

**Configuration**:
```python
...... 
# Step 1: Load both DataFrames
df_vol1 = pd.read_json("1838_vol1/gaz_dataframe_1838_vol1", orient="index")
df_vol2 = pd.read_json("1838_vol2/gaz_dataframe_1838_vol2", orient="index")
......
df_combined.to_json("1838_combined/gaz_dataframe_1838", orient="index")
```
**Execution**:
```shell
cd src
mkdir files/1838_combined
python combine_vol_dataframes.py
# You need change the json_path and to_json output path in the script for each different input folder, 
# and rerun this script
```
**Output**: `src/files/1838_combined/gaz_dataframe_1838` (json format): dataframe of further cleaned articles. 
You can access these dataframes that we have produced from [this section](#dataframes-with-extracted-articles). 
Note that these dataframes are used for the knowledge graph generation scripts below.

## Core Graph Construction

**Script**: [df_to_kg.py](./src/knowledge_graph/df_to_kg.py)

**Input**: 
* A list of `src/knowledge_graph/sources/gaz_dataframe_*` (json format): dataframe generated from section [Adding Metadata](#adding-metadata)
* `src/knowledge_graph/hto.ttl` (turtle format): the HTO ontology file.
* `src/knowledge_graph/name_map.pickle` (pickle format): key-value pairs to map a string value to its ID, this ID is used to construct URI. 
This design ensures URIs generated are valid, also makes the graph generation idempotent.

**Configuration**:
```python
# Change the filepaths of input dataframes
dataframe_files = ["sources/gaz_dataframe_1803",
                   "sources/gaz_dataframe_1806",
                   "sources/gaz_dataframe_1825",
                   "sources/gaz_dataframe_1838",
                   "sources/gaz_dataframe_1842",
                   "sources/gaz_dataframe_1846", 
                   "sources/gaz_dataframe_1868", 
                   "sources/gaz_dataframe_1882", 
                   "sources/gaz_dataframe_1884", 
                   "sources/gaz_dataframe_1901", 
                   ]
```
**Execution**:
```shell
cd src/knowledge_graph
python df_to_kg.py
```
**Output**: `src/knowledge_graph/results/gaz.ttl` (turtle format): generated base knowledge graph in turtle format.

### Adding Page Permanent URLs

**Script**: [add_page_permanent_url.py](./src/knowledge_graph/add_page_permanent_url.py)

**Input**: 
* `src/knowledge_graph/volume_page_urls.json` (json format): json file with page permanent urls.
* `src/knowledge_graph/gaz.ttl` (turtle format): generated base knowledge graph from [Core Graph Constrcution](#core-graph-construction)

**Execution**:
```shell
cd src/knowledge_graph
python add_page_permanent_url.py
```

**Output** `src/knowledge_graph/gaz.ttl` (turtle format): basic knowledge graph with extract page permanent urls added.

## Uploading Knowledge to Fuseki SPARQL Server

If you don't have Fuseki server, install one locally using this [docker image](https://hub.docker.com/r/stain/jena-fuseki).
Note that only the latest working version is `stain/jena-fuseki:4.0.0`. This will deploy the fuseki powered web UI for easy interaction.

Make sure your fuseki server is running. Create a new dataset in the server if you want, or using existing dataset, 
then upload the `src/knowledge_graph/gaz.ttl` from [above](#adding-page-permanent-urls) to the dataset. 

To create a new dataset in fuseki server, in home page, click `manage` tab -> click `new dataset` tab -> enter dataset name ->
check in-memory option -> click `create dataset`

To upload data in the fuseki server, in home page, click `datasets` tab -> click `add data` button -> click `select files` button ->
 select `gaz.ttl` -> click `upload now` button

#### Valid the uploaded knowledge:
Click `query` button at the dataset we uploaded to, and run the following query:
```sparql
PREFIX hto: <https://w3id.org/hto#>
PREFIX schema: <https://schema.org/>
SELECT * WHERE {
    <https://w3id.org/hto/WorkCollection/GazetteersofScotland>  a hto:WorkCollection;
        schema:hasPart ?series.
    ?series a hto:Series;
        hto:mmsid ?mmsid;
        hto:title ?series_title;
        schema:hasPart ?volume.
    OPTIONAL {
        ?series hto:subtitle ?series_subtitle;
    }
    OPTIONAL {
        ?series hto:number ?series_number.
    }
    ?volume a hto:Volume;
        hto:title ?vol_title;
        hto:number ?vol_number;
        hto:volumeId ?vol_id;
        hto:permanentURL ?permanentURL.
} ORDER BY ?series_number
```
If everything works, it should return all the volumes in this collection.

Note that the SPARQL endpoint to query this dataset is `hostname/dataset_name`, for example: `http://localhost:3030/test_gaz`


## Knowledge Graph Dataframe Generation

**Script**: [kg_to_df.py](./src/knowledge_graph/kg_to_df.py)

**Input**: `http://localhost:3030/test_gaz`: SPARQL endpoint of fuseki dataset with gazetteer knowledge graph uploaded. 

**Configuration**: 
```python
sparql = SPARQLWrapper(
    "http://localhost:3030/test_gaz" # change the endpoint
)
```
**Execution**:
```shell
cd src/knowledge_graph
python kg_to_df.py
```
**Output**: `src/knowledge_graph/results/gazetteers_entry_kg_df` (json format): dataframe for uploaded graph in fuseki dataset.

## Embedding Generation

**Script**: [generate_embeddings.py](./src/knowledge_graph/generate_embeddings.py)

**Input**: `src/knowledge_graph/results/gazetteers_entry_kg_df` (json format): dataframe for uploaded graph in fuseki dataset from [above](#knowledge-graph-dataframe-generation).

**Execution**:
```shell
cd src/knowledge_graph
python generate_embeddings.py
```
**Output**: `src/knowledge_graph/results/gaz_kg_df_with_embeddings` (json format): the graph dataframe with embeddings.


## Linking Articles Across Edition

**Script**: [record_linkage.py](./src/knowledge_graph/record_linkage.py)

**Input**: `src/knowledge_graph/results/gaz_kg_df_with_embeddings` (json format): the graph dataframe with embeddings.

**Execution**
```shell
cd src/knowledge_graph
python record_linkage.py
```

**Output**: `src/knowledge_graph/results/gaz_kg_concepts_df` (json format): the graph dataframe with embeddings and concept uris.

## Linking Wikidata Items

**Script**: [wikidata_linkage.py](./src/knowledge_graph/wikidata_linkage.py)
**Input**: 
* `src/knowledge_graph/results/gaz_kg_concepts_df` (json format): the graph dataframe with embeddings and concept uris from [article linkage](#linking-articles-across-edition).

**Execution**
```shell
cd src/knowledge_graph
python wikidata_linkage.py
```

**Output**: 
* `src/knowledge_graph/results/gaz_concept_wikidata_df` (json format): dataframe for linked wikidata items with their names, descriptions, embeddings and concept uris.

## Linking Dbpedia Items

**Script**: [dbpedia_linkage.py](./src/knowledge_graph/dbpedia_linkage.py)

**Input**: 
* `src/knowledge_graph/results/gaz_kg_concepts_df` (json format): the updated graph dataframe with embeddings and updated concept uris from [wikidata linkage](#wikidata-linkage).

**Execution**
```shell
cd src/knowledge_graph
python dbpedia_linkage.py
```

**Output**: 
* `src/knowledge_graph/results/gaz_concept_dbpedia_df` (json format): dataframe for newly linked dbpedia items with their names, descriptions, embeddings and concept uris.


## Concept Linkage Enrichment Graph Creation

**Script**: [add_concepts_to_graph.py](./src/knowledge_graph/add_concepts_to_graph.py)

**Input**:
* `src/knowledge_graph/results/gaz_kg_concepts_df` (json format): the updated input graph dataframe from [articles linkage](#linking-articles-across-edition).
* `src/knowledge_graph/results/gaz_concept_dbpedia_df` (json format): dataframe for linked dbpedia items.
* `src/knowledge_graph/results/gaz_concept_wikidata_df` (json format): dataframe for linked wikidata items.

**Execution**:
```shell
cd src/knowledge_graph
python add_concepts_to_graph.py
```

**Output**: `src/knowledge_graph/results/gaz_extra_concepts_links.ttl` (turtle format): concept linkage enriched knowledge graph.

**Upload to the dataset in fuseki server**: Similar to [previous step](#uploading-knowledge-to-fuseki-sparql-server), upload the 
`src/knowledge_graph/results/gaz_extra_concepts_links.ttl` file to the previous dataset.

**Validate**: run the following SPARQL query to validate uploaded graph:
```sparql
PREFIX hto: <https://w3id.org/hto#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT * WHERE {
  ?concept a skos:Concept;
  	hto:hadConceptRecord ?record.
} LIMIT 20
```
If everything works, it should return concept uri along with their linked records (gazetteer articles, wikidata items, or dbpedia items).

## Location Annotations Input Dataframe Generation

**Script**: [kg_to_df.py](./src/geoparse/kg_to_df.py)

**Input**: `http://localhost:3030/test_gaz`: SPARQL endpoint of fuseki dataset with gazetteer knowledge graph uploaded. 

**Configuration**: 
```python
sparql = SPARQLWrapper(
    "http://localhost:3030/test_gaz" # change the endpoint
)
```

**Execution**:
```shell
cd src/geoparser
python kg_to_df.py
```

**Output**: `src/geoparser/sources/gaz_articles_simple.json` (json format): dataframe for uploaded graph in fuseki dataset, 
this dataframe only minial types of data needed for location annotation enrichment, including article uris, article names, descriptions , description uris and published years.

## Geotagging

**Script**: [geotag.py](./src/geoparse/geotag.py)

**Input**: `src/geoparser/sources/gaz_articles_simple.json` (json format): output dataframe from [above step](#location-annotations-input-dataframe-generation)

**Execution**:
```shell
cd src/geoparser
python geotag.py
```

**Output**: `src/geoparser/results/geotagged_articles_df.json` (json format): input dataframe with geotagged locations.

## Georesoltion

**Script**: [georesolve.py](./src/geoparse/georesolve.py)

**Input**: `src/geoparser/sources/geotagged_articles_df.json` (json format): output dataframe from [above step](#geotagging)

**Execution**:
```shell
cd src/geoparser
python georesolve.py
```

**Output**: `src/geoparser/results/georesolved_df.json` (json format): input dataframe with georesolved information.

## Location Annotations Enriched Graph Generation

**Script**: [add_location_annotations.py](./src/knowledge_graph/add_location_annotations.py)

**Input**: 
* `src/geoparser/results/georesolved_df.json` (json format): output dataframe from [above step](#geotagging)
* `src/knowledge_graph/sources/countries_info.json` (json format): required dataframe with basic countries information 
from the required countries knowledge graph. 

**Execution**:
```shell
cd src/geoparser
python add_location_annotations.py
```

**Output**: `src/geoparser/results/gaz_locations_annotations.ttl` (turtle format): location annotations enriched knowledge graph.

**Upload to the dataset in fuseki server**: Similar to [previous step](#uploading-knowledge-to-fuseki-sparql-server), upload the 
`src/knowledge_graph/results/gaz_extra_concepts_links.ttl` file and also the countries knowledge graph to the previous dataset.

**Validate**: You can validate the uploaded graph by running the queries specifed in [KG_ES_USAGE.md](./KG_ES_USAGE.md)



## Gazetteers Index Creation

**Script**: [create_gaz_index.py](./src/elasticsearch/create_gaz_index.py)

**Inputs**:
* `src/knowledge_graph/results/gaz_kg_concepts_df` (json format): the updated graph dataframe from [articles linkage](#articles-linkage).

**Configuration**:

In `src/elasticsearch/config.py`:
```python
ELASTIC_HOST = "https://elastic.frances-ai.com:9200/" # change to your elasticsearch host
CA_CERT = "your_path/src/elasticsearch/ca.crt" # change to your certificate filepath 
ELASTIC_API_KEY = "your_api_key" # change to your api key
```

In `src/elasticsearch/create_gaz_index.py`:
```python
index = "test_gazetteers" # change the index name
```

**Execution**:

```shell
cd src/elasticsearch
# Run create_gaz_index.py to create index for gazetteers articles
python create_gaz_index.py

```
If everything works, you should see created index in the kibana interface, web interface for interaction with elasticsearch server.


## Wikidata Index and DBpedia Index Creation

**Scripts**: [create_dbpedia_wikidata_index.py](./src/elasticsearch/create_dbpedia_wikidata_index.py)

**Inputs**: 
* `src/knowledge_graph/results/gaz_concept_dbpedia_df` from [dbpedia linkage](#dbpedia-linkage) 
* `src/knowledge_graph/results/gaz_concept_wikidata_df` from [wikidata linkage](#wikidata-linkage)


**Configuration**:
In `src/elasticsearch/create_dbpedia_wikidata_index.py`:
```python
index = "test_gazetteers" # change the index name
...... 
# change input dataframe filepath
concept_df = pd.read_json("../knowledge_graph/results/gaz_concept_wikidata_df", orient="index")
```


**Execution**:

```shell
cd src/elasticsearch

# Configurate the create_dbpedia_wikidata_index.py for wikidata items and run it
python create_dbpedia_wikidata_index.py

# Configurate the create_dbpedia_wikidata_index.py for dbpedia items and run it
python create_dbpedia_wikidata_index.py
```

If everything works, you should see created index in the kibana interface, web interface for interaction with elasticsearch server.

**Validate**: You can validate the uploaded graph by running the queries specifed in [KG_ES_USAGE.md](./KG_ES_USAGE.md)


## 📥 Access or Download Pre-Built Knowledge Graphs

You can either download the knowledge graphs produced by this pipeline or access them via our live Fuseki SPARQL endpoint.

### 🔗 Online SPARQL Endpoint

The final enriched knowledge graph is deployed and queryable at this web UI http://yasgui.org/short/0M7HXSruJg, the SPARQL endpoint is 
http://query.frances-ai.com/hto_gaz/sparql

🧪 See our usage notebook for worked examples:
🧪 See our usage notebook for worked examples:
👉 [`Knowledge_Exploration_SPARQL.ipynb`](https://github.com/francesNLP/MappingChange/blob/main/Notebooks/Knowledge_Exploration_SPARQL.ipynb) — uses this endpoint to query Gazetteer entries, places, references, and enriched metadata.

---

### 💾 Direct Downloads

| File | Description |
|------|-------------|
| [`gaz.ttl`](https://drive.google.com/file/d/1fbpFu8ts7hPOsGAq8SUaiJn6IOZ73zez/view?usp=share_link) | Main Gazetteers KG: article-level concepts, metadata, and redirects |
| [`gaz_locations_annotations.ttl`](https://drive.google.com/file/d/1vnYZEeiLjcfwgkHyJG4l9OECuwtvY1yy/view?usp=share_link) | Gazetteer entries annotated with location/georesolution data |
| [`gaz_extra_concepts_links.ttl`](https://drive.google.com/file/d/1UeT8v9Avwk0dlqPx_ZD5-IxOFpOgAyX7/view?usp=share_link) | Links to external sources (e.g., Wikidata, DBpedia) via semantic enrichment |

These files can be uploaded to your own SPARQL server or used offline in any RDF-compatible tool.
