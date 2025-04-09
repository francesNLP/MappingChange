import pandas as pd
import re
from datetime import datetime
import json
import math
from openai import OpenAI

g_df= pd.read_json('files/gazatteers_dataframe', orient="index")
#g_df_1842_vol1 = g_df[g_df['edition'] == '1842, Volume 1'].copy()
#g_df_1842_pages = g_df_1842_vol1[
#    (g_df_1842_vol1['pageNum'] >= 27) & (g_df_1842_vol1['pageNum'] <= 532)
#].copy()

g_df_1842_vol1 = g_df[g_df['edition'] == '1842, Volume 1'].copy()
g_df_1842_pages = g_df_1842_vol1[
    (g_df_1842_vol1['pageNum'] >= 79) & (g_df_1842_vol1['pageNum'] <= 914)
].copy()
# Initialize OpenAI client
client = OpenAI(api_key="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")
import pandas as pd
import json
import re
import math
from openai import OpenAI


def is_index_entry(line: str) -> bool:
    text = line.strip()
    if not text:
        return False

    # Detect purely numeric page markers or Roman numerals
    if text.isdigit() or re.fullmatch(r'[IVXLCDM]+', text):
        return True

    # Detect patterns like ABB ABE (3-letter uppercase blocks)
    if re.fullmatch(r'([A-Z]{3}\s+){1,2}[A-Z]{3}', text):
        return True

    # Ignore full uppercase headers followed by periods like "ABERDEEN."
    if re.fullmatch(r'[A-Z]{2,}\.', text):
        return False

    # Page number before/after headers like "6 ABERDEEN." or "ABERDEEN. 6"
    if re.fullmatch(r'\d+\s+[A-Z]{2,}\.', text) or re.fullmatch(r'[A-Z]{2,}\.\s+\d+', text):
        return False

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

    prompt = f"""
    You are given a chunk of text from historical Gazetteers of Scotland.
Each page is clearly marked using the following format:

### PAGE_START:<page_num> ###
... page text ...
### PAGE_END:<page_num> ###

Your job is to extract the names of locations and their full descriptions.
Articles might span multiple pages, so ensure that:
- Ignore the sentence GAZETTEER OF SCOTLAND.
- Ignore pages that are empty, or contain one or two lines, or contain mostly unreadable characters (e.g. '* e *» « tn 1% •ô # si p| '* -Sf S Ki).
- An article usually begins with a line where the **place name is in UPPERCASE**, followed by a **comma** or **dot**, or optionally includes 'The' (e.g. `The ABBEY,`, `ABBEY,`, `ABBEY ST. BATHAN'S,`, `ABBEY PARISH.`).
- For each article extracted we **absolutly need** their **name**, **text**, **page_start** and **page_finish**. Identify the **first and last page number** where the article appears using the markers.
- Some articles may be **short references** (e.g., `ABBEY PARISH. See Paisley.`). Include these as well.
- An article may **continue across pages**, sometimes starting with a page header (e.g., `ABBOTSFORD.`) followed by lowercase continuation text (e.g., "`ing once resided...`").
- Multiple articles can appear on a single page—one after another. Do not stop after extracting the first one.
- If several article names appear in UPPERCASE (e.g., "ABBOTSHALL, ... ABB’S HEAD (St), ... ABDIE, ..."), extract each of them as a **separate** article, even if they are not at the start of the page.
- If a new page starts with lowercase text that clearly continues the prior sentence, label it as a `"name": "CONTINUATION_ARTICLE"` and extract it as part of the previous article (to be merged later).
- Articles can begin in the middle of a page, even if the previous article was still continuing from earlier pages. For example, after the continuation of an article ends, a new one might start like: "ABBOTSHALL, a parish of...". There may also be more articles following it on the same page—make sure to extract all of them
- Preserve full original text (do not summarize or modify).
- **Avoid indexes**: Any line that is just a 3-letter uppercase word (like `ABB`, `ABE`)  and has **no comma** should be ignored. These are index entries and **not full articles**.
- Preserve original capitalization, punctuation, and formatting as much as possible.
- **Maintain JSON format**.
- it’s okay if an article is partial — just extract it.

Format:
```json
{{
  "articles": [
    {{
      "name": "PLACE NAME",
      "text": "Full article text here...",
      "page_start": 80,
      "page_finish": 80
    }},
    {{
      "name": "CONTINUATION_ARTICLE",
      "text": "Continued text here...",
      "page_start": 81,
      "page_finish": 81
    }}
  ]
}}

 DO NOT summarize or paraphrase. Just extract what you see. Do not make up articles.


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



def prepare_marked_text(df):

    # Define the header patterns (compiled for efficiency)
    header_patterns = [
        r'GAZETTEER OF SCOTLAND\b',
        r'([A-Z]{3}\s+){1,2}[A-Z]{3}\b',             # ABB ABB, ABE ABE
        r'[A-Z]{3}\s+\d+\s+[A-Z]{2,3}\b',             # ETT 509 EU
        r'\d+\s+[A-Z]+\.\b',                          # 6 ABERDEEN.
        r'[A-Z]+\.\s*\d*\b',                          # ABERDEEN. or ABERDEEN. 6
        r'[A-Z]{2,}\s+[A-Z]{2,}\b',                   # ABB ABBEY
        r'[A-Z\s]{5,}'                                # ABE ABE ABE ABE
    ]
    header_regex = re.compile(r'^\s*(?:' + '|'.join(header_patterns) + r')\s*')

    full_text = ""

    for _, row in df.iterrows():
        page_num = row['pageNum']
        text = clean_ocr_text(row['text'])

        # Split into lines
        lines = text.strip().split('\n')

        if lines:
            # Clean header portion from the first line only
            original_line = lines[0]
            #print("Original line %s" %(original_line))
            cleaned_line = header_regex.sub('', original_line).strip()
            lines[0] = cleaned_line
            #print("Cleaned line %s" %(cleaned_line))

        # Rejoin the text
        cleaned_text = "\n".join(lines).strip()

        # Add to final text
        full_text += f"\n### PAGE_START:{page_num} ###\n{cleaned_text}\n### PAGE_END:{page_num} ###\n"

        #print("Full text %s ---- " %(full_text))

    return full_text


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
num_pages = len(g_df_1842_pages)
print(f"Total pages in DataFrame: {num_pages}")

for start in range(140, num_pages, pages_per_chunk):
    end = min(start + pages_per_chunk, num_pages)
    print(f"\nProcessing pages {start} to {end - 1}")

    g_df_1842_subset = g_df_1842_pages.iloc[start:end]
    marked_text = prepare_marked_text(g_df_1842_subset)
    raw_json_path = f"files/1842_vol1/main/raw_article_entries_{start:04d}_{end-1:04d}.json"
    result = extract_articles_from_marked_text(
        marked_text,
        calculate_raw_entries=1,
        save_raw_entries_to=raw_json_path
    )

    raw_filename = f"files/1842_vol1/main/raw_extracted_articles_{start:04d}_{end-1:04d}.json"
    with open(raw_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Saved RAW results to {raw_filename} with {result['total_articles']} articles.")

    cleaned_data = merge_index_entries(result)

    clean_filename = f"files/1842_vol1/main/cleaned_articles_{start:04d}_{end-1:04d}.json"
    with open(clean_filename, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
    print(f"Saved CLEANED results to {clean_filename} with {cleaned_data['total_articles']} articles.")

print("Smart post-processing complete. Saved to cleaned_articles.json.")



