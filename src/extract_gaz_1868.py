import pandas as pd
import re
from datetime import datetime
import json
import math
from openai import OpenAI

g_df= pd.read_json('files/gazatteers_dataframe', orient="index")
g_df_1868_vol2 = g_df[g_df['edition'] == '1868, Volume 2'].copy()
g_df_1868_pages = g_df_1868_vol2[
    (g_df_1868_vol2['pageNum'] >= 13) & (g_df_1868_vol2['pageNum'] <= 940)
].copy()
# Initialize OpenAI client
client = OpenAI(api_key="sk-xxx")
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

def robust_split_lines(text):
    lines = text.strip().split('\n')
    if len(lines) == 1:
        lines = re.split(r'(?<=[.?!])\s+(?=[A-Z])', text.strip())
    return lines



def is_index_header(line):
    line_clean = line.strip()
    #print("line clean is %s" % line_clean)

    if re.fullmatch(r'([A-Z]\s+){2,}[A-Z]\.', line_clean):
        #print(f"[Header matched: Case 1] {line_clean}")
        return True

    if re.fullmatch(r'((\d+\s+)?[A-Z][A-Z\-]{1,}\.\s*){1,5}', line_clean):
        #print(f"[Header matched: Case 2] {line_clean}")
        return True
  

    if re.fullmatch(r'([A-Z]{3,4}\s+){2,}[A-Z]{3,4}', line_clean):
        #print(f"[Header matched: Case 3] {line_clean}")
        return True

    if re.fullmatch(r'([A-Z][A-Z\s\-’]*\.){2,5}', line_clean):
        #print(f"[Header matched: Case 4] {line_clean}")
        return True

    if re.fullmatch(r'[A-Z][A-Z\s\-’]*\.\s*\d{1,4}\s+[A-Z][A-Z\s\-’]*\.?', line_clean):
        #print(f"[Header matched: Case 5] {line_clean}")
        return True


        # Case 6: First two UPPERCASE names ending in '.' followed by 'see' in the rest of the line
    if "see" in line_clean.lower():
        dot_words = re.findall(r'\b[A-Z][A-Z0-9\-’()]*\.', line_clean)
        if len(dot_words) >= 2:
            candidate = ' '.join(dot_words[:2])
            #print(f"[Header matched: Case 6] {candidate} (with 'see')")
            return True

        # Case 6: At least two UPPERCASE terms ending with dots, even with spaces in them (e.g., GRANGE BURN. GRANGEMOUTH.)
    dot_names = re.findall(r"\b[A-Z][A-Z0-9\s\-’()']*\.", line_clean)
    if len(dot_names) >= 2:
        #print(f"[Header matched: Case 7] {' '.join(dot_names[:2])}")
        return True

    return False

def remove_initial_index_headers(text, row_num, char_limit=150):
    """Remove page header banner + multi-term uppercase headers from start of page text."""
    header_zone = text[:char_limit]
    #print("Original header_zone:", header_zone)

    # Special case: remove "Till I M P E R I A L GAZE T T E E R or SCOTLAND"
    if row_num == 0 and re.search(r'I\s*M\s*P\s*E\s*R\s*I\s*A\s*L\s+G\s*A\s*Z\s*E\s*T\s*T\s*E\s*E\s*R', header_zone, re.IGNORECASE):
        text = re.sub(
            r'Till\s+I\s*M\s*P\s*E\s*R\s*I\s*A\s*L\s+G\s*A\s*Z\s*E\s*T\s*T\s*E\s*E\s*R\s+or\s+SCOTLAND\.?',
            '', text, count=1, flags=re.IGNORECASE
        )
        print("[Special case-1 removed: Imperial Gazetteer banner]")
        # Update header_zone after removal
        header_zone = text[:char_limit]
    # Special case: remove "Imperial Gazetteer banner" on first page only
    if row_num == 0 and re.search(r'(I|1)M[P|F]E[R|K]IAL\s+GAZETTEER.*SCOTLAND', header_zone, re.IGNORECASE):
        text = re.sub(
            r'(THE\s+)?(TILL\s+)?(I|1)M[P|F]E[R|K]IAL\s+GAZETTEER\s+(OR\s+)?SCOTLAND\.?',
            '',
            text,
            count=1,
            flags=re.IGNORECASE
        )
        print("[Special case-2 removed: Imperial Gazetteer banner]")


        # Update header_zone after removal
        header_zone = text[:char_limit]
        #print("Header zone updated %s" % header_zone)

    # Detect regular multi-term headers
    pattern = re.compile(r"((?:[A-Z][A-Z\s\-’'()]*\.\s*){2,5}|\b[A-Z][A-Z\s\-’'()]*\.\s*\d{1,4}\s+[A-Z][A-Z\s\-’'()]*\.?)")


    matches = pattern.finditer(header_zone)

    headers_to_remove = []
    for match in matches:
        full_match = match.group(0).strip()
        if is_index_header(full_match):
            if "See" in header_zone:
                dot_words = re.findall(r'\b[A-Z][A-Z0-9\-’()]*\.', full_match)
                if len(dot_words) >= 2:
                    trimmed_header = ' '.join(dot_words[:2])
                    headers_to_remove.append(trimmed_header)
            else:
                headers_to_remove.append(full_match)

    if headers_to_remove:
        #print(f"[Headers removed from text start]: {headers_to_remove}")
        for header in headers_to_remove:
            text = re.sub(re.escape(header), '', text, count=1)

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
    #print("------ response_text is %s" % response_text)
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



def split_marked_text_into_chunks_with_overlap(text, pages_per_chunk=2, overlap=0):
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

- Ignore pages that are empty, or contain one or two lines, or contain mostly unreadable characters (e.g. '* e *» « tn 1% •ô # si p| '* -Sf S Ki).
- A proper article begins with a line where the **place name is in UPPERCASE**, followed by a **comma** or a **dot**. Optionally includes 'The' (e.g. `The ABBEY,`, `ABBEY,`, `ABBEY ST. BATHAN'S,`).
- An article may **continue across pages**, sometimes starting with a page header (e.g., `ABERCORN.`) followed by lowercase continuation text (e.g., "`ing once resided...`").
- An article may also begin with `The` (e.g. `The ABBEY,`).
- An article may include **parentheses** (e.g. `ALSH (LOCH.)`).
- An article may be short and referece to another (e.g `ABERARGIE. See Aberdargie.`)
-  Articles migh have the same name but describe different places (`ABBEY, a village ....`; `ABBEY, a small village`; `ABBEY, any distract around` ), extract all separately (e.g. in this case will be 3 different articles.)

- If a new UPPERCASE name appears mid-page followed by a **comma** or a **dot**, treat it as the start of a new article, unless it's obviously part of a malformed continuation.

- If a new page starts with lowercase text that clearly continues the prior sentence, label it as a `"name": "CONTINUATION_ARTICLE"` and extract it as part of the previous article (to be merged later).
- Preserve full original text (do not summarize or modify).
- Extract:
  - `"name"`: original name (or `"CONTINUATION_ARTICLE"` if continuing),
  - `"text"`: full unedited text of the article,
  - `"page_start"` and `"page_finish"` using the `PAGE_START` and `PAGE_END` markers.


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
num_pages = len(g_df_1868_pages)
print(f"Total pages in DataFrame: {num_pages}")

for start in range(0, num_pages, pages_per_chunk):
    end = min(start + pages_per_chunk, num_pages)
    print(f"\nProcessing pages {start} to {end - 1}")

    g_df_1868_subset = g_df_1868_pages.iloc[start:end]
    marked_text = prepare_marked_text(g_df_1868_subset, start)
    raw_json_path = f"files/1868_vol2/main/raw_article_entries_{start:04d}_{end-1:04d}.json"
    result = extract_articles_from_marked_text(
        marked_text,
        calculate_raw_entries=1,
        save_raw_entries_to=raw_json_path
    )

    raw_filename = f"files/1868_vol2/main/raw_extracted_articles_{start:04d}_{end-1:04d}.json"
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved RAW results to {raw_filename} with {result['total_articles']} articles.")

    cleaned_data = merge_index_entries(result)

    clean_filename = f"files/1868_vol2/main/cleaned_articles_{start:04d}_{end-1:04d}.json"
    with open(clean_filename, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    print(f"Saved CLEANED results to {clean_filename} with {cleaned_data['total_articles']} articles.")

print("Smart post-processing complete. Saved to cleaned_articles.json.")



