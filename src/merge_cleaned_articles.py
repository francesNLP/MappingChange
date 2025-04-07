import os
import json
from glob import glob


# Set your directory here
INPUT_DIR = "./1806/json_final/"
#OUTPUT_FILE = "./1806/gazetteer_articles_fixed_merged_1806.json"
OUTPUT_FILE = "./1806/gazetteer_articles_merged_1806.json"

all_articles = []

# Find all cleaned JSON files
#json_files = sorted(glob(os.path.join(INPUT_DIR, "fixed_articles_*.json")))
json_files = sorted(glob(os.path.join(INPUT_DIR, "cleaned_articles_*.json")))

for file_path in json_files:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        total_in_file = data.get("total_articles", 0)
        print(file_path, total_in_file)
        for article in data.get("articles", []):
            article["total_articles_page"] = total_in_file
            all_articles.append(article)

# Sort all articles by name
#all_articles_sorted = sorted(all_articles, key=lambda x: x["name"])

# Final output
final_data = {
    "total_articles": len(all_articles),
    "articles": all_articles
}

# Write to file
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_data, f, indent=4, ensure_ascii=False)

print(f"✅ Merged {len(json_files)} files with a total of {len(all_articles)} articles.")
print(f"📝 Output saved to {OUTPUT_FILE}")

