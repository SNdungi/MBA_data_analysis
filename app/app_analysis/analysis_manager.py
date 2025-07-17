# File: app/analysis_manager.py
# --- COMPLETE AND CORRECTED VERSION ---

import pandas as pd
import numpy as np
import os
import re
from flask import current_app, session
from app.app_encoder.encoder_models import Study, ColumnEncoding
from app.app_encoder.encoder_manager import EncodingConfigManager
from . import analysis_utils as utils

class AnalysisManager:

    def __init__(self, study_id: int):
        self.study = Study.query.get_or_404(study_id)
        self.session_key = f"analysis_data_{study_id}"
        self.data = self._load_data()
        if self.data is None:
            raise FileNotFoundError("Encoded data file not found for this study.")

    def _load_data(self) -> pd.DataFrame | None:
        if self.session_key in session:
            return pd.read_json(session[self.session_key], orient='split')
        base_name = self.study.map_filename.replace('.json', '')
        encoded_filename = f"{base_name}_encoded.csv"
        file_path = os.path.join(current_app.config['GENERATED_FOLDER'], encoded_filename)
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='ignore')
            session[self.session_key] = df.to_json(orient='split')
            return df
        return None

    def _save_data(self):
        session[self.session_key] = self.data.to_json(orient='split')

    def reset_data(self):
        if self.session_key in session:
            session.pop(self.session_key)

    def get_variable_types(self) -> dict:
        numeric_vars, categorical_vars = [], []
        if self.data is not None:
            for col in self.data.columns:
                is_numeric = pd.api.types.is_numeric_dtype(self.data[col])
                if is_numeric:
                    numeric_vars.append(col)
                if not is_numeric or (is_numeric and self.data[col].nunique() <= 10):
                    categorical_vars.append(col)
        return {'numeric': sorted(numeric_vars), 'categorical': sorted(categorical_vars)}

    def create_composite_variable(self, new_var_name: str, source_vars: list):
        if not new_var_name or not new_var_name.strip(): raise ValueError("New variable name cannot be empty.")
        if new_var_name in self.data.columns: raise ValueError(f"Variable '{new_var_name}' already exists.")
        if not source_vars: raise ValueError("You must select at least one source variable.")
        for var in source_vars:
            if not pd.api.types.is_numeric_dtype(self.data[var]):
                raise TypeError(f"Source variable '{var}' must be numeric.")
        self.data[new_var_name] = self.data[source_vars].mean(axis=1)
        self._save_data()
        return f"Successfully created composite variable '{new_var_name}'."

    def _apply_value_labels(self, series: pd.Series) -> pd.Series:
        column_key = series.name
        col_encoding = ColumnEncoding.query.filter_by(study_id=self.study.id, column_key=column_key).first()
        if not col_encoding or not col_encoding.encoder_definition: return series
        definition = col_encoding.encoder_definition
        prototype_type, config = definition.prototype.encoder_type, definition.configuration
        reverse_map = {}
        if prototype_type == 'Likert': reverse_map = {v: k for k, v in config.get('map', {}).items()}
        elif prototype_type == 'Ordinal': reverse_map = {i: val for i, val in enumerate(config.get('order', []))}
        elif prototype_type == 'Binary': reverse_map = {1: 'Yes/True', 0: 'No/False'}
        elif prototype_type == 'Nominal':
            raw_map = config.get('value_map', {})
            try: reverse_map = {int(k): v for k, v in raw_map.items()}
            except (ValueError, TypeError): return series
        if not reverse_map: return series
        return series.map(reverse_map).fillna(series)

    def _convert_ordinal_to_numeric(self, labeled_series: pd.Series) -> pd.Series:
        def parse_label(label_str):
            s = str(label_str)
            if match := re.search(r'(\d+)\s*-\s*(\d+)', s): return (int(match.group(1)) + int(match.group(2))) / 2
            if match := re.search(r'(?:over|greater|>|at least)\s*(\d+)', s, re.IGNORECASE): return float(match.group(1))
            if match := re.search(r'(?:under|less|<)\s*(\d+)', s, re.IGNORECASE): return float(match.group(1)) / 2
            if match := re.search(r'(\d+)', s): return float(match.group(1))
            return np.nan
        unique_labels = labeled_series.unique()
        parsed_values = {label: parse_label(label) for label in unique_labels}
        ranges = [v for v in parsed_values.values() if isinstance(v, float) and v is not None]
        avg_gap = np.mean(np.diff(sorted(list(set(ranges))))) if len(ranges) > 1 else 5
        for label, val in parsed_values.items():
            if val is not None and ('over' in str(label).lower() or '>' in str(label)): parsed_values[label] = val + (avg_gap / 2)
        return labeled_series.map(parsed_values)

    def run_ordinal_analysis(self, column: str, figure_title: str = None):
        series_numeric_codes = self.data[column].dropna()
        if series_numeric_codes.empty: raise ValueError(f"The column '{column}' contains no data.")
        series_labeled = self._apply_value_labels(series_numeric_codes)
        freq_table_html = utils.generate_frequency_table_html(series_labeled)
        
        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f"Distribution of '{column}'"
        plot_url = utils.generate_barchart(series_labeled, title=final_plot_title)

        series_for_calc = self._convert_ordinal_to_numeric(series_labeled)
        if series_for_calc.notna().sum() > 0:
            numeric_desc_df = utils.get_descriptives(series_for_calc)
            numeric_desc_html = utils.generate_styled_html_table(numeric_desc_df)
            interp_numeric = "For calculation of Mean/Median/SD, categories were automatically converted to numeric values."
        else:
            numeric_desc_html = "<p class='text-danger'>Could not automatically convert categories to numbers.</p>"
            interp_numeric = "Numeric calculations could not be performed."
        
        return {
            'title': f'Ordinal Data Analysis for {column}', 
            'stats_table_html': freq_table_html,
            'plot_url': plot_url, 
            'numeric_desc_html': numeric_desc_html,
            'figure_title': final_plot_title,
            'interpretation': f"The bar chart and frequency table show the distribution across the ordered categories. {interp_numeric}"
        }

    def run_categorical_descriptives(self, column: str, plot_type: str = 'bar', 
                                     figure_title: str = None, 
                                     bar_orientation: str = 'horizontal', 
                                     pie_style: str = 'pie',
                                     pie_explode: str = None):
        
            series = self.data[column].dropna()
            labeled_series = self._apply_value_labels(series)
            table_html = utils.generate_frequency_table_html(labeled_series)

            if plot_type == 'hist':
                final_plot_title = figure_title if figure_title else f'Histogram of {column}'
                plot_url = utils.generate_histogram(series, title=final_plot_title)
                interp_plot = "The histogram visualizes the distribution of the underlying numeric codes."

            elif plot_type == 'pie':
                final_plot_title = figure_title if figure_title else f'Pie Chart of {column}'
                # Pass the pie_style and pie_explode parameters to the utility function
                plot_url = utils.generate_piechart(
                    labeled_series, 
                    title=final_plot_title, 
                    style=pie_style, 
                    explode_label=pie_explode
                )
                interp_plot = "The pie chart shows the proportion of each distinct category."
            else: # Default to bar
                final_plot_title = figure_title if figure_title else f'Bar Chart of {column}'
                # Pass the bar_orientation parameter to the utility function
                plot_url = utils.generate_barchart(labeled_series, title=final_plot_title, orientation=bar_orientation)
                interp_plot = "The bar chart shows the frequency of each distinct category."
                
            return {
                'title': f'Categorical Analysis for {column}', 'stats_table_html': table_html,
                'plot_url': plot_url, 'figure_title': final_plot_title,
                'interpretation': f"The frequency table uses descriptive labels. {interp_plot}"
            }
        

    def run_descriptive_analysis(self, column: str, figure_title: str = None):
        series = self.data[column].dropna()
        # Step 1: Get the data
        stats_df = utils.get_descriptives(series)
        # Step 2: Generate the styled HTML from the data
        stats_table_html = utils.generate_styled_html_table(stats_df)
        
        final_plot_title = figure_title if figure_title else f'Distribution of {column}'
        plot_url = utils.generate_histogram(series, title=final_plot_title)
        
        return {
            'title': f'Descriptive Statistics for {column}',
            'stats_table_html': stats_table_html, # Use the new styled HTML
            'plot_url': plot_url,
            'figure_title': final_plot_title,
            'interpretation': f"The table shows key statistical metrics for the variable '{column}'. The histogram visualizes its distribution."
        }
    def run_multi_category_descriptives(self, column: str, figure_title: str = None):
        """
        Runs descriptive analysis for a multi-select (comma-separated) column.
        Data cleaning now happens once in this method.
        """
        series = self.data[column].dropna()
        if series.empty:
            raise ValueError(f"The column '{column}' contains no data.")

        # --- FIX 2: CENTRALIZED DATA PREPARATION ---
        # 1. Split, explode, trim, and filter the data ONCE.
        cleaned_items_series = series.str.split(',').explode().str.strip()
        cleaned_items_series = cleaned_items_series[cleaned_items_series != '']
        
        if cleaned_items_series.empty:
            raise ValueError(f"The column '{column}' contains no valid items after processing.")

        # 2. Pass the CLEANED series to the table generator.
        table_html = utils.generate_multicategory_frequency_table(cleaned_items_series)

        # 3. Pass the EXACT SAME CLEANED series to the plot generator.
        final_plot_title = figure_title if figure_title else f'Frequencies of Items in {column}'
        plot_url = utils.generate_barchart(cleaned_items_series, title=final_plot_title)

        return {
            'title': f'Multi-Category Analysis for {column}',
            'stats_table_html': table_html,
            'plot_url': plot_url,
            'figure_title': final_plot_title,
            'interpretation': (
                "The table and chart show the frequency of each individual item chosen in this 'select all that apply' question. "
                "Percentages are now calculated based on the **total number of selections made**, so they will sum to 100%."
            )
        }
    
    def run_comparative_multi_category(self, var1_key: str, var2_key: str, figure_title: str = None):
        """
        Runs a comparative analysis between two multi-category columns.
        """
        series1 = self.data[var1_key].dropna()
        series2 = self.data[var2_key].dropna()

        if series1.empty or series2.empty:
            raise ValueError("One or both selected columns contain no data.")

        # --- Generate the Combined Table ---
        combined_table_html = utils.generate_combined_frequency_table(series1, series2)
        V1="Brand Category"
        v2="Brands"
        title = "Brand Portfolio"
        # --- Generate the Dual Bar Chart ---
        final_plot_title = figure_title if figure_title else f"Frequency Comparison: {var1_key} vs. {var2_key}"
        plot_url = utils.generate_dual_barchart(series1, series2, title1=var1_key, title2=var2_key)

        return {
            'title': f'Comparative Analysis: {var1_key} and {var2_key}',
            'stats_table_html': combined_table_html, # Re-using this key for the combined table
            'plot_url': plot_url,
            'figure_title': final_plot_title,
            'interpretation': (
                f"The table and figure below provide a side-by-side comparison of the frequencies for items selected in '{var1_key}' and '{var2_key}'. "
                "The table allows for direct comparison of counts for shared items, while the dual bar chart provides a clear visual representation of the distribution for each variable independently."
            )
        }

    def run_multi_descriptives(self, columns: list):
        if not columns:
            raise ValueError("Please select at least one variable.")
        # Step 1: Get the data
        stats_df = utils.get_descriptives_for_multiple(self.data, columns)
        # Step 2: Generate the styled HTML from the data
        stats_table_html = utils.generate_styled_html_table(stats_df)
        
        return {
            'title': 'Descriptive Statistics for Selected Variables',
            'stats_table_html': stats_table_html, # Use the new styled HTML
            'interpretation': "This table summarizes key statistics for the selected variables."
        }
    
    def run_descriptive_ranking(self, columns: list):
        """
        Orchestrates a descriptive ranking analysis and formats the output table.
        """
        if not columns:
            raise ValueError("Please select at least one variable for ranking.")

        # 1. Perform the core statistical analysis
        ranked_df = utils.perform_descriptive_ranking(self.data, columns)

        # 2. Get the full question text for each column key
        enc_manager = EncodingConfigManager()
        column_map = enc_manager.get_column_map(self.study.id)
        
        # Add the full "Statement" text to the DataFrame
        ranked_df['Statement'] = ranked_df.index.map(column_map)
        
        # Make the Statement the first column for better readability
        ranked_df = ranked_df.reset_index().rename(columns={'index': 'Variable'})
        final_cols = ['Statement', 'Variable', 'N', 'Mean', 'Std Dev', 'CV', 'Ranking']
        ranked_df = ranked_df[final_cols]

        # 3. Format the numbers for presentation
        # We can't use style.format here as it returns a Styler object, not a DataFrame
        # So we'll apply string formatting directly.
        for col in ['Mean', 'Std Dev', 'CV']:
            ranked_df[col] = ranked_df[col].apply(lambda x: f'{x:.2f}')
        
        # 4. Generate the final styled HTML table
        # We'll tell it to wrap the long 'Statement' column
        final_table_html = utils.generate_styled_html_table(ranked_df, wrap_column='Statement')

        return {
            'title': 'Descriptive Ranking Analysis by Consensus (Coefficient of Variation)',
            'stats_table_html': final_table_html,
            'interpretation': (
                "This table ranks the selected items based on the level of consensus among respondents. The 'Ranking' is determined by the "
                "Coefficient of Variation (CV), calculated as (Standard Deviation / Mean). A lower CV indicates less relative variability and therefore "
                "stronger consensus. The item ranked #1 is the statement that respondents agreed on the most, regardless of whether the "
                "mean score was high or low."
            )
        }
        
    def run_anova(self, dependent: str, independent: str, figure_title: str = None):
        if not pd.api.types.is_numeric_dtype(self.data[dependent]): raise TypeError("ANOVA dependent variable must be numeric.")
        f_val, p_val = utils.perform_anova(self.data, dependent, independent)
        df_for_plot = self.data.copy()
        df_for_plot[independent] = self._apply_value_labels(df_for_plot[independent])
        
        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f'Boxplot of {dependent} by {independent}'
        plot_url = utils.generate_boxplot(df_for_plot, independent, dependent, title=final_plot_title)
        
        interp = (f"The one-way ANOVA test compared means of '{dependent}' across groups of '{independent}'. Result: F={f_val:.2f}, p={p_val:.4f}.")
        return {
            'title': f'ANOVA: {dependent} vs. {independent}',
            'stats_table_html': pd.DataFrame([{'F-statistic': f'{f_val:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url, 'figure_title': final_plot_title,
            'interpretation': interp
        }

    def run_ttest(self, continuous: str, group: str, figure_title: str = None):
        if not pd.api.types.is_numeric_dtype(self.data[continuous]): raise TypeError("T-test continuous variable must be numeric.")
        t_stat, p_val, groups = utils.perform_ttest_ind(self.data, continuous, group)
        df_for_plot = self.data.copy()
        df_for_plot[group] = self._apply_value_labels(df_for_plot[group])

        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f'Boxplot of {continuous} by {group}'
        plot_url = utils.generate_boxplot(df_for_plot, group, continuous, title=final_plot_title)
        
        interp = (f"An independent samples T-test compared means of '{continuous}' for two groups. Result: T={t_stat:.2f}, p={p_val:.4f}.")
        return {
            'title': f'T-Test: {continuous} vs. {group}',
            'stats_table_html': pd.DataFrame([{'T-statistic': f'{t_stat:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url, 'figure_title': final_plot_title,
            'interpretation': interp
        }

    def run_correlation(self, var1: str, var2: str, figure_title: str = None):
        if not pd.api.types.is_numeric_dtype(self.data[var1]) or not pd.api.types.is_numeric_dtype(self.data[var2]):
            raise TypeError("Both variables for correlation must be numeric.")
        r, p_val = utils.perform_pearson_correlation(self.data[var1], self.data[var2])

        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f'Scatter Plot of {var1} vs. {var2}'
        plot_url = utils.generate_scatterplot(self.data, var1, var2, title=final_plot_title)

        interp = (f"A Pearson correlation was run between '{var1}' and '{var2}'. Result: r = {r:.3f}, p = {p_val:.4f}.")
        return {
            'title': f'Correlation: {var1} vs. {var2}',
            'stats_table_html': pd.DataFrame([{'Pearson r': f'{r:.3f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url, 'figure_title': final_plot_title,
            'interpretation': interp
        }

    def run_chi_squared(self, var1: str, var2: str, figure_title: str = None):
        labeled_var1, labeled_var2 = self._apply_value_labels(self.data[var1]), self._apply_value_labels(self.data[var2])
        labeled_df = pd.DataFrame({var1: labeled_var1, var2: labeled_var2})
        chi2, p, dof, table = utils.perform_chi_squared(labeled_df, var1, var2)
        
        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f'Heatmap of {var1} vs. {var2}'
        plot_url = utils.generate_heatmap(table, title=final_plot_title)

        enhanced_crosstab_html = utils.generate_enhanced_crosstab(table)
        interp = (f"A Chi-Squared test for independence between '{var1}' and '{var2}' yielded a Chi-Squared value of {chi2:.2f} with {dof} df and p={p:.4f}.")
        return {
            'title': f'Chi-Squared Test: {var1} vs. {var2}',
            'stats_table_html': pd.DataFrame([{'Chi-Squared': f'{chi2:.2f}', 'p-value': f'{p:.4f}', 'df': dof}]).to_html(classes='table table-sm', index=False),
            'enhanced_crosstab_html': enhanced_crosstab_html,
            'plot_url': plot_url, 'figure_title': final_plot_title,
            'interpretation': interp
        }

    def run_comparison_plot(self, column_key: str, figure_title: str = None):
        enc_manager = EncodingConfigManager()
        column_map = enc_manager.get_column_map(self.study.id)
        original_col_name = column_map.get(column_key)
        if not original_col_name: raise ValueError(f"Could not find original question text for key '{column_key}'.")
        base_name = self.study.map_filename.replace('.json', '')
        original_csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv")
        simulated_csv_path = os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv")
        if not os.path.exists(simulated_csv_path): raise FileNotFoundError("Simulated data file not found.")
        raw_original_series = pd.read_csv(original_csv_path, usecols=[original_col_name], encoding='latin1')[original_col_name]
        raw_simulated_series = pd.read_csv(simulated_csv_path, usecols=[column_key], encoding='latin1')[column_key]
        col_encoding = ColumnEncoding.query.filter_by(study_id=self.study.id, column_key=column_key).first()
        if not col_encoding or not col_encoding.encoder_definition: raise ValueError(f"No encoder definition assigned to '{column_key}'.")
        definition = col_encoding.encoder_definition
        encoded_original, encoded_simulated = self._encode_series(raw_original_series, definition).dropna(), self._encode_series(raw_simulated_series, definition).dropna()
        if encoded_original.empty or encoded_simulated.empty: raise ValueError("After encoding, one or both data series are empty.")
        
        # FIX: Decide the title BEFORE generating the plot
        final_plot_title = figure_title if figure_title else f"Original vs. Simulated Distribution for {column_key}"
        plot_url = utils.generate_comparison_kde_plot(encoded_original, encoded_simulated, title=final_plot_title, series1_name='Original', series2_name='Simulated')
        
        return {
            'title': f"Original vs. Simulated Distribution for {column_key}", 'plot_url': plot_url,
            'figure_title': final_plot_title,
            'interpretation': f"This plot compares the encoded values for '{original_col_name}'. A close match indicates the simulation preserved the original distribution."
        }

    # Helper and non-plotting methods
    def _encode_series(self, raw_series: pd.Series, definition):
        encoder_type, config = definition.prototype.encoder_type, definition.configuration
        def _normalize_text(text):
            if not isinstance(text, str): text = str(text)
            return re.sub(r'\s+', ' ', text).strip().lower()
        if encoder_type == 'Likert': return raw_series.apply(_normalize_text).map({_normalize_text(k): v for k, v in config.get('map', {}).items()})
        elif encoder_type == 'Ordinal': return raw_series.apply(_normalize_text).map({_normalize_text(k): v for k, v in {val: i for i, val in enumerate(config.get('order', []))}.items()})
        elif encoder_type == 'Binary': return raw_series.apply(_normalize_text).map(lambda x: 1 if x in ['yes', 'true', '1', 'y'] else 0)
        elif encoder_type == 'Nominal (Factorized)': return pd.factorize(raw_series)[0]
        return raw_series
    
    def run_multi_descriptives(self, columns: list):
        if not columns: raise ValueError("Please select at least one variable.")
        stats_table = utils.get_descriptives_for_multiple(self.data, columns)
        return {'title': 'Descriptive Statistics for Selected Variables', 
                'stats_table_html': stats_table.to_html(classes='table table-sm table-striped', index=False, border=0), 
                'interpretation': "This table summarizes key statistics for the selected variables."}
    
    def run_one_sample_ttest(self, column: str, popmean: float):
        if not pd.api.types.is_numeric_dtype(self.data[column]): raise TypeError("Variable must be numeric.")
        t_stat, p_val = utils.perform_one_sample_ttest(self.data[column], popmean)
        interp = (f"A one-sample t-test was run to determine if the mean of '{column}' was different from {popmean}. Result: t={t_stat:.2f}, p={p_val:.4f}.")
        return {'title': f'One-Sample T-Test for {column}', 
                'stats_table_html': pd.DataFrame([{'Test Value': popmean, 'T-statistic': f'{t_stat:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False), 
                'interpretation': interp}