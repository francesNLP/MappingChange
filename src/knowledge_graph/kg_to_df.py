import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Namespace

hto = Namespace("https://w3id.org/hto#")

sparql = SPARQLWrapper(
    "http://query.frances-ai.com/hto_gazetteers"
)
sparql.setReturnFormat(JSON)

def create_basic_dataframe(collection_name):
    info_list = []
    # year, edition num, volume num, start page, end page, term type, name, alter_names [], hq - description, description uri, related terms [{uri: , name: },{}], supplement edition num
    sparql.setQuery("""
    PREFIX hto: <https://w3id.org/hto#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT * WHERE {
        ?record_uri a hto:LocationRecord;
            hto:name ?name;
            hto:startsAtPage ?startPage;
            hto:endsAtPage ?endPage;
            hto:hasOriginalDescription ?desc.
        ?desc hto:text ?text;
            hto:hasTextQuality hto:Low.
        ?startPage hto:number ?s_page_num.
        ?endPage hto:number ?e_page_num.
        ?vol a hto:Volume;
            hto:hadMember ?startPage;
            hto:number ?vol_num;
            hto:title ?vol_title.
        ?series a hto:Series;
            hto:hadMember ?vol;
            hto:yearPublished ?year_published;
            hto:genre ?genre;
            hto:printedAt ?printedAt.
        ?printedAt rdfs:label ?print_location.
        OPTIONAL {?series hto:number ?series_num}
        ?collection a hto:WorkCollection;
                hto:hadMember ?series;
                hto:name "%s".
        }
    """ % collection_name)

    try:
        ret = sparql.queryAndConvert()
        for r in ret["results"]["bindings"]:
            record_uri = r["record_uri"]["value"]
            start_page_num = r["s_page_num"]["value"]
            end_page_num = r["e_page_num"]["value"]
            vol_num = r["vol_num"]["value"]
            year_published = r["year_published"]["value"]
            record_name = r["name"]["value"]
            series_num = None
            series_uri = r["series"]["value"]
            description = r['text']["value"]
            if "series_num" in r:
                series_num = r["series_num"]["value"]
            info_list.append({
                "series_uri": series_uri,
                "vol_num": vol_num,
                "vol_title": r["vol_title"]["value"],
                "genre": r["genre"]["value"],
                "print_location": r["print_location"]["value"],
                "year_published": year_published,
                "series_num": series_num,
                "record_uri": record_uri,
                "description": description,
                "description_uri": r["desc"]["value"],
                "record_name": record_name,
                "start_page_num": start_page_num,
                "end_page_num": end_page_num
            })
    except Exception as e:
        print(e)
    return pd.DataFrame(info_list)


def create_references_dicts():
    sparql.setQuery("""
    PREFIX hto: <https://w3id.org/hto#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT * WHERE {
        ?record_uri a hto:LocationRecord;
            hto:refersTo ?reference.
        ?reference a hto:LocationRecord;
            hto:name ?name.
    }
    """
                    )
    ret = sparql.queryAndConvert()
    references = {}
    for r in ret["results"]["bindings"]:
        record_uri = r["record_uri"]["value"]
        reference_uri = r["reference"]["value"]
        reference_name = r["name"]["value"]
        reference = {
            "uri": reference_uri,
            "name": reference_name
        }
        if record_uri in references:
            references[record_uri].append(reference)
        else:
            references[record_uri] = [reference]

    return references


def create_alter_names_dicts():
    sparql.setQuery("""
    PREFIX hto: <https://w3id.org/hto#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT * WHERE {
        ?record_uri a hto:LocationRecord;
            rdfs:label ?alter_name.
    }
    """
                    )
    ret = sparql.queryAndConvert()
    alter_names = {}
    for r in ret["results"]["bindings"]:
        record_uri = r["record_uri"]["value"]
        alter_name = r["alter_name"]["value"]
        if record_uri in alter_names:
            alter_names[record_uri].append(alter_name)
        else:
            alter_names[record_uri] = [alter_name]

    return alter_names


if __name__ == "__main__":
    print("----Getting gazetteers entry basic dataframe -----")
    collection_name = "Gazetteers of Scotland Collection"
    gazetteers_df = create_basic_dataframe(collection_name)
    print("----Getting reference terms -----")
    reference_terms = create_references_dicts()
    print("----Getting alternative names -----")
    alter_names = create_alter_names_dicts()

    print("----Adding references, alternative names to the dataframe ------")
    gazetteers_df["alter_names"] = gazetteers_df["record_uri"].apply(
        lambda record_uri: alter_names[record_uri] if record_uri in alter_names else [])
    gazetteers_df["references"] = gazetteers_df["record_uri"].apply(
        lambda record_uri: reference_terms[record_uri] if record_uri in reference_terms else [])

    result_filename = "results/gazetteers_entry_kg_df"
    print(f"----Saving the final dataframe to {result_filename}----")
    gazetteers_df.to_json(result_filename, orient="index")

