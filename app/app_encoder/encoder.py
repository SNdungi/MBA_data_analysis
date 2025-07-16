# File: app/app_encoder/encoder.py

import pandas as pd
from collections import defaultdict
import re

class DataEncoder:
    def __init__(self, dataframe, config):
        self.df = dataframe.copy() 
        self.config = config
        self.codebook = defaultdict(dict)
        self.column_map = self.config.get('column_map', {})
        self.warnings = []
        self.learned_value_maps = {}

    def encode(self):
        print("Starting encoding process...")
        self._encode_likert()
        self._encode_ordinal()
        self._encode_binary()
        self._encode_nominal_simple()
        self._encode_nominal_multi()
        
        print("Encoding process complete.")

        return self.df, self.codebook, self.warnings, self.learned_value_maps

    def _normalize_text(self, text):
        if not isinstance(text, str):
            text = str(text)
        return re.sub(r'\s+', ' ', text).strip().lower()

    def _perform_smart_mapping(self, col_key, definition_map, encoder_type):
        # ... (This method is unchanged) ...
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
        likert_configs = self.config.get('Likert', {})
        for col_key, config in likert_configs.items():
            actual_map = config.get('map', {})
            if not actual_map or not isinstance(actual_map, dict):
                self.warnings.append({
                    "column_key": col_key,
                    "unmapped_values": [f"Configuration Error: Likert definition for this column is missing a valid 'map' object."]
                })
                print(f"WARNING: Likert configuration for '{col_key}' is missing a valid 'map' object. Skipping.")
                continue
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
        value_map = {0: 'No/False', 1: 'Yes/True'} # This is the standard map

        for col_key in binary_configs:
            if col_key not in self.df.columns: continue
            
            self.df[col_key] = self.df[col_key].apply(self._normalize_text).map(lambda x: 1 if x in positive_vals else 0)
            
            # Populate the codebook and store the learned map
            self.codebook[col_key]['question_text'] = self.column_map.get(col_key, "N/A")
            self.codebook[col_key]['encoder_type'] = 'Binary'
            self.codebook[col_key]['value_map'] = value_map
            self.learned_value_maps[col_key] = value_map # Store for persistence

    def _encode_nominal_simple(self):
        nominal_configs = self.config.get('Nominal', {})
        for col_key in nominal_configs:
            if col_key not in self.df.columns: continue
            
            # Using .astype('category') is a more robust way to handle factorizing
            self.df[col_key] = self.df[col_key].astype('category')
            value_map = dict(enumerate(self.df[col_key].cat.categories))
            self.df[col_key] = self.df[col_key].cat.codes.replace(-1, pd.NA)

            # Populate the codebook and store the learned map
            self.codebook[col_key]['question_text'] = self.column_map.get(col_key, "N/A")
            self.codebook[col_key]['encoder_type'] = 'Nominal (Factorized)'
            self.codebook[col_key]['value_map'] = value_map
            self.learned_value_maps[col_key] = value_map # Store for persistence

    def _encode_nominal_multi(self):
        # ... (This method is unchanged as it creates new binary columns, which are handled by _encode_binary) ...
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