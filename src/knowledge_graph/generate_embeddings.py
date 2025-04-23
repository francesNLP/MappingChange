import pandas as pd
from sentence_transformers import SentenceTransformer

import re

NON_AZ_REGEXP = re.compile("[^a-z]")


def normalize(word):
    """
    Normalize a word by converting it to lower-case and removing all
    characters that are not 'a',...,'z'.

    :param word: Word to normalize
    :type word: str or unicode
    :return: normalized word
    :rtype word: str or unicode
    """
    return re.sub(NON_AZ_REGEXP, '', word.lower())


def normalize_text(text):
    all_words = text.split()
    all_normalised_words = []
    for word in all_words:
        all_normalised_words.append(normalize(word))
    return ' '.join(all_normalised_words)

if __name__ == "__main__":
    kg_df_filename = "gazetteers_entry_kg_df"
    kg_df = pd.read_json(kg_df_filename, orient="index")

    descriptions = kg_df['description'].tolist()
    model = SentenceTransformer('all-mpnet-base-v2')
    model._first_module().max_seq_length = 509
    descriptions = [normalize_text(description) for description in descriptions]
    text_embeddings_new = model.encode(descriptions, show_progress_bar = True)
    kg_df["embedding"] = text_embeddings_new.tolist()
    # store this dataframe
    result_df_filename = "gaz_kg_df_with_embeddings"
    print(f"----Saving the final dataframe to {result_df_filename}----")
    kg_df.to_json(result_df_filename, orient="index")