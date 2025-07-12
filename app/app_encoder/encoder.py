# File: app/app_encoder/encoder.py

import pandas as pd
from collections import defaultdict
import re

class DataEncoder:
    """
    DataEncoder operates on a DataFrame where columns are ALREADY named with
    short keys (e.g., 'q1', 'q2'). It uses a config dictionary keyed by these
    short names to perform encoding. The original long question text is only
    used at the end to generate the human-readable codebook.
    """
    def __init__(self, dataframe, config):
        self.df = dataframe.copy() 
        self.config = config
        self.codebook = defaultdict(dict)
        self.column_map = self.config.get('column_map', {})
        self.warnings = []

    def encode(self):
        print("Starting encoding process on DataFrame with short-key headers...")
        self._encode_likert()
        self._encode_ordinal()
        self._encode_binary()
        self._encode_nominal_simple()
        self._encode_nominal_multi()
        
        print("Encoding process complete.")
        return self.df, self.codebook, self.warnings

    def _normalize_text(self, text):
        if not isinstance(text, str):
            text = str(text)
        return re.sub(r'\s+', ' ', text).strip().lower()

    def _perform_smart_mapping(self, col_key, definition_map, encoder_type):
        if col_key not in self.df.columns:
            print(f"WARNING: Column key '{col_key}' not found in the input DataFrame. Skipping.")
            return

        normalized_def_map = {self._normalize_text(k): v for k, v in definition_map.items()}
        
        data_series = self.df[col_key].dropna().apply(self._normalize_text)
        unique_data_values = set(data_series.unique())
        unmapped_normalized_values = unique_data_values - set(normalized_def_map.keys())
        
        if unmapped_normalized_values:
            original_unmapped = [
                str(val) for val in self.df[col_key].dropna().unique() 
                if self._normalize_text(val) in unmapped_normalized_values
            ]
            self.warnings.append({
                "column_key": col_key,
                "unmapped_values": sorted(original_unmapped)
            })

        self.df[col_key] = self.df[col_key].apply(self._normalize_text).map(normalized_def_map)
        
        self.codebook[col_key]['question_text'] = self.column_map.get(col_key, "N/A")
        self.codebook[col_key]['encoder_type'] = encoder_type
        self.codebook[col_key]['value_map'] = {v: k for k, v in definition_map.items()}

    def _encode_likert(self):
        """
        Handles the nested configuration object for Likert scales. It specifically
        extracts the dictionary from the 'map' key to use for encoding.
        """
        likert_configs = self.config.get('Likert', {})
        
        # `config` is the nested object: {"map": {"Agree": 4, ...}, "is_reverse": false}
        for col_key, config in likert_configs.items():
            
            # THE FIX: Get the dictionary from the 'map' key inside the config.
            # Use .get() with a default empty dict {} for safety.
            actual_map = config.get('map', {})
            
            # This check is now crucial. If 'map' key was missing or its value was
            # not a dictionary, actual_map will be empty.
            if not actual_map or not isinstance(actual_map, dict):
                self.warnings.append({
                    "column_key": col_key,
                    "unmapped_values": [f"Configuration Error: Likert definition for this column is missing a valid 'map' object."]
                })
                print(f"WARNING: Likert configuration for '{col_key}' is missing a valid 'map' object. Skipping.")
                continue
                
            # Now, pass the correct mapping dictionary to the main mapping function.
            # `actual_map` is now {"Agree": 4, "Disagree": 2, ...}
            self._perform_smart_mapping(col_key, actual_map, 'Likert')



    def _encode_ordinal(self):
        ordinal_configs = self.config.get('Ordinal', {})
        for col_key, config in ordinal_configs.items():
            order_list = config.get('order', [])
            ordinal_map = {value: i for i, value in enumerate(order_list)}
            self._perform_smart_mapping(col_key, ordinal_map, 'Ordinal')

    def _encode_binary(self):
        binary_configs = self.config.get('Binary', {})
        positive_vals = ['yes', 'true', '1', 'y']
        
        for col_key in binary_configs:
            if col_key not in self.df.columns: continue
            
            self.df[col_key] = self.df[col_key].apply(self._normalize_text).map(lambda x: 1 if x in positive_vals else 0)
            
            self.codebook[col_key]['question_text'] = self.column_map.get(col_key, "N/A")
            self.codebook[col_key]['encoder_type'] = 'Binary'
            self.codebook[col_key]['value_map'] = {0: 'No/False', 1: 'Yes/True'}

    def _encode_nominal_simple(self):
        nominal_configs = self.config.get('Nominal', {})
        for col_key in nominal_configs:
            if col_key not in self.df.columns: continue
            
            codes, uniques = pd.factorize(self.df[col_key])
            self.df[col_key] = pd.Series(codes).replace(-1, pd.NA)
            
            self.codebook[col_key]['question_text'] = self.column_map.get(col_key, "N/A")
            self.codebook[col_key]['encoder_type'] = 'Nominal (Factorized)'
            self.codebook[col_key]['value_map'] = {i: category for i, category in enumerate(uniques)}

    def _encode_nominal_multi(self):
        multi_configs = self.config.get('NominalMulti', {})
        for col_key, config in multi_configs.items():
            if col_key not in self.df.columns: continue

            categories_to_find = config.get("categories", [])
            if not categories_to_find: continue
            
            dummies = self.df[col_key].str.get_dummies(sep=',').reindex(columns=categories_to_find, fill_value=0)
            
            sanitized_names = {cat: f"{col_key}_{re.sub(r'[^a-zA-Z0-9]', '', cat).lower()}" for cat in categories_to_find}
            dummies.rename(columns=sanitized_names, inplace=True)

            original_question = self.column_map.get(col_key, col_key)
            for cat, new_col_name in sanitized_names.items():
                self.codebook[new_col_name]['question_text'] = f"{original_question} (Category: {cat})"
                self.codebook[new_col_name]['encoder_type'] = 'Binary (from Multi-Select)'
                self.codebook[new_col_name]['value_map'] = {0: 'Not Present', 1: 'Present'}

            self.df = self.df.join(dummies)
            self.df.drop(columns=[col_key], inplace=True)