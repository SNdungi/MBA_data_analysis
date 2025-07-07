# File: app/app_encoder/encoder.py

import pandas as pd
from collections import defaultdict
import re

class DataEncoder:
    def __init__(self, dataframe, config):
        self.raw_df = dataframe
        self.encoded_df = dataframe.copy()
        self.config = config
        self.codebook = defaultdict(dict)
        self.column_map = self.config.get('column_map', {})
        self.warnings = []

    def encode(self):
        print("Starting encoding process...")
        self._encode_likert()
        self._encode_ordinal()
        self._encode_binary()
        self._encode_nominal_simple() # The old nominal method
        self._encode_nominal_multi()  # The new powerful method
        
        print("Encoding complete. Generating final codebook string.")
        codebook_string = self._generate_codebook_string()
        
        return self.encoded_df, codebook_string, self.warnings

    def _perform_smart_mapping(self, col_key, definition_map, encoder_type):
        """
        This method is now ONLY for encoders with pre-defined maps (Likert, Ordinal).
        """
        actual_col_name = self.column_map.get(col_key)
        if not (actual_col_name and actual_col_name in self.encoded_df.columns):
            print(f"WARNING: Could not find a valid column for key '{col_key}'. Skipping.")
            return

        def normalize_text(text):
            if not isinstance(text, str):
                text = str(text)
            # 1. Replace all whitespace sequences (spaces, tabs, newlines) with a single space.
            # 2. Strip leading/trailing space.
            # 3. Convert to lowercase.
            return re.sub(r'\s+', ' ', text).strip().lower()
        
        
        # 1. Prepare for case-insensitive matching using our new robust function
        normalized_def_map = {normalize_text(k): v for k, v in definition_map.items()}
        
        # Get the set of unique values from the data column, also robustly normalized.
        data_series = self.encoded_df[actual_col_name].dropna().apply(normalize_text)
        unique_data_values = set(data_series.unique())
        
        # 2. Perform the sanity check (this logic remains the same)
        unmapped_values = unique_data_values - set(normalized_def_map.keys())
        
        # 3. If there are mismatches, generate a detailed warning for the user
        if unmapped_values:
            original_unmapped = []
            # Find the original values that correspond to the unmapped normalized ones
            for val in self.encoded_df[actual_col_name].dropna().unique():
                if normalize_text(val) in unmapped_values:
                    original_unmapped.append(str(val))
            
            warning = {
                "column_key": col_key, "column_name": actual_col_name,
                "unmapped_values": sorted(list(original_unmapped)),
                "definition_keys": sorted(list(definition_map.keys()))
            }
            self.warnings.append(warning)

        # 4. Perform the smart mapping using the same robust function
        mapped_series = self.encoded_df[actual_col_name].apply(
            lambda x: normalized_def_map.get(normalize_text(x)) if pd.notna(x) else None
        )
        self.encoded_df[actual_col_name] = mapped_series
        
        # 5. Update the codebook (this logic remains the same)
        if not mapped_series.isnull().all():
            self.codebook[col_key]['question'] = actual_col_name
            self.codebook[col_key]['type'] = encoder_type
            self.codebook[col_key]['values'] = definition_map

    def _encode_likert(self):
        likert_configs = self.config.get('Likert', {})
        if not likert_configs: return
        for col_key, likert_map in likert_configs.items():
            self._perform_smart_mapping(col_key, likert_map, 'Likert')

    def _encode_ordinal(self):
        ordinal_configs = self.config.get('Ordinal', {})
        if not ordinal_configs: return
        for col_key, details in ordinal_configs.items():
            order_list = details.get('order', [])
            ordinal_map = {value: i for i, value in enumerate(order_list)}
            self._perform_smart_mapping(col_key, ordinal_map, 'Ordinal')

    # --- NEW, SPECIALIZED METHOD FOR BINARY ---
    def _encode_binary(self):
        """
        Encodes binary columns by dynamically creating a 0/1 map.
        Typically maps 'no', 'false', '0' to 0 and 'yes', 'true', '1' to 1.
        """
        binary_configs = self.config.get('Binary', {})
        if not binary_configs: return
        print(f"Encoding {len(binary_configs)} Binary columns...")
        
        # Define common "negative" and "positive" values
        negative_vals = ['no', 'false', '0', 'n']
        positive_vals = ['yes', 'true', '1', 'y']

        for col_key in binary_configs.keys(): # We only need the key, not the (empty) value
            actual_col_name = self.column_map.get(col_key)
            if not (actual_col_name and actual_col_name in self.encoded_df.columns):
                continue
            
            # Create the dynamic map based on what's found
            dynamic_map = {}
            unique_vals = self.encoded_df[actual_col_name].dropna().astype(str).str.strip().str.lower().unique()

            for val in unique_vals:
                if val in negative_vals:
                    dynamic_map[val] = 0
                elif val in positive_vals:
                    dynamic_map[val] = 1
            
            # Perform the mapping
            mapped_series = self.encoded_df[actual_col_name].astype(str).str.strip().str.lower().map(dynamic_map)
            self.encoded_df[actual_col_name] = mapped_series
            
            # Update the codebook with the map we just created
            self.codebook[col_key]['question'] = actual_col_name
            self.codebook[col_key]['type'] = 'Binary'
            # Reverse the map for the codebook to be human-readable (0: 'no', 1: 'yes')
            self.codebook[col_key]['values'] = {v: k for k, v in dynamic_map.items()}

    # --- NEW, SPECIALIZED METHOD FOR NOMINAL ---
    def _encode_nominal_simple(self):
        """Encodes simple, single-answer nominal columns using factorize."""
        nominal_configs = self.config.get('Nominal', {})
        if not nominal_configs: return
        print(f"Encoding {len(nominal_configs)} simple Nominal columns...")

        for col_key in nominal_configs.keys():
            actual_col_name = self.column_map.get(col_key)
            if not (actual_col_name and actual_col_name in self.encoded_df.columns):
                continue
            
            codes, uniques = pd.factorize(self.encoded_df[actual_col_name].dropna())
            self.encoded_df.loc[self.encoded_df[actual_col_name].notna(), actual_col_name] = codes
            nominal_map = {i: category for i, category in enumerate(uniques)}
            
            self.codebook[col_key]['question'] = actual_col_name
            self.codebook[col_key]['type'] = 'Nominal (Simple)'
            self.codebook[col_key]['values'] = nominal_map

    # --- THIS IS THE NEW, POWERFUL METHOD FOR MULTI-RESPONSE ---
    def _encode_nominal_multi(self):
        """
        Performs one-hot encoding for multi-response questions.
        Replaces one column with multiple new binary (0/1) columns.
        """
        multi_configs = self.config.get('NominalMulti', {})
        if not multi_configs: return
        print(f"Encoding {len(multi_configs)} multi-response Nominal columns...")

        for col_key, details in multi_configs.items():
            actual_col_name = self.column_map.get(col_key)
            if not (actual_col_name and actual_col_name in self.encoded_df.columns):
                continue

            # Get the user-defined list of categories to search for
            # The config must be like: {"categories": ["USA", "Canada", "Mexico", ...]}
            categories_to_find = details.get("categories", [])
            if not categories_to_find:
                print(f"WARNING: No categories defined for multi-response column '{col_key}'. Skipping.")
                continue

            # Create the new columns, initialized to 0
            new_column_names = []
            for category in categories_to_find:
                # Sanitize category name to create a valid column name
                new_col = f"{col_key}_{re.sub(r'[^a-zA-Z0-9]', '', category).lower()}"
                self.encoded_df[new_col] = 0
                new_column_names.append(new_col)
            
            # Iterate through each row of the original column
            for index, row in self.encoded_df[[actual_col_name]].dropna().iterrows():
                cell_content = str(row[actual_col_name]).lower()
                # For each user-defined category, check if it's present in the cell
                for i, category in enumerate(categories_to_find):
                    # Check for the category as a whole word to avoid matching "us" in "russia"
                    if re.search(r'\b' + re.escape(category.lower()) + r'\b', cell_content):
                        self.encoded_df.loc[index, new_column_names[i]] = 1

            # Update the codebook for each new column created
            for i, category in enumerate(categories_to_find):
                self.codebook[new_column_names[i]]['question'] = f"{actual_col_name} (Presence of: {category})"
                self.codebook[new_column_names[i]]['type'] = 'Binary (from Multi-Response)'
                self.codebook[new_column_names[i]]['values'] = {0: 'Not Present', 1: 'Present'}

            # Drop the original, now-encoded column
            self.encoded_df = self.encoded_df.drop(columns=[actual_col_name])

            
    # _generate_codebook_string method remains unchanged
    def _generate_codebook_string(self):
        md_string = "# Codebook\n\n"
        md_string += "This document describes the variables and encoding scheme used in the accompanying encoded data file.\n\n"
        for col_key, details in sorted(self.codebook.items()):
            md_string += f"## `{col_key}`\n\n"
            md_string += f"- **Question:** {details.get('question', 'N/A')}\n"
            md_string += f"- **Encoding Type:** {details.get('type', 'N/A')}\n"
            md_string += "- **Value Mapping:**\n"
            values = details.get('values', {})
            if isinstance(values, dict):
                for key, val in values.items():
                    md_string += f"  - ` {val} ` = {key}\n"
            md_string += "\n---\n\n"
        return md_string