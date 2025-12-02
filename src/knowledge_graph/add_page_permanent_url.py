import json

from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD, DCTERMS, SDO, PROV

hto = Namespace("https://w3id.org/hto#")

def get_volume_mmsid(graph):
    volume_mmsid_list = {}
    from rdflib.plugins.sparql import prepareQuery
    q = prepareQuery('''
        SELECT ?volume_id ?mmsid WHERE {
            ?volume a hto:Volume;
                dct:identifier ?volume_id.
            ?edition_or_series a ?document_type;
                schema:hasPart ?volume;
                hto:mmsid ?mmsid.
            FILTER (?document_type = hto:Edition || ?document_type = hto:Series)
    }
      ''',
                     initNs={"hto": hto, "dct": DCTERMS, "schema": SDO}
                     )

    for r in graph.query(q):
        volume_mmsid_list[str(r.volume_id)] = str(r.mmsid)

    return volume_mmsid_list


def add_page_permanent_url_to_graph(graph, volume_page_urls, volume_mmsid_list):
    page_uri_url = {}
    for volume_id in volume_page_urls:
        if volume_id in volume_mmsid_list:
            mmsid = volume_mmsid_list[volume_id]
            page_urls = volume_page_urls[volume_id]
            for page_num in page_urls:
                page_url = page_urls[page_num]
                page_uri_ref = URIRef("https://w3id.org/hto/Page/" + mmsid + "_" + volume_id + "_" + page_num)
                page_uri_url[page_uri_ref] = page_url
                if (page_uri_ref, RDF.type, hto.Page) not in graph:
                    graph.add((page_uri_ref, RDF.type, hto.Page))
                    graph.add((page_uri_ref, hto.number, Literal(int(page_num), datatype=XSD.integer)))
                permanentURL = URIRef(page_url)
                graph.add((permanentURL, RDF.type, PROV.Location))
                graph.add((page_uri_ref, hto.permanentURL, permanentURL))


if __name__ == "__main__":
    print("---- Start the add page permanent url task ----")
    # Load all the page urls
    print("Loading the page urls file....")
    volume_page_urls_json_filepath = "volume_page_urls.json"
    volume_page_urls = json.loads(open(volume_page_urls_json_filepath, "r").read())
    total__pages = sum([len(volume_page_urls[vol_id]) for vol_id in volume_page_urls])
    print(f"{total__pages} page urls loaded.")

    print("Loading the input graph....")
    # Load graph from file
    graph = Graph()
    graph_filepath = "results/gaz.ttl"
    graph.parse(graph_filepath, format="turtle")
    print("The input graph is loaded!")

    volume_mmsid_list = get_volume_mmsid(graph)

    print("Adding page permanent url to the input graph....")
    add_page_permanent_url_to_graph(graph, volume_page_urls, volume_mmsid_list)

    # Save the Graph in the RDF Turtle format
    result_graph_filepath = graph_filepath
    print(f"Saving the result graph to {result_graph_filepath}....")
    graph.serialize(format="turtle", destination=result_graph_filepath)
    print("Finished saving the result graph!")