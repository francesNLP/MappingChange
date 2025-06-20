# 📊 Knowledge Graph and ElasticSearch Usage Guide

This file documents how to query and explore the knowledge graph produced by the MappingChange pipeline, deployed locally using [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/). For details on how to generate and upload the KG, refer to [`PIPELINE_EXECUTION.md`](./PIPELINE_EXECUTION.md).

You can also find worked examples on how to query our KGs in our available public Fuseki endpoit [http://query.frances-ai.com/hto_gazetteers](http://query.frances-ai.com/hto_gazetteers)  in the Notebook at [`Knowledge_Exploration_SPARQL `](https://github.com/francesNLP/MappingChange/tree/main/Notebooks/Knowledge_Exploration_SPARQL.ipynb). The notebook also contain the *evaluation* with 


This file documents how to query and explore the knowledge graph produced by the MappingChange pipeline, deployed locally using [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/). For details on how to generate and upload the KG, refer to [`PIPELINE_EXECUTION.md`](./PIPELINE_EXECUTION.md).

You can also find worked examples on how to query our KGs via the public Fuseki endpoint at [http://query.frances-ai.com/hto_gazetteers](http://query.frances-ai.com/hto_gazetteers), showcased in the notebook [`Knowledge_Exploration_SPARQL.ipynb`](https://github.com/francesNLP/MappingChange/tree/main/Notebooks/Knowledge_Exploration_SPARQL.ipynb).

The same notebook includes two sets of SPARQL queries that help **explore and validate** the structure and coverage of the knowledge graphs—one focusing on internal consistency (e.g., redirects, references) and another on external linkage to sources like Wikidata.

This document also provides a guide of how to use ES search indices.

---

## 🔎 SPARQL Queries for Validation and Exploration

**Upload to the dataset in fuseki server**: Upload the `src/knowledge_graph/results/gaz_extra_concepts_links.ttl` (see [instructions](./PIPELINE_EXECUTION.md)) file and also the countries knowledge graph to the previous dataset.

You can also download [gaz_extra_concepts_links.ttl](https://drive.google.com/file/d/1UeT8v9Avwk0dlqPx_ZD5-IxOFpOgAyX7/view?usp=share_link) from that link. 

### Query 1: Places near Edinburgh (within 50 miles)

```sparql
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://jena.apache.org/function/spatial#>
PREFIX units: <http://www.opengis.net/def/uom/OGC/1.0/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>

SELECT ?name ?neigh_wkt WHERE {
   ?edi a crm:SP2_Phenomenal_Place;
        rdfs:label "Edinburgh";
        geo:hasCentroid ?centroid.
   ?centroid a crm:SP6_Declarative_Place;
        geo:asWKT ?edi_wkt.
   ?neigh a crm:SP2_Phenomenal_Place;
        rdfs:label ?name;
        geo:hasCentroid ?neigh_centroid.
   ?neigh_centroid a crm:SP6_Declarative_Place;
        geo:asWKT ?neigh_wkt.
  FILTER(geof:distance(?edi_wkt, ?neigh_wkt, units:mile) < 50)
} LIMIT 20
```

If everything works, it should return name and coordinates of top 20 places which are less than 50 miles from central Edinburgh.

---

### Query 2: Article Descriptions Mentioning Edinburgh

```sparql
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
PREFIX hto: <https://w3id.org/hto#>
PREFIX oa: <http://www.w3.org/ns/oa#>
PREFIX schema: <https://schema.org/>

SELECT ?name ?start_index ?end_index ?text WHERE {
   ?article a hto:LocationRecord;
        hto:name ?name;
        hto:hasOriginalDescription ?desc;
        schema:mentions ?edi.
   ?desc a hto:OriginalDescription;
        hto:text ?text.
   ?annotation a oa:Annotation;
        oa:hasBody ?edi;
        oa:hasTarget ?specific_words.
   ?specific_words oa:hasSource ?desc;
        oa:hasSelector ?selector.
   ?selector a oa:TextPositionSelector;
        oa:start ?start_index;
        oa:end ?end_index.
   ?edi a crm:SP2_Phenomenal_Place;
        rdfs:label "Edinburgh";
} LIMIT 20
```

If everything works, it should return name and description of top 20 articles which mentions Edinburgh, along with the start and end position where Edinburgh appears in the description.

---

### Query 3: Perth Locations and Country Boundaries

```sparql
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
PREFIX hto: <https://w3id.org/hto#>

SELECT ?country_name ?country_boundary_wkt ?perth_wkt WHERE {
   ?perth a crm:SP2_Phenomenal_Place;
        rdfs:label "Perth";
        crm:P89_falls_within ?country;
        geo:hasCentroid ?centroid.
   ?centroid a crm:SP6_Declarative_Place;
        geo:asWKT ?perth_wkt.
   ?country a crm:SP2_Phenomenal_Place;
        rdfs:label ?country_name;
        hto:hasLocationType hto:Country;
        geo:hasCentroid ?country_centroid;
        geo:defaultGeometry ?country_boundary.
   ?country_boundary a crm:SP6_Declarative_Place;
        geo:asWKT ?country_boundary_wkt.
}
```
If everything works, it should return coordinates of all the places called 'Perth', names and boundaries of the countries where they belong. 

---

## 🔍 Elasticsearch Index Usage

If your indices were created using the provided scripts, you can access:

- **Gazetteers article index**
- **Wikidata index**
- **DBpedia index**

These are searchable using [Frances](https://www.frances-ai.com) or standard Elasticsearch queries via Kibana or Python (e.g., `elasticsearch-py`).

Make sure to check the following in your configuration:
- Hostname, certificate path, and API key
- Index names: `"gazetteers"`, `"wikidata_items"`, `"dbpedia_items"` (or your custom names)

---

If you're using Kibana, try a search like:

```json
GET gazetteers/_search
{
  "query": {
    "match": {
      "description": "Edinburgh"
    }
  }
}
```

For setup details, refer to [PIPELINE_EXECUTION.md](./PIPELINE_EXECUTION.md).

