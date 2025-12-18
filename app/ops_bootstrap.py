# File: app/ops_bootstrap.py
import pandas as pd
import numpy as np
import json
import io

import os
from typing import Optional, Dict

class DataBootstrapper:
    """
    A class to perform bootstrap resampling on data.
    It can automatically generate a question map from a CSV's headers if one is not found.
    """

    def __init__(self, file_path: str, map_path: str, encoding: str = 'utf-8'):
        self.file_path = file_path
        self.map_path = map_path
        self.encoding = encoding
        self.original_df: Optional[pd.DataFrame] = None
        self.simulated_df: Optional[pd.DataFrame] = None
        self.question_map: Dict[str, str] = {}
        if os.path.exists(self.map_path):
            self._load_question_map()
        else:
            self._create_and_load_map()
        self.load_data()

    def _load_question_map(self):
        print(f"--- Found existing question map. Loading from '{self.map_path}'... ---")
        try:
            with open(self.map_path, 'r', encoding='utf-8') as f:
                self.question_map = json.load(f)
            print("✅ Successfully loaded question map.")
        except json.JSONDecodeError:
            print(f"❌ Error: Could not decode JSON from '{self.map_path}'. File may be corrupt.")
            raise

    def _create_and_load_map(self):
        print(f"--- Question map not found at '{self.map_path}'. Generating new map... ---")
        try:
            original_headers = pd.read_csv(self.file_path, encoding=self.encoding, nrows=0).columns.tolist()
            new_map = {f"{i+1}": header for i, header in enumerate(original_headers)}
            with open(self.map_path, 'w', encoding='utf-8') as f:
                json.dump(new_map, f, indent=2)
            self.question_map = new_map
            print(f"✅ Successfully created and saved new question map to '{self.map_path}'.")
        except Exception as e:
            print(f"❌ Failed to create question map. Error: {e}")
            raise

    def load_data(self):
        try:
            self.original_df = pd.read_csv(self.file_path, encoding=self.encoding)
            if self.question_map:
                rename_dict = {v: k for k, v in self.question_map.items()}
                self.original_df.rename(columns=rename_dict, inplace=True)
                print("✅ Successfully loaded and standardized data columns.")
            print(f"   Original dataset has {len(self.original_df)} rows and {len(self.original_df.columns)} columns.")
        except Exception as e:
            print(f"❌ An error occurred during data loading: {e}")
            raise

    def get_question_text(self, column_name: str) -> str:
        return self.question_map.get(column_name, column_name)

    def bootstrap(self, new_size: int, random_state: Optional[int] = None) -> pd.DataFrame:
        """Performs a standard bootstrap, resampling full rows."""
        if self.original_df is None:
            raise ValueError("Original data not loaded.")
        print("\n🔄 Performing standard bootstrap...")
        self.simulated_df = self.original_df.sample(n=new_size, replace=True, ignore_index=True, random_state=random_state)
        print("✅ Standard bootstrap complete.")
        return self.simulated_df

    def bootstrap_remix(self,
                        new_size: int,
                        start_remix_col: str,
                        end_remix_col: str,
                        random_state: Optional[int] = None) -> pd.DataFrame:
        """Performs a 'remix' bootstrap on a slice of columns."""
        if self.original_df is None: raise ValueError("Original data not loaded.")
        if not self.question_map: raise ValueError("Question map (JSON) not loaded.")

        print("\n🔄 Performing REMIX bootstrap on a slice...")
        
        all_cols = list(self.question_map.keys())
        try:
            start_index = all_cols.index(start_remix_col)
            end_index = all_cols.index(end_remix_col)
        except ValueError as e:
            raise ValueError(f"A specified start/end column was not found in the question map keys. Details: {e}")
        
        if start_index > end_index:
            raise ValueError("The 'start' remix column must come before the 'end' column.")

        remix_cols = all_cols[start_index : end_index + 1]
        fixed_cols = all_cols[:start_index] + all_cols[end_index + 1:]
        
        print(f"   - Identified fixed columns: {fixed_cols}")
        print(f"   - Identified remixed columns (from '{start_remix_col}' to '{end_remix_col}'): {remix_cols}")
        
        if random_state: np.random.seed(random_state)
        
        if fixed_cols:
            fixed_part = self.original_df[fixed_cols].sample(n=new_size, replace=True, random_state=random_state)
        else:
            fixed_part = pd.DataFrame()

        random_part = self.original_df[remix_cols].sample(n=new_size, replace=True, random_state=random_state)
        
        self.simulated_df = pd.concat([fixed_part.reset_index(drop=True), random_part.reset_index(drop=True)], axis=1)
        self.simulated_df = self.simulated_df[all_cols]
        print("✅ Remix bootstrap complete.")
        return self.simulated_df

    # =============================================================================
    # NEW DEEP REMIX SAMPLER
    # =============================================================================
    def bootstrap_deep_remix(self, new_size: int, random_state: Optional[int] = None) -> pd.DataFrame:
        """
        Performs a 'deep remix' bootstrap, shuffling each column independently
        to create completely new, decorrelated rows.
        """
        if self.original_df is None:
            raise ValueError("Original data not loaded.")

        print("\n🔄 Performing DEEP REMIX (cell-level) bootstrap...")
        
        new_data = {}
        
        rng = np.random.default_rng(random_state)
        num_cols = len(self.original_df.columns)
        column_seeds = rng.integers(low=0, high=10**6, size=num_cols)
        
        for i, col in enumerate(self.original_df.columns):
            # Sample `new_size` values from the current column, with replacement.
            # Use the unique seed generated for this specific column.
            col_seed = column_seeds[i]
            new_data[col] = self.original_df[col].sample(
                n=new_size, 
                replace=True, 
                random_state=col_seed, 
                ignore_index=True)
        
        self.simulated_df = pd.DataFrame(new_data)
        print("✅ Deep Remix bootstrap complete.")
        return self.simulated_df


    def save_simulated_data(self, output_path: str):
        if self.simulated_df is None:
            raise ValueError("No simulated data to save.")
        self.simulated_df.to_csv(output_path, index=False)
        print(f"\n💾 Simulated data successfully saved to '{output_path}'.")
        
    def get_result_as_csv_string(self):
        """Returns the simulated dataframe as a CSV string."""
        if self.simulated_df is None:
            raise ValueError("No simulation data found. Run bootstrap() first.")
        
        buffer = io.StringIO()
        self.simulated_df.to_csv(buffer, index=False)
        return buffer.getvalue()