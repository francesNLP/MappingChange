import pandas as pd
import json
import numpy as np
import re
from difflib import SequenceMatcher
import re
import regex
import os
import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key="xxx")

from difflib import SequenceMatcher

def normalize_name_1(name):
    """Normalize by removing spaces and uppercasing."""
    return ''.join(name.upper().split())

def fuzzy_match_1(a, b, threshold=0.99):
    """Check if two normalized names are similar enough."""
    return SequenceMatcher(None, a, b).ratio() >= threshold

def fix_ocr_glitches_in_names(df, threshold=0.99):
    """
    Fix OCR-glitch names directly in 'name' column by checking similarity
    between normalized versions of adjacent rows.

    Parameters:
        df (pd.DataFrame): Must contain a 'name' column.
        threshold (float): Fuzzy similarity threshold.

    Returns:
        pd.DataFrame: A new DataFrame with corrected 'name' values.
    """
    df_fixed = df.copy()

    for i in range(1, len(df_fixed) - 1):
        prev_name = df_fixed.loc[i - 1, "name"]
        curr_name = df_fixed.loc[i, "name"]
        next_name = df_fixed.loc[i + 1, "name"]

        prev_norm = normalize_name_1(prev_name)
        curr_norm = normalize_name_1(curr_name)
        next_norm = normalize_name_1(next_name)

        if fuzzy_match_1(prev_norm, next_norm, threshold=threshold) and not fuzzy_match_1(prev_norm, curr_norm, threshold=threshold):
            print(f"\n🔁 Fixing row {i}: '{curr_name}' → '{prev_name}'")
            print("📌 Context:")
            print(f"  Row {i - 1}: {prev_name} ({prev_norm})")
            print(f"👉 Row {i}: {curr_name} ({curr_norm} -- New name: {prev_name})  ← FIXED")
            print(f"  Row {i + 1}: {next_name} ({next_norm})")
            df_fixed.loc[i, "name"] = prev_name  # apply fix directly
            if (next_norm != next_name) & (next_norm == prev_norm):
                print(f"👉 Row {i+1}: {next_name} ({next_norm} -- New name: {prev_name})  ← FIXED")
                df_fixed.loc[i+1, "name"] = prev_name

    print("\n✅ Done checking for OCR-glitchy names.")
    return df_fixed

def simple_norm(name):
    name = name.upper()
    name = name.replace("13", "B").replace("1", "I").replace("0", "O")
    name = re.sub(r"[^A-Z\s]", "", name)  # Remove everything except letters and spaces
    name = re.sub(r"\s+", " ", name)  # Normalize multiple spaces to single
    return name.strip()

def print_repeated_articles(df):
    grouped = df.groupby(['edition', 'volumeId', 'name'])
    repeated = grouped.filter(lambda g: len(g) > 1)

    if repeated.empty:
        print("✅ No repeated place names found.")
        return

    print(f"\n🔁 Repeated articles found: {repeated['name'].nunique()} unique repeated names\n")

    for (edition, volumeId, name), group in repeated.groupby(['edition', 'volumeId', 'name']):
        print(f"\n📍 Name: {name} | Edition: {edition} | Volume: {volumeId} | Entries: {len(group)}\n")

        for idx, row in group.iterrows():
            print(f"🔹 Index: {idx} | Pages: {row['starts_at_page']}–{row['ends_at_page']}")
            print(f"Text (first 300 chars): {row['text'][:300]}...\n{'-'*60}")


def normalize_name_2(name):
    return re.sub(r"[^A-Z]", "", name.upper())

def fuzzy_match_2(a, b, threshold=0.96):
    return SequenceMatcher(None, a, b).ratio() >= threshold

def collapse_fuzzy_name_variants(df, threshold=0.90):
    df = df.copy()
    names = df['normalized_name'].tolist()
    fixed_names = names.copy()

    for i in range(1, len(names) - 1):
        curr, prev, next_ = normalize_name_2(names[i]), normalize_name_2(names[i - 1]), normalize_name_2(names[i + 1])
        if fuzzy_match_2(prev, next_, threshold) and not fuzzy_match_2(prev, curr, threshold):
            print(f"🔁 Fixing row {i}: '{names[i]}' → '{names[i - 1]}'")
            fixed_names[i] = fixed_names[i - 1]

    df['normalized_name'] = fixed_names
    return df


def ask_gpt_same_or_different(texts):
    prompt = (
        "You're analyzing historical Gazetteer entries that have the same name within a volume. "
        "Determine if they refer to:\n\n"
        "1. The **same place**, described across multiple entries (a continuation), or\n"
        "2. **Different places** that happen to share the same name.\n\n"
        "Here are the entries:\n\n"
    )
    for i, t in enumerate(texts, 1):
        prompt += f"Entry {i}:\n{t.strip()[:1000]}\n\n"

    prompt += (
        "Please respond with:\n"
        "- 'Same place (continuation)' OR\n"
        "- 'Different places'\n\n"
        "Then give a short justification."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a historical Gazetteer analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()


def merge_continuation_group(df, group):
    df = df.copy()
    group = group.sort_values("starts_at_page").reset_index()
    main_idx = group.loc[0, "index"]
    continuation_indices = group.loc[1:, "index"]

    print(f"\n🔧 Merging {len(continuation_indices)} continuation entries into:")
    print(f"🟢 Main Index: {main_idx} | Pages: {df.at[main_idx, 'starts_at_page']}–{df.at[main_idx, 'ends_at_page']}")

    combined_text = " ".join(df.loc[continuation_indices.tolist() + [main_idx], "text"].dropna())
    df.loc[main_idx, "text"] = combined_text
    new_end_page = df.loc[continuation_indices.tolist() + [main_idx], "ends_at_page"].max()
    df.loc[main_idx, "ends_at_page"] = new_end_page
    print(f"📝 New end page: {new_end_page}")

    # Drop continuation rows
    df.drop(index=continuation_indices, inplace=True)

    # Adjust total_articles
    if "total_articles" in df.columns:
        df.loc[:, "total_articles"] -= len(continuation_indices)

    # Adjust total_articles_page
    if "total_articles_page" in df.columns:
        start_page = df.at[main_idx, "starts_at_page"]
        end_page = df.at[main_idx, "ends_at_page"]
        for page in range(start_page, end_page + 1):
            df.loc[df["starts_at_page"] == page, "total_articles_page"] = 1

    print(f"🗑️ Dropped rows: {continuation_indices.tolist()}")
    return df


def normalize_name(name):
    name = name.upper()
    name = name.replace(" ", "")  # Remove spaces
    name = re.sub(r"[^A-Z]", "", name)  # Remove digits/symbols
    name = name.replace("13", "B").replace("1", "I").replace("0", "O")
    return name.strip()


def fix_repeated_articles_with_gpt4_proximity(df, max_index_gap=30, max_batch_size=5):

    def normalize_name_2(name):
        return re.sub(r"[^A-Z]", "", name.upper())

    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    df = df.copy()
    df["normalized_name"] = df["name"].apply(normalize_name_2)

    grouped = df.groupby(['edition', 'volumeId', 'normalized_name'])
    repeated = grouped.filter(lambda g: len(g) > 1)

    if repeated.empty:
        print("✅ No repeated names.")
        return df

    print(f"🔁 Found {repeated['normalized_name'].nunique()} repeated names.\n")

    for (edition, volumeId, normalized_name), group in repeated.groupby(['edition', 'volumeId', 'normalized_name']):
        indices = group.index.tolist()
        index_diffs = np.diff(indices)

        # Group by proximity (indices within max_index_gap)
        chunks = []
        chunk = [indices[0]]
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] <= max_index_gap:
                chunk.append(indices[i])
            else:
                if len(chunk) > 1:
                    chunks.append(chunk)
                chunk = [indices[i]]
        if len(chunk) > 1:
            chunks.append(chunk)

        for chunk_indices in chunks:
            sub_group = df.loc[chunk_indices]
            print(f"\n📍 Name: {normalized_name} | Edition: {edition} | Volume: {volumeId} | Entries: {len(sub_group)}")

            for idx, row in sub_group.iterrows():
                print(f"🔹 Index: {idx} | Pages: {row['starts_at_page']}–{row['ends_at_page']}")
                print(f"Text Snippet: {row['text'][:300]}...\n{'-'*60}")

            texts = sub_group["text"].tolist()
            batches = [texts[i:i+max_batch_size] for i in range(0, len(texts), max_batch_size)]

            merged = False
            for batch_num, batch in enumerate(batches, 1):
                print(f"🧠 Asking GPT-4 to classify batch {batch_num}...\n")
                verdict = ask_gpt_same_or_different(batch)
                print(f"🤖 GPT-4 says:\n{verdict}\n{'='*80}")

                verdict_line = verdict.strip().splitlines()[0].strip().lower()
                if "same" in verdict_line and not merged:
                    print("🛠️ Merging entries as continuation...")
                    df = merge_continuation_group(df, sub_group)
                    merged = True
                    break
                else:
                    print("✅ Keeping as separate entries.")

    df = df.reset_index(drop=True)
    print("\n✅ Done processing repeated articles with GPT-4 (with proximity constraint).")
    return df


#def fix_repeated_articles_with_gpt4_proximity(df, max_index_gap=30):
#    from difflib import SequenceMatcher
#    import numpy as np
#
#    def normalize_name_2(name):
#        return re.sub(r"[^A-Z]", "", name.upper())
#
#    def similar(a, b):
#        return SequenceMatcher(None, a, b).ratio()
#
#    df = df.copy()
#    df["normalized_name"] = df["name"].apply(normalize_name_2)
#
#    grouped = df.groupby(['edition', 'volumeId', 'normalized_name'])
#    repeated = grouped.filter(lambda g: len(g) > 1)
#
#    if repeated.empty:
#        print("✅ No repeated names.")
#        return df
#
#    print(f"🔁 Found {repeated['normalized_name'].nunique()} repeated names.\n")
#
#    for (edition, volumeId, normalized_name), group in repeated.groupby(['edition', 'volumeId', 'normalized_name']):
#        indices = group.index.tolist()
#        index_diffs = np.diff(indices)
#
#        # Group by proximity (indices within max_index_gap)
#        chunks = []
#        chunk = [indices[0]]
#        for i in range(1, len(indices)):
#            if indices[i] - indices[i-1] <= max_index_gap:
#                chunk.append(indices[i])
#            else:
#                if len(chunk) > 1:
#                    chunks.append(chunk)
#                chunk = [indices[i]]
#        if len(chunk) > 1:
#            chunks.append(chunk)
#
#        for chunk_indices in chunks:
#            sub_group = df.loc[chunk_indices]
#            print(f"\n📍 Name: {normalized_name} | Edition: {edition} | Volume: {volumeId} | Entries: {len(sub_group)}")
#
#            for idx, row in sub_group.iterrows():
#                print(f"🔹 Index: {idx} | Pages: {row['starts_at_page']}–{row['ends_at_page']}")
#                print(f"Text Snippet: {row['text'][:300]}...\n{'-'*60}")
#
#            texts = sub_group["text"].tolist()
#            verdict = ask_gpt_same_or_different(texts)
#            print(f"🤖 GPT-4 says:\n{verdict}\n{'='*80}")
#
#            if "same" in verdict.lower():
#                print("🛠️ Merging entries as continuation...")
#                df = merge_continuation_group(df, sub_group)
#
#    df = df.reset_index(drop=True)
#    print("\n✅ Done processing repeated articles with GPT-4 (with proximity constraint).")
#    return df


def fix_repeated_articles_with_gpt4(df):
    df = df.copy()
    df["normalized_name"] = df["name"].apply(normalize_name_2)
    #df = collapse_fuzzy_name_variants(df)  # 💡 Clean OCR name variants first
    grouped = df.groupby(['edition', 'volumeId', 'normalized_name'])
    repeated = grouped.filter(lambda g: len(g) > 1)

    if repeated.empty:
        print("✅ No repeated names.")
        return df

    print(f"🔁 Found {repeated['normalized_name'].nunique()} repeated names.\n")

    for (edition, volumeId, normalized_name), group in repeated.groupby(['edition', 'volumeId', 'normalized_name']):
        print(f"\n📍 Name: {normalized_name} | Edition: {edition} | Volume: {volumeId} | Entries: {len(group)}\n")

        for idx, row in group.iterrows():
            print(f"🔹 Index: {idx} | Pages: {row['starts_at_page']}–{row['ends_at_page']}")
            print(f"Text Snippet: {row['text'][:300]}...\n{'-'*60}")

        texts = group["text"].tolist()
        max_batch_size = 5
        batches = [texts[i:i+max_batch_size] for i in range(0, len(texts), max_batch_size)]
        merged = False

        for batch_num, batch in enumerate(batches, 1):
            print(f"🧠 Asking GPT-4 to classify batch {batch_num}...\n")
            verdict = ask_gpt_same_or_different(batch)
            print(f"🤖 GPT-4 says:\n{verdict}\n{'='*80}")

            verdict_line = verdict.strip().splitlines()[0].strip().lower()
            if "same" in verdict_line and not merged:
                print("🛠️ Merging entries as continuation...")
                df = merge_continuation_group(df, group)
                merged = True
                break
            else:
                print("✅ Keeping as separate entries.")

    df = df.reset_index(drop=True)
    print("\n✅ Done processing repeated articles with GPT-4.")
    return df


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
#gdf_1838 = gdf[gdf['edition'] == '1838, Volume 2'].copy()
gdf_1825 = gdf[gdf['edition'] == '1825?'].copy()

if gdf_1825.empty:
    raise ValueError("No entries found for edition '1825' in gazatteers_dataframe.")

# Take metadata from the first row (except 'text')
meta_row = gdf_1825.iloc[0].drop(["text", "pageNum"], errors="ignore").to_dict()
print(meta_row)

# Load combined article entries (article-level info)
json_path = "1825/gazetteer_articles_merged_1825.json"
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
page_to_alto = gdf_1825.set_index("pageNum")["altoXML"].to_dict()

# Map starts_at_page to altoXML (this will be the file where the article starts)
df_articles["altoXML"] = df_articles["starts_at_page"].map(page_to_alto)

df_articles["total_articles"]=total_articles



# Normalise Name

df_articles["name"] = df_articles["name"].apply(simple_norm)
df_articles = fix_ocr_glitches_in_names(df_articles)


# Final Clean:

# Step 1: Deduplicate using earlier smart logic
g_df_deduped = deduplicate_articles_1(df_articles)


# Step 2: Apply cross-page containment cleaner
g_df_clean = remove_nested_and_duplicate_texts_across_pages(g_df_deduped)

# Step 3:

g_df_cleaned = deduplicate_articles_by_token_prefix(g_df_clean)


# Step 4 - FINAL GPT-4 Clean: Merge articles across different rows about the same place

g_df_fix = fix_repeated_articles_with_gpt4_proximity(g_df_cleaned.copy())

g_df_fix.drop(columns=["normalized_name"], inplace=True)


# Step 5: Apply to df_articles (or later on g_df_cleaned if you prefer)

g_df_fix['reference_terms'] = g_df_fix['text'].apply(extra_see_references)

g_df_fix['alter_names'] = g_df_fix['name'].apply(lambda x: extract_names(x)[1])




num_with_references = g_df_fix['reference_terms'].notnull().sum()
non_empty_references = g_df_fix['reference_terms'].apply(lambda x: isinstance(x, list) and len(x) > 0)
num_with_references = non_empty_references.sum()
print(f"✅ Number of articles with references: {num_with_references}")


non_empty_alt_names = g_df_fix['alter_names'].apply(lambda x: isinstance(x, list) and len(x) > 0)
num_with_alter_names = non_empty_alt_names.sum()
print(f"✅ Number of articles with alter_names: {num_with_alter_names}")

total_articles = len(g_df_fix)
percentage = (num_with_references / total_articles) * 100
print(f"✅ {num_with_references} out of {total_articles} articles ({percentage:.2f}%) have references.")


non_empty_refs = g_df_fix['reference_terms'].apply(lambda x: isinstance(x, list) and len(x) > 0)
example_row = g_df_fix[non_empty_refs].iloc[0]

# Then print it nicely
print("📌 Example Article with References:")
print(f"Name: {example_row['name']}")
print(f"Starts at Page: {example_row['starts_at_page']}")
print(f"Reference Terms: {example_row['reference_terms']}")
print(f"Text Snippet: {example_row['text'][:300]}...")


non_empty_alts = g_df_fix['alter_names'].apply(lambda x: isinstance(x, list) and len(x) > 0)
example_alt_row = g_df_fix[non_empty_alts].iloc[0]

# Print it nicely
print("📌 Example Article with Alternative Names:")
print(f"Name: {example_alt_row['name']}")
print(f"Starts at Page: {example_alt_row['starts_at_page']}")
print(f"Alternative Names: {example_alt_row['alter_names']}")
print(f"Text Snippet: {example_alt_row['text'][:300]}...")


# Show summary
print(f"✅ DataFrame created with {len(df_articles)} rows.")
print(g_df_fix.head())

# Save final dataframe to JSON
g_df_fix.to_json(r'1825/gaz_dataframe_1825', orient="index")
print("✅ Created DataFrame with metadata attached. Saved as JSON.")






