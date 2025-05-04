from tqdm import tqdm
import pandas as pd
from utils import normalize_name
from geoparser import geo_tagging


if __name__ == "__main__":
    # load gaz articles
    print("Loading gaz articles....")
    articles_df = pd.read_json('sources/gaz_articles_simple.json', orient='records', lines=True)
    print(f"{len(articles_df)} articles loaded")

    # geoparse all articles
    articles = articles_df.to_dict(orient='records')
    print("Geotagging articles....")
    for index, article in enumerate(tqdm(articles)):
        # add name back to the text
        article_name = normalize_name(article["name"])
        text_with_article_name = article_name + ", " + article["description"]
        # geotagging
        location_tokens = geo_tagging(text_with_article_name)
        # check if this article is identified as a location
        if len(location_tokens) > 0 and location_tokens[0]['name'] == article_name:
            location_tokens.pop(0)

        # forward all the indices by the length of <article_name, >
        forward_len = len(article_name + ", ")
        for location in location_tokens:
            location["start"] -= forward_len
            location["end"] -= forward_len

        # remove the all locations with negative index, as part of article name could be identified as a location
        negative_locations_count = 0
        for location_token in location_tokens:
            if location_tokens[0]['start'] < 0:
                negative_locations_count += 1
        for _ in range(negative_locations_count):
            location_tokens.pop(0)

        # put the article name back to the location tokens, as it is certainly a location
        location_tokens.insert(0, {
            "name": article_name,
            'start': 0,
            'end': 0,
        })

        article["locations"] = location_tokens

    # store articles
    print("Saving geotagged articles....")
    articles_df = pd.DataFrame(articles)
    result_path = "results/geotagged_articles_df.json"
    articles_df.to_json(result_path, orient='records', lines=True)
    print(f"result saved to {result_path}")


