import pandas as pd
import json
import numpy as np
import re
from difflib import SequenceMatcher
import re

import regex
def extract_names(head: str) -> tuple[str, list[str]]:
    """
    This function extracts primary name (first name appears) and alternative names from a head (first few words with article names in dictionary like text).
    :param head: first few words with article names in dictionary like text.
    :return: primary name and a list of alternative names.
    """
    pre_or, sep, post_or = head.partition(" OR ")
    #print(f"pre_or: {pre_or}, sep: {sep}, post_or: {post_or}")
    alternative_names = []
    primary_name = head
    words_pattern_str = "(([\p{L}\p{N}\-\'\.]+\s*)+)"
    if sep:
        # handle head with "OR"
        # if "OR" is embedded within parentheses
        paren_match = regex.search(r'' + words_pattern_str + '\(([^)]+)\sOR\s([^)]+)\)', head)
        if paren_match:
            #print(f"group 1: {paren_match.group(1)}, group 3: {paren_match.group(3)}, group4: {paren_match.group(4)}")
            pre_name = paren_match.group(1).strip()
            first_post_name = paren_match.group(3).strip()
            # remove the last comma if exists
            first_post_name = first_post_name.split(',', 1)[0]
            second_post_name = paren_match.group(4).strip()
            primary_name = f"{pre_name} {first_post_name}"
            alter_name = f"{pre_name} {second_post_name}"
            alternative_names.append(alter_name)
            #print(head)
            return primary_name, alternative_names

        names = pre_or.split(",")
        names = [name.strip() for name in names if len(name) > 0]
        primary_name = names[0]
        alternative_names = names[1:]
        last_alter_match = regex.search(r'\s+(PROPERLY|CALLED)\s+', post_or)
        if last_alter_match:
            last_name_start_index = last_alter_match.end(1)
            last_name = post_or[last_name_start_index:].strip()
            alternative_names.append(last_name)
        else:
            alternative_names.append(post_or)

        return primary_name, alternative_names

    # other rules
    indicator_match = regex.search(r'\s+(OTHERWISE\s+CALLED|CALLED|NAMED|PROPERLY|OTHERWISE)\s+' + words_pattern_str, head)
    if indicator_match:
        #print(head)
        pre_indicator_end_index = indicator_match.start(0)
        primary_name_end_index = head.rfind(",", 0, pre_indicator_end_index)
        if primary_name_end_index < 0:
            primary_name_end_index = head.rfind("(", 0, pre_indicator_end_index)
            if primary_name_end_index < 0:
                primary_name_end_index = pre_indicator_end_index
        primary_name = head[:primary_name_end_index].strip()
        last_name = indicator_match.group(2).strip()
        alternative_names.append(last_name)
        return primary_name, alternative_names
    return primary_name, alternative_names


def extra_see_references(text:str) -> list[str]:
    """
    This function extracts see references after the word "See" at the end of the text. If there are same reference name occurs multiple times, this function will only return one.
    :param text: text to extract references from.
    :return: a list of reference names
    """
    references = []
    indicator_match = regex.search(r"(See|Vide)\s+((\(?\p{Lu}[\p{Lu\p{L}\-\'\.\)]+\s*)+(and\s+(\(?\p{Lu}[\p{Lu\p{L}\-\'\.\)]+\s*)+)?)$", text)

    if indicator_match:
        post_indicator_text = indicator_match.group(2).strip()
        if post_indicator_text[-1] == '.':
            post_indicator_text = post_indicator_text[:-1]
        pre_and, sep, post_and = post_indicator_text.partition(" and ")
        #print(post_indicator_text)
        if sep:
            references.append(pre_and.strip())
            references.append(post_and.strip())
        else:
            references.append(post_indicator_text.strip())

    return references


def extract_reference_terms(text):
    """Extracts reference names from patterns like 'See Lesmahago.' or 'See Lesmahago and Aby.'"""
    # Regex to match patterns like:
    # - See Name.
    # - See Name and Name.
    # - See Name, Name, and Name.
    # Also allow optional semicolon before or after
    pattern = re.compile(r"See ([A-Z][a-zA-Z'\- ]+(?: and [A-Z][a-zA-Z'\- ]+)*(?:,? [A-Z][a-zA-Z'\- ]+)*?)\s*(?:[.;])")

    matches = pattern.findall(text)
    referenced = []

    for match in matches:
        # Normalize and split by ' and ' or ','
        subparts = re.split(r',| and ', match)
        for ref in subparts:
            ref_clean = ref.strip()
            if ref_clean and ref_clean not in referenced:
                referenced.append(ref_clean)
    return referenced if referenced else None


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def is_corrupted_by_next_article(text):
    return ';' in text[100:] and any(
        keyword in text.lower() for keyword in [" ; ", "a river", "a parish", "a town", "or ", "wall", "loch"]
    )

def deduplicate_articles_1(df, fuzzy_threshold=0.97, prefix_window=500):
    df = df.copy()
    rows_to_remove = []

    grouped = df.groupby(['edition', 'volumeId', 'starts_at_page', 'name'])

    for _, group in grouped:
        if len(group) <= 1:
            continue

        indexes = group.index.tolist()

        # Step 1: Remove direct substring or fuzzy matches
        for i in indexes:
            for j in indexes:
                if i == j or i in rows_to_remove or j in rows_to_remove:
                    continue

                text_i = df.at[i, 'text'].strip()
                text_j = df.at[j, 'text'].strip()

                if len(text_i) < len(text_j):
                    shorter, longer = text_i, text_j
                    idx_shorter = i
                else:
                    shorter, longer = text_j, text_i
                    idx_shorter = j

                is_substring = shorter in longer
                is_fuzzy = similar(shorter, longer) >= fuzzy_threshold and len(shorter) / len(longer) >= 0.9
                is_early_window_match = shorter in longer[:prefix_window]

                if is_substring or is_fuzzy or is_early_window_match:
                    rows_to_remove.append(idx_shorter)

                    edition = df.at[idx_shorter, 'edition']
                    volumeId = df.at[idx_shorter, 'volumeId']
                    page = df.at[idx_shorter, 'starts_at_page']

                    mask_vol = (df['edition'] == edition) & (df['volumeId'] == volumeId)
                    df.loc[mask_vol, 'total_articles'] -= 1

                    mask_page = mask_vol & (df['starts_at_page'] == page)
                    df.loc[mask_page, 'total_articles_page'] -= 1

        # Step 2: Fallback cleanup (only if remaining are very similar)
        remaining = group.loc[~group.index.isin(rows_to_remove)]

        if len(remaining) > 1:
            texts = remaining['text'].tolist()
            all_similar = True
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    if similar(texts[i], texts[j]) < 0.85:
                        all_similar = False
                        break
                if not all_similar:
                    break

            if all_similar:
                remaining = remaining.copy()
                remaining['text_length'] = remaining['text'].apply(len)
                remaining['has_name_in_text'] = remaining.apply(
                    lambda row: str(row['name']).lower().split()[0] in row['text'][:80].lower(), axis=1
                )
                remaining['is_corrupted'] = remaining['text'].apply(is_corrupted_by_next_article)
                remaining['score'] = (
                    remaining['has_name_in_text'].astype(int) * 2 -
                    remaining['is_corrupted'].astype(int) +
                    (remaining['text_length'] / remaining['text_length'].max())
                )

                idx_to_keep = remaining.sort_values('score', ascending=False).index[0]

                for idx in remaining.index:
                    if idx != idx_to_keep:
                        #print("\n📌 Removing entry in fallback (SOAY or BARR):")
                        #print(f"- Name: {df.at[idx, 'name']}")
                        #print(f"- Removed index: {idx}, Kept index: {idx_to_keep}")
                        #print(f"- Removed text preview: {df.at[idx, 'text'][:120]}...")
                        #print(f"- Kept text preview  : {df.at[idx_to_keep, 'text'][:120]}...")

                        rows_to_remove.append(idx)

                        edition = df.at[idx, 'edition']
                        volumeId = df.at[idx, 'volumeId']
                        page = df.at[idx, 'starts_at_page']

                        mask_vol = (df['edition'] == edition) & (df['volumeId'] == volumeId)
                        df.loc[mask_vol, 'total_articles'] -= 1

                        mask_page = mask_vol & (df['starts_at_page'] == page)
                        df.loc[mask_page, 'total_articles_page'] -= 1

    df_cleaned = df.drop(index=rows_to_remove).reset_index(drop=True)
    return df_cleaned



def remove_nested_and_duplicate_texts_across_pages(df, fuzzy_threshold=0.99):
    df = df.copy()
    rows_to_remove = []

    grouped = df.groupby(['edition', 'volumeId', 'name'])

    for _, group in grouped:
        if len(group) <= 1:
            continue

        indexes = group.index.tolist()

        for i in range(len(indexes)):
            for j in range(len(indexes)):
                if i == j:
                    continue

                idx_i, idx_j = indexes[i], indexes[j]
                if idx_i in rows_to_remove or idx_j in rows_to_remove:
                    continue

                text_i = df.at[idx_i, 'text'].strip()
                text_j = df.at[idx_j, 'text'].strip()

                # Sort by length
                if len(text_i) < len(text_j):
                    shorter, longer = text_i, text_j
                    idx_shorter = idx_i
                else:
                    shorter, longer = text_j, text_i
                    idx_shorter = idx_j

                is_exact_duplicate = text_i == text_j
                is_strict_substring = shorter in longer
                is_fuzzy_duplicate = similar(text_i, text_j) >= fuzzy_threshold

                if is_exact_duplicate or is_strict_substring or is_fuzzy_duplicate:
                    rows_to_remove.append(idx_shorter)

                    # Adjust counts
                    edition = df.at[idx_shorter, 'edition']
                    volumeId = df.at[idx_shorter, 'volumeId']
                    page = df.at[idx_shorter, 'starts_at_page']

                    mask_vol = (df['edition'] == edition) & (df['volumeId'] == volumeId)
                    df.loc[mask_vol, 'total_articles'] -= 1

                    mask_page = mask_vol & (df['starts_at_page'] == page)
                    df.loc[mask_page, 'total_articles_page'] -= 1

    return df.drop(index=rows_to_remove).reset_index(drop=True)


def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())


def deduplicate_articles_by_token_prefix(df, token_limit=100, jaccard_threshold=0.8, fuzzy_threshold=0.92):
    df = df.copy()
    rows_to_remove = []

    grouped = df.groupby(['edition', 'volumeId', 'name'])

    for _, group in grouped:
        if len(group) <= 1:
            continue

        seen = []
        for idx1, row1 in group.iterrows():
            if idx1 in rows_to_remove:
                continue

            tokens1 = tokenize(row1['text'])[:token_limit]
            prefix1 = " ".join(tokens1)

            for idx2 in seen:
                tokens2 = tokenize(df.at[idx2, 'text'])[:token_limit]
                prefix2 = " ".join(tokens2)

                # Fuzzy and token-based comparison
                jaccard_sim = len(set(tokens1) & set(tokens2)) / len(set(tokens1) | set(tokens2))
                fuzzy_sim = similar(prefix1, prefix2)

                if jaccard_sim >= jaccard_threshold or fuzzy_sim >= fuzzy_threshold:
                    len1 = len(row1['text'])
                    len2 = len(df.at[idx2, 'text'])

                    if len1 >= len2:
                        idx_remove = idx2
                        idx_keep = idx1
                    else:
                        idx_remove = idx1
                        idx_keep = idx2

                    print(f"\n📌 Removing near-duplicate:")
                    print(f"- Removed:  {df.at[idx_remove, 'name']} (pages {df.at[idx_remove, 'starts_at_page']}–{df.at[idx_remove, 'ends_at_page']})")
                    print(f"- Kept:     {df.at[idx_keep, 'name']} (pages {df.at[idx_keep, 'starts_at_page']}–{df.at[idx_keep, 'ends_at_page']})")

                    rows_to_remove.append(idx_remove)
                    break

            seen.append(idx1)

    # Adjust article counts
    for idx in rows_to_remove:
        edition = df.at[idx, 'edition']
        volumeId = df.at[idx, 'volumeId']
        page = df.at[idx, 'starts_at_page']

        mask_vol = (df['edition'] == edition) & (df['volumeId'] == volumeId)
        df.loc[mask_vol, 'total_articles'] -= 1

        mask_page = mask_vol & (df['starts_at_page'] == page)
        df.loc[mask_page, 'total_articles_page'] -= 1

    print(f"\n✅ Total duplicates removed: {len(rows_to_remove)}")
    return df.drop(index=rows_to_remove).reset_index(drop=True)



# Load metadata dataframe (page-level info, but we only use first row for edition-level metadata)
gdf = pd.read_json("gazatteers_dataframe", orient="index")
gdf_1838_vol1 = gdf[gdf['edition'] == '1838, Volume 1'].copy()
#gdf_1838_vol1 = g_df[g_df['edition'] == '1838, Volume 2'].copy()

if gdf_1838_vol1.empty:
    raise ValueError("No entries found for edition '1838_vol1' in gazatteers_dataframe.")

# Take metadata from the first row (except 'text')
meta_row = gdf_1838_vol1.iloc[0].drop(["text", "pageNum"], errors="ignore").to_dict()
print(meta_row)

# Load combined article entries (article-level info)
json_path = "1838_vol1/gazetteer_articles_merged_1838_vol1.json"
with open(json_path, "r", encoding="utf-8") as f:
    article_data = json.load(f)

# Turn articles into a DataFrame
df_articles = pd.DataFrame(article_data["articles"])
total_articles = article_data["total_articles"]
print("Len of df_articles %s" % (len(df_articles)))
print("total_articles %s" % total_articles)


# Add metadata columns to each article row (ensure proper length even for lists)
for key, value in meta_row.items():
    if isinstance(value, (list, dict, np.ndarray)):
        df_articles[key] = pd.Series([value] * len(df_articles))
    else:
        df_articles[key] = value

# Optional: Reorder columns
desired_order = ["name", "page_start", "page_finish", "total_articles_page", "text"]
# Add metadata fields after if you want
metadata_columns = [col for col in df_articles.columns if col not in desired_order]
df_articles = df_articles[metadata_columns + desired_order]

# Rename page columns
df_articles = df_articles.rename(columns={
    "page_start": "starts_at_page",
    "page_finish": "ends_at_page"
})


# Create a mapping from pageNum to altoXML file path
page_to_alto = gdf_1838_vol1.set_index("pageNum")["altoXML"].to_dict()

# Map starts_at_page to altoXML (this will be the file where the article starts)
df_articles["altoXML"] = df_articles["starts_at_page"].map(page_to_alto)

df_articles["total_articles"]=total_articles


# Final Clean:
# Step 1: Deduplicate using earlier smart logic
g_df_deduped = deduplicate_articles_1(df_articles)


# Step 2: Apply cross-page containment cleaner
g_df_clean = remove_nested_and_duplicate_texts_across_pages(g_df_deduped)

# Step 3:

g_df_cleaned = deduplicate_articles_by_token_prefix(g_df_clean)


# Step 4: Apply to df_articles (or later on g_df_cleaned if you prefer)

g_df_cleaned['reference_terms'] = g_df_cleaned['text'].apply(extra_see_references)

g_df_cleaned['alter_names'] = g_df_cleaned['name'].apply(lambda x: extract_names(x)[1])



num_with_references = g_df_cleaned['reference_terms'].notnull().sum()
non_empty_references = g_df_cleaned['reference_terms'].apply(lambda x: isinstance(x, list) and len(x) > 0)
num_with_references = non_empty_references.sum()
print(f"✅ Number of articles with references: {num_with_references}")


non_empty_alt_names = g_df_cleaned['alter_names'].apply(lambda x: isinstance(x, list) and len(x) > 0)
num_with_alter_names = non_empty_alt_names.sum()
print(f"✅ Number of articles with alter_names: {num_with_alter_names}")

total_articles = len(g_df_cleaned)
percentage = (num_with_references / total_articles) * 100
print(f"✅ {num_with_references} out of {total_articles} articles ({percentage:.2f}%) have references.")


non_empty_refs = g_df_cleaned['reference_terms'].apply(lambda x: isinstance(x, list) and len(x) > 0)
example_row = g_df_cleaned[non_empty_refs].iloc[0]

# Then print it nicely
print("📌 Example Article with References:")
print(f"Name: {example_row['name']}")
print(f"Starts at Page: {example_row['starts_at_page']}")
print(f"Reference Terms: {example_row['reference_terms']}")
print(f"Text Snippet: {example_row['text'][:300]}...")


non_empty_alts = g_df_cleaned['alter_names'].apply(lambda x: isinstance(x, list) and len(x) > 0)
example_alt_row = g_df_cleaned[non_empty_alts].iloc[0]

# Print it nicely
print("📌 Example Article with Alternative Names:")
print(f"Name: {example_alt_row['name']}")
print(f"Starts at Page: {example_alt_row['starts_at_page']}")
print(f"Alternative Names: {example_alt_row['alter_names']}")
print(f"Text Snippet: {example_alt_row['text'][:300]}...")


# Show summary
print(f"✅ DataFrame created with {len(df_articles)} rows.")
print(g_df_cleaned.head())

# Save final dataframe to JSON
g_df_cleaned.to_json(r'1838_vol1/gaz_dataframe_1838_vol1', orient="index")
print("✅ Created DataFrame with metadata attached. Saved as JSON.")






