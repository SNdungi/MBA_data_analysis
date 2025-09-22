# File: app/analysis_manager.py
# --- COMPLETE AND CORRECTED VERSION ---

from typing import Optional
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
        # The session key now points to a list of operations, not the dataframe
        self.ops_session_key = f"analysis_ops_{study_id}"
        self.data = self._load_and_process_data()
        if self.data is None:
            raise FileNotFoundError("Encoded data file not found for this study.")

    def _load_and_process_data(self) -> Optional[pd.DataFrame]:
        """
        Loads the base encoded data from the CSV file and then applies any
        user-defined operations (like creating composite variables) from the session.
        """
        base_name = self.study.map_filename.replace('.json', '')
        encoded_filename = f"{base_name}_encoded.csv"
        file_path = os.path.join(current_app.config['GENERATED_FOLDER'], encoded_filename)
        
        if not os.path.exists(file_path):
            return None

        # 1. Load the base DataFrame from the CSV every time
        df = pd.read_csv(file_path)
        # Fix for FutureWarning and ensures numeric types
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                # This column is not numeric, which is fine
                pass

        # 2. Get the list of operations from the session
        operations = session.get(self.ops_session_key, [])
        
        # 3. Re-apply each operation to the DataFrame
        for op in operations:
            if op.get('type') == 'create_composite':
                name = op.get('name')
                sources = op.get('sources')
                if name and sources and all(s in df.columns for s in sources):
                    df[name] = df[sources].mean(axis=1)
        
        return df

    def reset_data(self):
        """Resets the data by simply clearing the operations from the session."""
        if self.ops_session_key in session:
            session.pop(self.ops_session_key)

    def create_composite_variable(self, new_var_name: str, source_vars: list):
        """
        Creates a new composite variable by adding an 'operation' to the session,
        NOT by saving the entire DataFrame.
        """
        if not new_var_name or not new_var_name.strip():
            raise ValueError("New variable name cannot be empty.")
        if new_var_name in self.data.columns: # self.data is already processed
            raise ValueError(f"Variable '{new_var_name}' already exists.")
        if not source_vars:
            raise ValueError("You must select at least one source variable.")
        
        # Get the current list of operations, or an empty list if none exists
        operations = session.get(self.ops_session_key, [])
        
        # Define the new operation
        new_op = {
            'type': 'create_composite',
            'name': new_var_name,
            'sources': source_vars
        }
        
        # Add the new operation to the list
        operations.append(new_op)
        
        # Save the updated list of operations back to the session.
        # This keeps the session cookie very small.
        session[self.ops_session_key] = operations
        
        return f"Successfully created composite variable '{new_var_name}'."
    
    # --- ALL OTHER METHODS (get_variable_types, _apply_value_labels, all run_* methods) ARE UNCHANGED ---
    # They will now operate on the `self.data` DataFrame which is correctly
    # loaded and processed by the new `_load_and_process_data` method on initialization.
    def get_variable_types(self) -> dict:
        numeric_vars = []
        categorical_vars = []
        if self.data is not None:
            for col in self.data.columns:
                is_numeric = pd.api.types.is_numeric_dtype(self.data[col])
                if is_numeric:
                    numeric_vars.append(col)
                if not is_numeric or (is_numeric and self.data[col].nunique() <= 10):
                    categorical_vars.append(col)
        return {'numeric': sorted(numeric_vars), 'categorical': sorted(categorical_vars)}

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
        elif prototype_type == 'Nominal (Factorized)':
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
        
    def run_cronbach_alpha(self, columns: list):
        """
        Orchestrates a Cronbach's Alpha reliability test and formats the output.
        """
        # 1. Perform the core statistical analysis
        alpha_df = utils.calculate_cronbach_alpha(self.data, columns)       
        # 2. Generate the styled HTML table
        alpha_table_html = utils.generate_styled_html_table(alpha_df)
        # 3. Provide a standard interpretation guide
        interpretation = """
        <p>Cronbach's Alpha is a measure of internal consistency (reliability) for a set of scale items. It is not a measure of unidimensionality.</p>
        <strong>General Rules of Thumb for Interpretation:</strong>
        <ul>
            <li><strong>α > 0.9:</strong> Excellent</li>
            <li><strong>0.8 < α ≤ 0.9:</strong> Good</li>
            <li><strong>0.7 < α ≤ 0.8:</strong> Acceptable</li>
            <li><strong>0.6 < α ≤ 0.7:</strong> Questionable</li>
            <li><strong>0.5 < α ≤ 0.6:</strong> Poor</li>
            <li><strong>α < 0.5:</strong> Unacceptable</li>
        </ul>
        <p>A high alpha suggests that the items in your scale are reliably measuring the same underlying latent construct.</p>
        """

        return {
            'title': "Cronbach's Alpha Reliability Analysis",
            'stats_table_html': alpha_table_html,
            'interpretation': interpretation
        }
    def run_bivariate_correlation(self, x_vars: list, y_var: str):
        """
        Orchestrates a bivariate correlation analysis and formats the output table.
        """
        # 1. Perform the core statistical analysis
        results_df = utils.perform_bivariate_correlations(self.data, x_vars, y_var)

        # 2. Get the full question text for each variable key to make the table readable
        enc_manager = EncodingConfigManager()
        column_map = enc_manager.get_column_map(self.study.id)
        
        # Replace the short keys with the full question "Statement"
        results_df['Independent Variable'] = results_df['Independent Variable'].map(column_map)
        
        # Format the numeric columns for presentation
        results_df['Pearson r'] = pd.to_numeric(results_df['Pearson r'], errors='coerce').map('{:.3f}'.format)
        results_df['p-value'] = pd.to_numeric(results_df['p-value'], errors='coerce').map('{:.4f}'.format)
        
        # 3. Generate the final styled HTML table
        final_table_html = utils.generate_styled_html_table(results_df, wrap_column='Independent Variable')

        y_var_text = column_map.get(y_var, y_var)

        return {
            'title': f"Bivariate Correlations with '{y_var_text}'",
            'stats_table_html': final_table_html,
            'interpretation': (
                f"This table shows the results of Pearson correlations between several independent variables and the single dependent variable: '{y_var_text}'. "
                "The 'Pearson r' value indicates the strength and direction of the linear relationship (-1 to +1). "
                "The 'Significance' column indicates if the relationship is statistically significant (typically p < .05). "
                "This analysis is useful for examining the individual impact of several factors on a single outcome."
            )
        }


    def run_linear_regression(self, x_vars: list, y_var: str):
        """
        Orchestrates a linear regression analysis and provides interpretation
        based on the new SPSS-style output.
        """
        enc_manager = EncodingConfigManager()
        column_map = enc_manager.get_column_map(self.study.id)

        # Create a temporary dataframe with readable names for the table
        df_for_reg = self.data.rename(columns=column_map)
        
        x_vars_full = [column_map.get(v, v) for v in x_vars]
        y_var_full = column_map.get(y_var, y_var)
        
        # 1. Perform the core statistical analysis
        regression_results = utils.perform_linear_regression(df_for_reg, x_vars_full, y_var_full)

        # 2. Provide a detailed interpretation guide
        f_pvalue_num = float(regression_results['f_pvalue'])
        adj_r_sq_num = float(regression_results['adj_r_squared'])
        
        model_sig_text = "statistically significant" if f_pvalue_num < 0.05 else "not statistically significant"

        interpretation = f"""
        <p>A multiple linear regression was run to predict <strong>{y_var_full}</strong> from the predictor variables.</p>
        <p>The overall regression model was <strong>{model_sig_text}</strong> (p = {f_pvalue_num:.3f}), explaining <strong>{adj_r_sq_num*100:.1f}%</strong> of the variance in the outcome (Adjusted R² = {adj_r_sq_num:.3f}).</p>
        <strong>Coefficients Table Interpretation:</strong>
        <ul>
            <li><strong>B (Unstandardized Coefficient):</strong> For a one-unit increase in the predictor, the outcome is predicted to change by this amount, holding other predictors constant.</li>
            <li><strong>Sig. (p-value):</strong> If this value is less than 0.05, the predictor is considered to have a statistically significant unique contribution to the model.</li>
        </ul>
        """

        return {
            'title': f'Linear Regression Predicting "{y_var_full}"',
            'model_summary_table': regression_results['model_summary_table'],
            'anova_table': regression_results['anova_table'],
            'coeffs_table': regression_results['coeffs_table'],
            'interpretation': interpretation
        }
        

    # --- NEW METHOD ---
    def run_correlation_matrix(self, row_vars: list, col_vars: list):
        """
        Orchestrates the generation of an SPSS-style correlation matrix.
        """
        # 1. Generate the styled HTML table
        # We need to replace the short keys with full text for the final table.
        enc_manager = EncodingConfigManager()
        column_map = enc_manager.get_column_map(self.study.id)
        
        # Create a temporary dataframe with readable names for the function
        df_for_corr = self.data.rename(columns=column_map)
        
        # Map the selected short keys to their full text names
        row_vars_full = [column_map.get(v, v) for v in row_vars]
        col_vars_full = [column_map.get(v, v) for v in col_vars]
        
        matrix_html = utils.generate_spss_correlation_matrix(df_for_corr, row_vars_full, col_vars_full)

        return {
            'title': 'Pearson Correlation Matrix',
            'stats_table_html': matrix_html, # Re-use the stats_table_html key
            'interpretation': (
                "The table displays the Pearson correlation coefficient (r), the p-value (Sig. 2-tailed), and the sample size (N) for each pair of variables. "
                "The asterisks indicate the level of statistical significance, which shows whether the observed relationship is likely due to chance. "
                "This format is standard for reporting correlations in academic research."
            )
        }
    


    # === THIS IS THE CORRECTED AND FINAL METHOD ===
    def run_likert_distribution_chart(self, columns: list, figure_title: str = None):
        """
        Prepares data for a diverging stacked bar chart, using short keys on the
        y-axis and providing a full question map for a detailed legend.
        """
        if not columns:
            raise ValueError("Please select at least one variable.")
        
        likert_df = self.data[columns]
        
        first_col_encoding = ColumnEncoding.query.filter_by(study_id=self.study.id, column_key=columns[0]).first()
        if not first_col_encoding or not first_col_encoding.encoder_definition:
            raise ValueError(f"Could not find a valid encoder definition for '{columns[0]}'.")
        
        raw_map = first_col_encoding.encoder_definition.configuration.get('map', {})
        if not raw_map:
             raise ValueError(f"The encoder definition for '{columns[0]}' does not contain a valid 'map'.")

        sorted_items = sorted(raw_map.items(), key=lambda item: item[1])
        category_order = [str(item[0]) for item in sorted_items]

        freq_data = []
        for col in likert_df.columns:
            counts = self._apply_value_labels(likert_df[col]).value_counts(normalize=True) * 100
            freq_data.append(counts)
        
        freq_df = pd.DataFrame(freq_data, index=columns)
        freq_df = freq_df.reindex(columns=category_order, fill_value=0)
        
        # --- KEY CHANGE: Do NOT replace the index with full text ---
        # The index should remain as the short keys ('q30', 'q31', etc.) for the plot y-axis.
        
        # 1. Get the full question map
        enc_manager = EncodingConfigManager()
        full_column_map = enc_manager.get_column_map(self.study.id)
        
        # 2. Create a specific map only for the questions being plotted
        legend_question_map = {key: full_column_map.get(key, "N/A") for key in columns}
        
        # 3. For the HTML table, we still want the full text.
        table_df = freq_df.copy()
        table_df['Statement'] = table_df.index.map(full_column_map)
        table_df = table_df.set_index('Statement')
        table_df = table_df.round(1).reset_index()
        table_html = utils.generate_styled_html_table(table_df, wrap_column='Statement')

        # --- Generate Plot ---
        final_plot_title = figure_title if figure_title else "Distribution of Responses for Likert Scale Items"
        # Pass both the data (indexed by short keys) and the new legend map to the plotter
        plot_url = utils.generate_diverging_stacked_bar(freq_df, title=final_plot_title)

        return {
            'title': 'Likert Scale Distribution Analysis',
            'stats_table_html': table_html,
            'plot_url': plot_url,
            'figure_title': final_plot_title, # This can now be the caption for the whole figure
            'interpretation': "..."
        }