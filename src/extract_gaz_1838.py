import pandas as pd
import re
from datetime import datetime
import json
import math
from openai import OpenAI

g_df= pd.read_json('files/gazatteers_dataframe', orient="index")
g_df_1838_vol1 = g_df[g_df['edition'] == '1838, Volume 1'].copy()
g_df_1838_pages = g_df_1838_vol1[
    (g_df_1838_vol1['pageNum'] >= 27) & (g_df_1838_vol1['pageNum'] <= 532)
].copy()
# Initialize OpenAI client
client = OpenAI(api_key="XXX")



import pandas as pd
import json
import re
import math
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key="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")


def is_index_entry(line: str) -> bool:
    """
    Determine if a line is an index entry (non-article content) that should be skipped.
    Returns True for index-like lines, False for normal content lines.
    """
    text = line.strip()
    if not text:
        return False  # skip empty lines

    # Skip standalone page numbers (e.g., "496") or Roman numerals (likely page headers)
    if text.isdigit():
        return True
    if re.fullmatch(r'[IVXLCDM]+', text):
        return True

    # **Updated logic:** Do NOT mark as index if the line is a full uppercase place name
    # followed by a period or if it includes a number with the place name.
    # These indicate article headers in the new format, not index entries.
    if re.fullmatch(r'[A-Z]{2,}\.', text):
        return False  # e.g. "ABERDEEN." (valid article header, not an index)
    if re.fullmatch(r'\d+\s+[A-Z]{2,}', text) or re.fullmatch(r'[A-Z]{2,}\s+\d+', text):
        return False  # e.g. "496 GLASGOW" or "GLASGOW 496" (page number + name)

    # (No longer treating 3-letter codes as index entries)
    # Any previous rule that identified 3-letter uppercase codes as index has been removed.

    # Default: not an index entry
    return False


def merge_index_entries(data):
    cleaned_articles = []
    previous_article = None

    for article in data["articles"]:
        name = article["name"]
        text = article["text"].strip()

        if is_index_entry(name):
            if previous_article:
                previous_article["text"] += " " + text
                previous_article["page_finish"] = max(previous_article["page_finish"], article["page_finish"])
        else:
            cleaned_articles.append(article)
            previous_article = article

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
        article_pattern = re.finditer(r'\{\s*"name"\s*:\s*".+?",.*?"page_finish"\s*:\s*\d+\s*\}', response_text[
start_index:], re.DOTALL)
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

def prepare_marked_text(df):
    full_text = ""
    for _, row in df.iterrows():
        page_num = row['pageNum']
        text = clean_ocr_text(row['text'])

        # Split into lines and remove the first header line if it's a known header format
        lines = text.strip().split('\n')

        if lines:
            header_line = lines[0].strip()

            # Match patterns like "ABERCORN." or "495 ABERCORN."
            if re.fullmatch(r'[A-Z\s]{2,}\.', header_line) or re.fullmatch(r'\d+\s+[A-Z\s]{2,}\.', header_line):
                lines = lines[1:]  # drop header line

        cleaned_text = "\n".join(lines).strip()

        full_text += f"\n### PAGE_START:{page_num} ###\n{cleaned_text}\n### PAGE_END:{page_num} ###\n"

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

    #print("The chunk is %s --- out of %s" %(chunk, chunk_index))
    prompt = f"""
You are given a chunk of text from historical Gazetteers of Scotland.
Each page is clearly marked using the following format:

### PAGE_START:<page_num> ###
... page text ...
### PAGE_END:<page_num> ###

Your job is to extract the **names of places** and their **full descriptions** (articles). Please follow these detailed rules:

- Ignore the sentence GAZETTEER OF SCOTLAND.
- Ignore pages that are empty, or contain one or two lines, or contain mostly unreadable characters (e.g. '* e *» « tn 1% •ô # si p| '* -Sf S Ki).
- A proper article begins with a line where the **place name is in UPPERCASE**, followed by a **comma**, or optionally includes 'The' (e.g. `The ABBEY,`, `ABBEY,`, `ABBEY ST. BATHAN'S,`).
- An article may **continue across pages**, sometimes starting with a page header (e.g., `ABERCORN.`) followed by lowercase continuation text (e.g., "`ing once resided...`").
- If a new page starts with lowercase text that clearly continues the prior sentence, label it as a `"name": "CONTINUATION_ARTICLE"` and extract it as part of the previous article (to be merged later).
- Do **not** create new articles from UPPERCASE words followed by periods unless they match the UPPERCASE + comma rule and introduce **substantial new content**.
- Preserve full original text (do not summarize or modify).
- Extract:
  - `"name"`: original name (or `"CONTINUATION_ARTICLE"` if continuing),
  - `"text"`: full unedited text of the article,
  - `"page_start"` and `"page_finish"` using the `PAGE_START` and `PAGE_END` markers.

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
    {{
      "name": "CONTINUATION_ARTICLE",
      "text": "continued text here...",
      "page_start": 45,
      "page_finish": 45
    }}
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
    """
    Merges articles across pages by recognizing placeholder 'CONTINUATION_ARTICLE' entries
    and appending them to the most recent real article.
    """
    merged = []
    previous_article = None

    for entry in article_entries:
        name = format_article_name(entry["name"])
        text = entry["text"].strip()
        p_start = entry["page_start"]
        p_end = entry["page_finish"]

        if name == "CONTINUATION_ARTICLE":
            if previous_article:
                previous_article["text"] += " " + text
                previous_article["page_finish"] = max(previous_article["page_finish"], p_end)
            continue

        # Otherwise treat as a normal new article
        formatted_entry = {
            "name": name,
            "text": text,
            "page_start": p_start,
            "page_finish": p_end
        }
        merged.append(formatted_entry)
        previous_article = formatted_entry

    return merged



def extract_articles_from_marked_text(marked_text, calculate_raw_entries=1, save_raw_entries_to=None, read_raw_entries_from=None):
    if calculate_raw_entries:
        chunks = split_marked_text_into_chunks_with_overlap(marked_text)
        article_entries = []
        for i, chunk in enumerate(chunks):
            result = process_marked_chunk(chunk, i, len(chunks))
            if result:
                article_entries.extend(result.get("articles", []))
            else:
                print(f"Failed to process chunk {i + 1}")

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
num_pages = len(g_df_1838_pages)
print(f"Total pages in DataFrame: {num_pages}")

for start in range(0, num_pages, pages_per_chunk):
    end = min(start + pages_per_chunk, num_pages)
    print(f"\nProcessing pages {start} to {end - 1}")

    g_df_1838_subset = g_df_1838_pages.iloc[start:end]
    marked_text = prepare_marked_text(g_df_1838_subset)
    raw_json_path = f"files/1838_vol1/main/raw_article_entries_{start:04d}_{end-1:04d}.json"
    result = extract_articles_from_marked_text(
        marked_text,
        calculate_raw_entries=1,
        save_raw_entries_to=raw_json_path
    )

    raw_filename = f"files/1838_vol1/main/raw_extracted_articles_{start:04d}_{end-1:04d}.json"
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved RAW results to {raw_filename} with {result['total_articles']} articles.")

    cleaned_data = merge_index_entries(result)

    clean_filename = f"files/1838_vol1/main/cleaned_articles_{start:04d}_{end-1:04d}.json"
    with open(clean_filename, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    print(f"Saved CLEANED results to {clean_filename} with {cleaned_data['total_articles']} articles.")

print("Smart post-processing complete. Saved to cleaned_articles.json.")



