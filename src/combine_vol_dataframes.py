import pandas as pd

# Step 1: Load both DataFrames
df_vol1 = pd.read_json("1838_vol1/gaz_dataframe_1838_vol1", orient="index")
df_vol2 = pd.read_json("1838_vol2/gaz_dataframe_1838_vol2", orient="index")

# Optional sanity check
print(f"Volume 1 rows: {len(df_vol1)}")
print(f"Volume 2 rows: {len(df_vol2)}")

# Step 2: Concatenate the two DataFrames
df_combined = pd.concat([df_vol1, df_vol2], ignore_index=True)

print(f"✅ Total combined rows: {len(df_combined)}")

# Step 3: Save to a new JSON file
df_combined.to_json("1838_combined/gaz_dataframe_1838", orient="index")
print("✅ Combined DataFrame saved to 1838_combined/gaz_dataframe_1838")

