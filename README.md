# 🗺️ MappingChange
## Tracking the Evolution of Place Descriptions in the Gazetteers of Scotland (1803–1901)
This repository supports a research project to transform [The Gazetteers of Scotland (1803–1901)](https://data.nls.uk/data/digitised-collections/gazetteers-of-scotland/), digitized by the National Library of Scotland, into structured article-level data. These gazetteers provide detailed historical accounts of Scottish places—towns, glens, castles, and parishes—captured across 21 volumes:
  
![NumVolGaz1803_1901](https://github.com/user-attachments/assets/b81dca6b-87c7-4468-b0f4-caeb1e76d3bb)


  

The goal is to extract these entries from OCR-based page-level text and convert them into cleaned, deduplicated article records that can eventually populate a temporal and semantic knowledge graph (ScotGaz19-KG). This graph will be integrated into the [Frances platform](http://www.frances-ai.com), enabling rich visualizations and advanced NLP-driven analysis of Scotland’s historical landscape.

This work forms part of the RSE-funded project and builds on prior research funded by the National Library of Scotland.

## Set Up the Environment
### Step 1: Create the environment with Python 3.11

```
conda create -n gazetteer_env python=3.11 -y
```
### Step 2: Activate the environment
```
conda activate gazetteer_env
```

### Step 3: Install required libraries

```
pip install -r requirements.txt
```

## 📚 Gazetteer Article Extraction 

This repository contains a set of scripts for extracting, processing, and cleaning historical article entries from multiple editions of the Gazetteers of Scotland. These Gazetteers are digitized historical documents structured as page-by-page OCR-extracted text. The aim is to extract individual location-based entries (articles), correct common OCR issues, and resolve duplicates across pages and editions.

The scripts used this repo support:

* Entry-level extraction of articles from OCR-ed pages using GPT-4
* Cleaning and deduplication of overlapping or fragmented entries
* Metadata enrichment from the original XML files (via the dataframe)
* Preparation for integration into a knowledge graph (HTO-compliant)

## 🗂️ Pipeline Overview

We are using the dataframe version of this [KnowledgeGraph](https://zenodo.org/records/14051678) as an input data from our pipeline. If you want to have access to it, drop us an email. 

 1. Extraction Scripts ([extract_gaz_1803.py](./src/extract_gaz_1803.py), [extract_gaz_1806.py](./src/extract_gaz_1806.py) ....): 	Main scripts for processing the respective editions. They extract articles from specific page ranges, send chunked prompts to OpenAI’s GPT-4 for article segmentation, and save both raw and cleaned JSON results. Different prompts are used across different scripts, since the format of the books (pages headers, articles names, descriptions) change over years. 

 2. [Merging Cleaning Data](./src/merge_cleaned_articles.py): Merges all the cleaned JSON article files into a single output file, sorting and aligning metadata across the dataset.

 3. [Dataframe Generation](./src/dataframe_articles.py):A	Script that deduplicates and cleans already extracted articles. It includes advanced logic to detect fuzzy duplicates, substring containment, and prefix-based similarity across multiple pages. It also adds metadata from the original OCR dataset. These are then exported and analyzed in Jupyter/Colab notebooks.


All these scripts used are in [src](./src).

## Dataframes with Extracted Articles

These cleaned, deduplicated DataFrames (as a result of running[dataframe_articles.py](./src/dataframe_articles.py) wich each dataset) are ready for semantic enrichment and visual analysis:

* [dataframe_gaz_1803](https://drive.google.com/file/d/1a4BtLrwyfHb4I6cmAVbaaw-IafWf1dnR/view?usp=share_link)
* [dataframe_gaz_1806](https://drive.google.com/file/d/1ZGt8hKzQ2rvk_-dlVHpn6UwoSkiZyNDO/view?usp=share_link)
* [dataframe_gaz_1825](https://drive.google.com/file/d/1Fsr61JqpV4JND0VKtezbNoVCrdw_Ahi4/view?usp=share_link)
* [dataframe_gaz_1838](https://drive.google.com/file/d/1g5xCuG_eAJp0GQNfDDTpwSK4ndqTz-G_/view?usp=share_link)
* [dataframe_gaz_1842](https://drive.google.com/file/d/1dNJaS9RWHOvP3vsfy5ZDE6SCiVeSiRj_/view?usp=share_link)


## Google Colabs

* Explore extracted articles from [1803: Gazetteer of Scotland](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97343436) -->  [Google Colab Notebook](https://colab.research.google.com/drive/1EGzcmjiDNEJNkAUfMjsqZis0k1ZVjzYh?usp=sharing)
* Explore extracted articles from [1806: Gazetteer of Scotland: containing a particular and concise description of the counties, parishes, islands, cities with maps](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97414570) --> [Google Colab Notebook](https://colab.research.google.com/drive/1EfqonO3p6XGCxEXyEohUU5uQD7BlIQRr?usp=sharing) 

* Explore extracted articles from [1825: Gazetteer of Scotland: arranged under the various descriptions of counties, parishes, islands -- 1 volume](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97421702) --> [Google Colab Notebook](https://colab.research.google.com/drive/1CVd40bNGe-RAuPmv1M07tEjSWC5-wcgs?usp=sharing)
* Explore extracted articles from [1838: Gazetteer of Scotland with plates and maps -- 2 volumes](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97491771) --> [Google Colab Notebook](https://colab.research.google.com/drive/1_OJ2ZA-TksnVwW9QRPyU8iJUEkBBHAlY?usp=sharing)


### Comparative 
As a result, we can already do experiment with some analyses in this [Google Colab](https://colab.research.google.com/drive/1mmspC8c1FcYOOY9-wqH4TU8qKVNtFQE1?usp=sharing)
<img width="1192" alt="Screenshot 2025-04-09 at 18 59 03" src="https://github.com/user-attachments/assets/d7784a58-a3a9-464d-bc78-9d1edbfe6d8f" />

<img width="1227" alt="Screenshot 2025-04-09 at 19 01 23" src="https://github.com/user-attachments/assets/437b5007-b824-4190-8617-512340658b3e" />


## ✨ Research Context

This work contributes to the ScotGaz19-KG initiative: building a temporal and semantic knowledge graph of 19th-century Scottish place descriptions. It enables researchers to:

- Analyze the evolution of geographical and cultural narratives
- Compare local descriptions in the Gazetteers with national perspectives in the Encyclopaedia Britannica
- Link and cluster places across editions and sources using NLP and semantic matching
- The extracted articles will be integrated into Frances, an AI-driven platform for historical text analysis hosted at the Edinburgh International Data Facility (EIDF).
