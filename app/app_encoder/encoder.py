<<<<<<< HEAD
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from typing import Dict, List, Any, Tuple

class DataEncoder:
    """
    A robust, configuration-driven class for encoding mixed-type survey data.

    This class uses scikit-learn for standard encoding practices and provides
    custom logic for Likert scales, including reverse-coding. It operates based on a
    configuration dictionary and generates a detailed codebook of all transformations.
    """

    def __init__(self, dataframe: pd.DataFrame, config: Dict[str, Any]):
        """
        Initializes the DataEncoder.

        Args:
            dataframe (pd.DataFrame): The raw dataframe with original string values.
            config (Dict[str, Any]): A configuration dictionary detailing how to encode
                                      the data. Expected structure:
                                      {
                                          "ordinal_cols": ["col1", "col2"],
                                          "nominal_cols": ["col3", "col4"],
                                          "likert_cols": {
                                              "positive": ["col5", "col6"],
                                              "reverse": ["col7"]
                                          },
                                          "mappings": {
                                              "col1": ["Low", "Medium", "High"],
                                              "likert_5_point": {
                                                  "Strongly Disagree": 1, ...
                                              }
                                          }
                                      }
        """
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("Input 'dataframe' must be a pandas DataFrame.")
        if not isinstance(config, dict):
            raise TypeError("Input 'config' must be a dictionary.")

        self.original_df = dataframe.copy()
        self.config = config
        self.encoded_df = dataframe.copy()
        self.codebook = ["# Data Encoding Codebook\n\n"]
        self.fitted_encoders = {} # To store fitted sklearn encoders

    def encode(self) -> Tuple[pd.DataFrame, str]:
        """
        Orchestrates the entire encoding process based on the configuration.

        Returns:
            Tuple[pd.DataFrame, str]: A tuple containing the fully encoded
                                      DataFrame and the generated codebook as a string.
        """
        print("--- Starting Data Encoding Process ---")
        
        # The order of these operations is intentional
        if self.config.get("ordinal_cols"):
            self._encode_ordinal()
        
        if self.config.get("likert_cols"):
            self._encode_likert()
        
        if self.config.get("nominal_cols"):
            self._encode_nominal()
            
        print("--- Data Encoding Process Complete ---")
        return self.encoded_df, "".join(self.codebook)

    def _add_to_codebook(self, title: str, details: List[str]):
        """Helper to format and append sections to the codebook."""
        self.codebook.append(f"## Column: {title}\n")
        self.codebook.append("-------------------\n")
        for detail in details:
            self.codebook.append(f"- {detail}\n")
        self.codebook.append("\n")

    def _encode_ordinal(self):
        """Encodes ordinal columns using scikit-learn's OrdinalEncoder."""
        print("Encoding ordinal columns...")
        cols = self.config["ordinal_cols"]
        mappings = self.config["mappings"]

        for col in cols:
            if col not in self.encoded_df.columns:
                print(f"Warning: Ordinal column '{col}' not found in DataFrame. Skipping.")
                continue
            
            # The order of categories for each column must be specified in the config
            category_order = mappings.get(col)
            if not category_order:
                raise ValueError(f"Mapping for ordinal column '{col}' not found in config['mappings'].")
            
            encoder = OrdinalEncoder(categories=[category_order], dtype=int)
            
            # Reshape column for the encoder
            column_data = self.encoded_df[[col]]
            self.encoded_df[col] = encoder.fit_transform(column_data)
            self.fitted_encoders[col] = encoder

            # Generate codebook entry
            codebook_details = [f"Type: Ordinal (Integer Encoded)"]
            for i, category in enumerate(category_order):
                codebook_details.append(f"Original: '{category}' -> Encoded: {i}")
            self._add_to_codebook(col, codebook_details)
            
    def _encode_likert(self):
        """Encodes Likert scale columns, handling normal and reverse-coded items."""
        print("Encoding Likert scale columns...")
        likert_config = self.config["likert_cols"]
        mapping_name = likert_config.get("mapping_name", "likert_5_point")
        likert_map = self.config["mappings"].get(mapping_name)

        if not likert_map:
            raise ValueError(f"Likert mapping '{mapping_name}' not found in config['mappings'].")

        # Create the reverse map
        max_val = max(likert_map.values())
        min_val = min(likert_map.values())
        reverse_map = {k: (max_val + min_val - v) for k, v in likert_map.items()}

        # Process positively-worded items
        for col in likert_config.get("positive", []):
            self.encoded_df[col] = self.encoded_df[col].map(likert_map)
            details = [f"Type: Likert Scale (Mapping: {mapping_name})"] + [f"'{k}' -> {v}" for k, v in likert_map.items()]
            self._add_to_codebook(col, details)

        # Process reverse-coded items
        for col in likert_config.get("reverse", []):
            self.encoded_df[col] = self.encoded_df[col].map(reverse_map)
            details = [f"Type: Likert Scale (REVERSE CODED, Mapping: {mapping_name})"] + [f"'{k}' -> {v}" for k, v in reverse_map.items()]
            self._add_to_codebook(col, details)
            
        # Ensure the columns are numeric, coercing errors to NaN
        all_likert_cols = likert_config.get("positive", []) + likert_config.get("reverse", [])
        self.encoded_df[all_likert_cols] = self.encoded_df[all_likert_cols].apply(pd.to_numeric, errors='coerce')


    def _encode_nominal(self):
        """Encodes nominal columns using scikit-learn's OneHotEncoder."""
        print("Encoding nominal columns...")
        cols = self.config["nominal_cols"]
        
        # Filter out columns that don't exist
        cols_to_encode = [col for col in cols if col in self.encoded_df.columns]
        if not cols_to_encode:
            print("No nominal columns found to encode.")
            return

        encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False, drop='first')
        
        # Fit and transform the data
        encoded_data = encoder.fit_transform(self.encoded_df[cols_to_encode])
        
        # Create new column names
        new_col_names = encoder.get_feature_names_out(cols_to_encode)
        
        # Create a new DataFrame with the one-hot encoded columns
        encoded_cols_df = pd.DataFrame(encoded_data, columns=new_col_names, index=self.encoded_df.index, dtype=int)
        
        # Drop original nominal columns and join the new ones
        self.encoded_df = self.encoded_df.drop(columns=cols_to_encode)
        self.encoded_df = self.encoded_df.join(encoded_cols_df)
        self.fitted_encoders['nominal'] = encoder

        # Generate codebook entries
        for col in cols_to_encode:
            categories = self.fitted_encoders['nominal'].categories_[cols_to_encode.index(col)]
            details = [f"Type: Nominal (One-Hot Encoded, drop_first=True)"]
            details.append(f"Original categories: {list(categories)}")
            details.append(f"Generated columns: {[name for name in new_col_names if name.startswith(col)]}")
            self._add_to_codebook(col, details)
=======
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
>>>>>>> main
