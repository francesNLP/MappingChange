from SPARQLWrapper import SPARQLWrapper, JSON
import pandas as pd

sparql = SPARQLWrapper(
    "http://query.frances-ai.com/test_gaz"
)
sparql.setReturnFormat(JSON)

def get_articles():
    articles = []
    sparql.setQuery("""
    PREFIX schema: <https://schema.org/>
    PREFIX hto: <https://w3id.org/hto#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?record_uri ?name ?desc ?text ?year_published WHERE {
        ?record_uri a hto:LocationRecord;
            rdfs:label ?name;
            hto:startsAtPage ?startPage;
            hto:hasOriginalDescription ?desc.
        ?desc hto:text ?text;
            hto:hasTextQuality hto:Low.
  		# Calculate word count for description
    	BIND (STRLEN(REPLACE(?text, "\\\\S", " ")) AS ?length)
    	FILTER (?length > 0)
        ?vol a hto:Volume;
            schema:hasPart ?startPage.
        ?series a hto:Series;
            schema:hasPart ?vol;
            hto:yearPublished ?year_published.
        ?collection a hto:WorkCollection;
            rdfs:label 'Gazetteers of Scotland Collection';
            schema:hasPart ?series.
        }
    """ )

    try:
        ret = sparql.queryAndConvert()
        for r in ret["results"]["bindings"]:
            articles.append({
                "record_uri": r["record_uri"]["value"],
                "name": r["name"]["value"],
                "description": r["text"]["value"],
                "description_uri": r["desc"]["value"],
                "year_published": r["year_published"]["value"]
            })
    except Exception as e:
        print(e)

    return articles


if __name__ == "__main__":
    print("----Getting gazetteers entry simple dataframe -----")
    articles = get_articles()
    articles_df = pd.DataFrame(articles)
    print("----Saving gazetteers entry simple dataframe -----")
    articles_df.to_json("sources/gaz_articles_simple.json", orient="records", lines=True)
    print("Done")