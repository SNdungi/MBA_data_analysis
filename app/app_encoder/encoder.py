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