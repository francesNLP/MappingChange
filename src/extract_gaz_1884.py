import pandas as pd
import re
from datetime import datetime
import json
import math
from openai import OpenAI

g_df= pd.read_json('files/gazatteers_dataframe', orient="index")
g_df_1884_vol6 = g_df[g_df['edition'] == '1884-1885, Volume 6'].copy()
g_df_1884_pages = g_df_1884_vol6[
    (g_df_1884_vol6['pageNum'] >= 13) & (g_df_1884_vol6['pageNum'] <= 327)
].copy()
# Initialize OpenAI client
client = OpenAI(api_key="sk-xxxx")

import re

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
    text = re.sub(r'\b1SS0\b', '1880', text)  # misread year
    text = re.sub(r'\blSS1\b', '1881', text)
    text = re.sub(r'1S(\d{2})', r'18\1', text)  # general pattern for 1800s
    text = re.sub(r'\bO\b', '0', text)         # misread zero

    return text



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

def robust_split_lines(text):
    lines = text.strip().split('\n')
    if len(lines) == 1:
        lines = re.split(r'(?<=[.?!])\s+(?=[A-Z])', text.strip())
    return lines

def is_index_header(line):
    """
    For the 1884–1885 Ordnance Gazetteer: treat lines in full UPPERCASE without punctuation as index headers.
    """
    line_clean = line.strip()

    # Ignore empty lines
    if not line_clean:
        return False

    # If line is all UPPERCASE and doesn't contain a period or comma → it's a header
    if line_clean.isupper() and not re.search(r'[.,]', line_clean):
        #print(f"[Index header detected]: '{line_clean}'")
        return True

    return False



def remove_initial_index_headers(text, row_num, char_limit=180):
    """Remove Gazetteer-specific banners and multi-word uppercase headers at the start of a page."""
    header_zone = text[:char_limit]
    #print("Original header_zone:", header_zone)

    # Special case: Remove "ORDNANCE GAZETTEER OF SCOTLAND" banner on first page
    if row_num == 0 and re.search(r'ORDNANCE\s+GAZETTEER\s+OF\s+SCOTLAND[.,]?', header_zone, re.IGNORECASE):
        text = re.sub(r'ORDNANCE\s+GAZETTEER\s+OF\s+SCOTLAND[.,]?', '', text, count=1, flags=re.IGNORECASE)
        #print("[Removed: ORDNANCE GAZETTEER OF SCOTLAND banner]")
        header_zone = text[:char_limit]

    # Detect and remove full-line uppercase headers (e.g., "ABERDEEN ABERDEEN")
    index_header_match = re.match(r'^([A-Z]{3,}(?:\s+[A-Z]{3,}){0,3})\s+', header_zone)
    if index_header_match:
        header_candidate = index_header_match.group(1)
        # Ensure it does not contain a period or comma (not a valid article)
        if not re.search(r'[.,]', header_candidate):
            #print(f"[Removed uppercase header]: '{header_candidate}'")
            text = text[len(header_candidate):].lstrip()

    return text



def prepare_marked_text(df, row_num, collapse_text=True):
    full_text = ""

    for _, row in df.iterrows():
        page_num = row['pageNum']
        raw_text = row['text']


        raw_text = remove_initial_index_headers(raw_text, row_num)

        if collapse_text:
            cleaned = clean_ocr_text(raw_text)
            cleaned_text = re.sub(r'\s+', ' ', cleaned).strip()
        else:
            lines = robust_split_lines(raw_text)
            #print(f"\ntext for page {page_num} is:\n{raw_text}\n---")
            #print(f"Split into {len(lines)} lines")

            first_two = []
            for line in lines[:2]:
                cleaned_line = clean_ocr_text(line)
                if not is_index_header(cleaned_line):
                    first_two.append(cleaned_line)

            rest = lines[2:]
            cleaned_text = "\n".join(first_two + rest).strip()

        full_text += f"\n### PAGE_START:{page_num} ###\n{cleaned_text}\n### PAGE_END:{page_num} ###\n"

    return full_text


def format_article_name(name):
    name = name.upper()
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\(ST\.\)', r'(ST.', name)
    return name

def validate_json_format(response_text):
    try:
        #print("Validating JSON format...")
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



def split_marked_text_into_chunks_with_overlap(text, pages_per_chunk=2, overlap=1):
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

Your task is to extract the **names of places** and their **full descriptions (articles)** from this Gazetteer text. Follow these detailed rules:

1. What to Ignore:
- The banner: `ORDNANCE GAZETTEER OF SCOTLAND`
- WORDS thare are ALL UPPERCASE in doesnt have a comma or dot after them (e.g. ingore ABERDEEN, but do not ingore ABERDEEN. )
- Pages that are:
  - Completely empty,
  - Only one or two lines long,
  - Mostly unreadable or corrupted (e.g., `* e *» « tn 1% •ô # si p| '* -Sf S Ki`)

2. How to Identify a Valid Article: A valid article begins with a place name that:
- Starts with a **Capitalized Word** (e.g., Abbey, Aberdeen, Abbeyhill, Abbey St Bathans, Abbey Well, Abbey Land,)
- If the name contains multiple words, **each word should be capitalized**
- Is **immediately followed by a comma or a period**, like:
  - `Abbey, a parish in ...`
  - `Abbeytown. See Airt.`
  - `Abbey Bathans. See Abbey St Bathans.`

3. Articles can appear in two formats:
- **Full description**: `Abbey, a burn and a small headland ...`
- **Redirect**: `Abbeytown. See Airth.` or `Abbey Bathans. See Abbey St Bathans.` 

4.  Multiple Articles With the Same Name: If the same place name appears multiple times with different descriptions (e.g.):
- `Abbey, a village ...`
- `Abbey, a small village ...`
- `Abbey, a district around ...`
Treat each as a separate article and extract all versions.

5. Articles Spanning Pages:
- Some articles (e.g., `Aberdeen`, `Edinburgh`, `Glasgow`, etc ..) span multiple pages.
- If a new page begins with lowercase text clearly continuing the previous sentence, extract it as a:
  ```json
  "name": "CONTINUATION_ARTICLE"
  ```

6. Mid-Page Article Starts: If a new capitalized name (e.g., Abbey, Aberdeen, Abbey St Bathans, Abbey Land, Abbey Well) appears mid-page or end-page, treat it as the start of a new article, even if it's not at the beginning of the chunk

7. Avoid False Article Starts: Ignore fragments like:`church of Uequhatit, Elginshire.`. These are part of an existing article, not new place names. In that case, just label it as CONTINUATION_ARTICLE

8. Extract:
  - `"name"`: original name (or `"CONTINUATION_ARTICLE"` if continuing),
  - `"text"`: full unedited text of the article,
  - `"page_start"` and `"page_finish"` using the `PAGE_START` and `PAGE_END` markers.

9. Output Format: Return a valid JSON object like this:
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
        #print("Entry is %s ---" %entry)
        name = entry["name"]
        if name != "CONTINUATION_ARTICLE":
                name = format_article_name(name)
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
num_pages = len(g_df_1884_pages)
print(f"Total pages in DataFrame: {num_pages}")

for start in range(0, num_pages, pages_per_chunk):
    end = min(start + pages_per_chunk, num_pages)
    print(f"\nProcessing pages {start} to {end - 1}")

    g_df_1884_subset = g_df_1884_pages.iloc[start:end]
    marked_text = prepare_marked_text(g_df_1884_subset, start)
    raw_json_path = f"files/1884_vol6/main/raw_article_entries_{start:04d}_{end-1:04d}.json"
    result = extract_articles_from_marked_text(
        marked_text,
        calculate_raw_entries=1,
        save_raw_entries_to=raw_json_path
    )

    raw_filename = f"files/1884_vol6/main/raw_extracted_articles_{start:04d}_{end-1:04d}.json"
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved RAW results to {raw_filename} with {result['total_articles']} articles.")

    cleaned_data = merge_index_entries(result)

    clean_filename = f"files/1884_vol6/main/cleaned_articles_{start:04d}_{end-1:04d}.json"
    with open(clean_filename, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    print(f"Saved CLEANED results to {clean_filename} with {cleaned_data['total_articles']} articles.")

print("Smart post-processing complete. Saved to cleaned_articles.json.")



