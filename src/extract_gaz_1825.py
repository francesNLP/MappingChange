import pandas as pd
import re
from datetime import datetime
import json
import math
from openai import OpenAI

g_df= pd.read_json('files/gazatteers_dataframe', orient="index")
g_df_1825 = g_df[g_df['edition'] == '1825?'].copy()
g_df_1825_pages = g_df_1825[
    (g_df_1825['pageNum'] >= 5) & (g_df_1825['pageNum'] <= 218)].copy()

# Initialize OpenAI client
client = OpenAI(api_key="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")


def is_index_entry(name, prev_name=None, next_name=None):
    name = name.strip()

    # Case 1: Single 3-letter uppercase word like "ABE"
    if re.fullmatch(r"[A-Z]{3}", name):
        if prev_name and next_name:
            return name in prev_name or name in next_name
        return True

    # Case 2: Repeated 3-letter words like "ABE ABE"
    match_dup = re.fullmatch(r"([A-Z]{3}) \1", name)
    if match_dup:
        return True

    # Case 3: Sequential index words like "ABE ABF"
    match_seq = re.fullmatch(r"([A-Z]{3}) ([A-Z]{3})", name)
    if match_seq:
        word1, word2 = match_seq.groups()
        if word1[:2] == word2[:2] and ord(word2[2]) == ord(word1[2]) + 1:
            return True

    return False

def merge_index_entries(data):
    cleaned_articles = []
    previous_article = None
    articles = data["articles"]

    for idx, article in enumerate(articles):
        name = article["name"].strip()
        text = article["text"].strip()
        prev_name = articles[idx - 1]["name"].strip() if idx > 0 else None
        next_name = articles[idx + 1]["name"].strip() if idx < len(articles) - 1 else None

        if is_index_entry(name, prev_name, next_name):
            if previous_article:
                previous_article["text"] += " " + text
                previous_article["page_finish"] = max(previous_article["page_finish"], article["page_finish"])
        else:
            cleaned_articles.append(article)
            previous_article = article

    # Overlap detection logging
    for i in range(1, len(cleaned_articles)):
        prev = cleaned_articles[i - 1]
        curr = cleaned_articles[i]
        if curr['page_start'] < prev['page_finish']:
            print(f"Overlap detected between '{prev['name']}' and '{curr['name']}' (pages {prev['page_start']}–{prev['page_finish']} and {curr['page_start']}–{curr['page_finish']})")
            prev['page_finish'] = curr['page_start'] - 1

    return {
        "total_articles": len(cleaned_articles),
        "articles": cleaned_articles
    }

def clean_ocr_text(text):
    text = re.sub(r'\u00a7', '7', text)
    text = re.sub(r'\\', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    text = re.sub(r'\bWbittadder\b', 'Whitadder', text)
    text = re.sub(r'\bhe\^th\b', 'heath', text)
    text = re.sub(r'(?<=\w)-\s+', '', text)
    text = re.sub(r'dn elegant', 'an elegant', text)
    text = re.sub(r'i\u00b0(\d+)', r'1°\1', text)
    return text

def format_article_name(name):
    name = name.upper()
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\(ST\.\)', r'(ST.', name)
    return name


def validate_json_format(response_text):
    try:
        # Try to locate the beginning of the "articles" list
        start_match = re.search(r'\{\s*"articles"\s*:\s*\[', response_text)
        if not start_match:
            raise ValueError("Missing 'articles' key or opening list bracket.")

        start_index = start_match.end()

        # Now try to find the LAST complete object before a broken one
        article_pattern = re.finditer(r'\{\s*"name"\s*:\s*".+?",.*?"page_finish"\s*:\s*\d+\s*\}', response_text[start_index:], re.DOTALL)
        valid_articles = []
        last_end = start_index

        for match in article_pattern:
            last_end = start_index + match.end()
            valid_articles.append(match.group())

        if not valid_articles:
            raise ValueError("No valid article blocks found.")

        cleaned_json_str = '{ "articles": [\n' + ",\n".join(valid_articles) + '\n] }'

        return json.loads(cleaned_json_str)

    except Exception as e:
        print(f"\n❌ JSON Validation Error: {e}")
        print("🔍 Problematic text (preview):")
        print("```json\n" + response_text + "\n```")
        print("---")
        return None



#def validate_json_format(response_text):
#    try:
#        # Try to extract the JSON blob more precisely
#        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
#        if not json_match:
#            raise ValueError("No JSON structure with 'articles' list found.")
#
#        cleaned_json = json_match.group(0)
#        # Fix common issues: remove trailing commas before closing brackets/braces
#        cleaned_json = re.sub(r",\s*([}\]])", r"\1", cleaned_json)
#        # Try parsing
#        return json.loads(cleaned_json)
#    except Exception as e:
#        print(f"\nJSON Validation Error: {e}")
#        print("🔍 Problematic text (preview):")
#        #preview = response_text[:1000] + "..." if len(response_text) > 1000 else response_text
#        #preview = response_text[:1000] + "..." if len(response_text) > 1000 else response_text
#        print(response_text)
#        print("---")
#        return None



#def validate_json_format(response_text):
#    try:
#        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
#        if not json_match:
#            raise ValueError("No JSON detected.")
#        cleaned_json = json_match.group(0)
#        cleaned_json = re.sub(r",\s*\}", "}", cleaned_json)
#        cleaned_json = re.sub(r",\s*\]", "]", cleaned_json)
#        return json.loads(cleaned_json)
#    except Exception as e:
#        print(f"JSON Validation Error: {e}")
#        return None

def prepare_marked_text(df):
    full_text = ""
    for _, row in df.iterrows():
        page_num = row['pageNum']
        text = clean_ocr_text(row['text'])
        full_text += f"\n### PAGE_START:{page_num} ###\n{text}\n### PAGE_END:{page_num} ###\n"
    return full_text

def split_marked_text_into_chunks_with_overlap(text, pages_per_chunk=3, overlap=1):
    page_blocks = re.findall(r"(### PAGE_START:(\d+) ###.*?### PAGE_END:\2 ###)", text, re.DOTALL)
    chunks = []
    i = 0
    while i < len(page_blocks):
        chunk_block = page_blocks[i:i + pages_per_chunk]
        chunk_text = "\n".join(block[0] for block in chunk_block)
        chunks.append(chunk_text)
        i += (pages_per_chunk - overlap)
    return chunks

def process_marked_chunk(chunk, chunk_index, total_chunks):
    prompt = f"""
You are given a chunk of text from historical Gazetteers of Scotland.
Each page is clearly marked using the following format:

### PAGE_START:<page_num> ###
... page text ...
### PAGE_END:<page_num> ###

Your job is to extract the names of locations and their full descriptions.
Articles might span multiple pages, so ensure that:
- **Ignore** the sentence **THE GAZETTEER OF SCOTLAND**
- An article typically begins with a line where the **name is in UPPERCASE**, followed by a **comma (,)**. Use this pattern to detect article starts.
- An article name sometimes has the article *The* followed by the name in UPPERCASE
- Extract the full **name** exactly as it appears, but exclude the comma if present.
- Extract the full unedited **text** of the article.
- **Do not summarize** - extract the full text.
- **Avoid indexes**: Any line that is just a 3-letter uppercase word (like `ABB`, `ABE`)  and has **no comma** should be ignored. These are index entries and **not full articles**.
- If text follows an index word, it usually **belongs to the previous article** — do not create a new article for it.
- Preserve original capitalization, punctuation, and formatting as much as possible.
- **Maintain JSON format**.
- Identify the **first and last page number** where the article appears using the markers.
- it’s okay if an article is partial — just extract it.

Format:
```json
{{
  "articles": [
    {{
      "name": "PLACE NAME",
      "text": "Full article text...",
      "page_start": 43,
      "page_finish": 44
    }},
    ...
  ]
}}

Avoid summaries. Do not invent pages. Just extract what you see.

CHUNK {chunk_index + 1} of {total_chunks}
{chunk}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Extract places and descriptions from the text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        return validate_json_format(response.choices[0].message.content)
    except Exception as e:
        print(f"Error processing chunk {chunk_index + 1}: {e}")
        return None

def merge_articles_with_pages(article_entries):
    merged = []
    article_map = {}
    for entry in article_entries:
        name = format_article_name(entry["name"])
        text = entry["text"].strip()
        p_start = entry["page_start"]
        p_end = entry["page_finish"]
        if name in article_map:
            if text not in article_map[name]["text"]:
                article_map[name]["text"] += " " + text
            article_map[name]["page_start"] = min(article_map[name]["page_start"], p_start)
            article_map[name]["page_finish"] = max(article_map[name]["page_finish"], p_end)
        else:
            article_map[name] = {
                "name": name,
                "text": text,
                "page_start": p_start,
                "page_finish": p_end
            }
            merged.append(article_map[name])
    return merged


def extract_articles_from_marked_text(marked_text, calculate_raw_entries=1, save_raw_entries_to=None, read_raw_entries_from=None):
    if calculate_raw_entries:
        chunks = split_marked_text_into_chunks_with_overlap(marked_text)
        article_entries = []
        for i, chunk in enumerate(chunks):
            print("we are at chunk  %s" %i)
            result = process_marked_chunk(chunk, i, len(chunks))
            if result:
                article_entries.extend(result.get("articles", []))
            else:
                #result = process_marked_chunk(chunk, i, len(chunks))
                #if result:
                #    article_entries.extend(result.get("articles", []))
                #else:
                print(f"Failed to process chunk {i}, after retrying")
                

        if save_raw_entries_to:
            with open(save_raw_entries_to, "w", encoding="utf-8") as f:
                json.dump(article_entries, f, indent=4, ensure_ascii=False)
            print(f"✅ Saved article entries to {save_raw_entries_to}")
    else:
        if not read_raw_entries_from:
            raise ValueError("You must specify 'read_raw_entries_from' when 'calculate_raw_entries' is False")
        with open(read_raw_entries_from, "r", encoding="utf-8") as f:
            article_entries = json.load(f)

    merged_articles = merge_articles_with_pages(article_entries)
    return {
        "total_articles": len(merged_articles),
        "articles": merged_articles
    }

# Set the number of pages per chunk
pages_per_chunk = 10
num_pages = len(g_df_1825_pages)
print(f"Total pages in DataFrame: {num_pages}")

for start in range(0, num_pages, pages_per_chunk):
    end = min(start + pages_per_chunk, num_pages)
    print(f"\nProcessing pages {start} to {end - 1}")

    g_df_1825_subset = g_df_1825_pages.iloc[start:end]
    marked_text = prepare_marked_text(g_df_1825_subset)
    raw_json_path = f"files/1825/main2/raw_article_entries_{start:04d}_{end-1:04d}.json"
    result = extract_articles_from_marked_text(
        marked_text,
        calculate_raw_entries=1,
        save_raw_entries_to=raw_json_path
    )

    raw_filename = f"files/1825/main2/raw_extracted_articles_{start:04d}_{end-1:04d}.json"
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved RAW results to {raw_filename} with {result['total_articles']} articles.")

    cleaned_data = merge_index_entries(result)

    clean_filename = f"files/1825/main2/cleaned_articles_{start:04d}_{end-1:04d}.json"
    with open(clean_filename, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    print(f"Saved CLEANED results to {clean_filename} with {cleaned_data['total_articles']} articles.")

print("Smart post-processing complete. Saved to cleaned_articles.json.")



