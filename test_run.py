# --- In your future encoding_routes.py ---

from app.app_encoder.encoder import DataEncoder
import pandas as pd

# 1. Load your raw DataFrame
raw_df = pd.read_csv("path/to/your/data.csv")

# 2. Define the configuration (this will eventually come from your UI)
encoding_config = {
    "ordinal_cols": ["experience_level", "education"],
    "nominal_cols": ["department", "location"],
    "likert_cols": {
        "mapping_name": "likert_5_point",
        "positive": ["q9_satisfaction", "q11_ease_of_use"],
        "reverse": ["q10_is_confusing"]
    },
    "mappings": {
        "experience_level": ["Junior", "Mid-level", "Senior", "Lead"],
        "education": ["High School", "Bachelors", "Masters", "PhD"],
        "likert_5_point": {
            "Strongly Disagree": 1,
            "Disagree": 2,
            "Neutral": 3,
            "Agree": 4,
            "Strongly Agree": 5
        }
    }
}

# 3. Instantiate the encoder and run the process
encoder = DataEncoder(dataframe=raw_df, config=encoding_config)
encoded_dataframe, codebook_string = encoder.encode()

# 4. Save the results
encoded_dataframe.to_csv("path/to/encoded_data.csv", index=False)
with open("path/to/codebook.md", "w") as f:
    f.write(codebook_string)

print("--- Encoded DataFrame ---")
print(encoded_dataframe.head())

print("\n--- Generated Codebook ---")
print(codebook_string)