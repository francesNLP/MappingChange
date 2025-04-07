# 🗺️ MappingChange: Tracking the Evolution of Place Descriptions in the Gazetteers of Scotland (1803–1901)
Repository to map the change of the gazetteers of Scotland (1803 to 1901)

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

## 📚 Gazetteer Article Extraction and Cleaning Pipeline

This repository contains a set of scripts for extracting, processing, and cleaning historical article entries from multiple editions of the Gazetteers of Scotland. These Gazetteers are digitized historical documents structured as page-by-page OCR-extracted text. The aim is to extract individual location-based entries (articles), correct common OCR issues, and resolve duplicates across pages and editions.

## 🗂️ Structure of the src/ Folder

* extract_gaz_1803.py, extract_gaz_1806.py extract_gaz_1825.py, extract_gaz_1838.py: 	Main scripts for processing the respective editions. They extract articles from specific page ranges, send chunked prompts to OpenAI’s GPT-4 for article segmentation, and save both raw and cleaned JSON results.

* merge_cleaned_articles.py: Merges all the cleaned JSON article files into a single output file, sorting and aligning metadata across the dataset.

* dataframe_articles.py:A	Script that deduplicates and cleans already extracted articles. It includes advanced logic to detect fuzzy duplicates, substring containment, and prefix-based similarity across multiple pages. It also adds metadata from the original OCR dataset. The results of running this script are processed later in our Google Colab Notebooks. In the next section of this Readme you have the links to download those dataframes. 

All these scripts used are in [src](!./src).

## Dataframes with Extracted Articles

* [dataframe_gaz_1803](https://drive.google.com/file/d/1a4BtLrwyfHb4I6cmAVbaaw-IafWf1dnR/view?usp=share_link)
* [dataframe_gaz_1806](https://drive.google.com/file/d/1a4BtLrwyfHb4I6cmAVbaaw-IafWf1dnR/view?usp=share_link)
* [dataframe_gaz_1825](https://drive.google.com/file/d/1Fsr61JqpV4JND0VKtezbNoVCrdw_Ahi4/view?usp=share_link)


# Google Colabs

* Explore extracted articles from [1803: Gazetteer of Scotland](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97343436) -->  [Google Colab Notebook](https://colab.research.google.com/drive/1EGzcmjiDNEJNkAUfMjsqZis0k1ZVjzYh?usp=sharing)
* Explore extracted articles from [1806: Gazetteer of Scotland: containing a particular and concise description of the counties, parishes, islands, cities with maps](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97414570) --> [Google Colab Notebook](https://colab.research.google.com/drive/1EfqonO3p6XGCxEXyEohUU5uQD7BlIQRr?usp=sharing) 

* Explore extracted articles from [1825: Gazetteer of Scotland: arranged under the various descriptions of counties, parishes, islands -- 1 volume](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97421702) --> [Google Colab Notebook](https://colab.research.google.com/drive/1CVd40bNGe-RAuPmv1M07tEjSWC5-wcgs?usp=sharing)
* Explore extracted articles from [1838: Gazetteer of Scotland with plates and maps -- 2 volumes](https://digital.nls.uk/gazetteers-of-scotland-1803-1901/archive/97491771) --> Currently working on it
