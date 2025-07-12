# --- START OF FILE analysis_manager.py ---

import pandas as pd
import os
from flask import current_app, session
from app.app_encoder.encoder_models import Study
from . import analysis_utils as utils

class AnalysisManager:

    def __init__(self, study_id: int):
        self.study = Study.query.get_or_404(study_id)
        self.session_key = f"analysis_data_{study_id}"
        self.data = self._load_data()
        if self.data is None:
            raise FileNotFoundError("Encoded data file not found for this study.")
            
    def _load_data(self) -> pd.DataFrame | None:
        """
        Loads data. Tries to get session-modified data first, 
        otherwise loads from the original file.
        """
        if self.session_key in session:
            return pd.read_json(session[self.session_key], orient='split')

        base_name = self.study.map_filename.replace('.json', '')
        encoded_filename = f"{base_name}_encoded.csv"
        file_path = os.path.join(current_app.config['GENERATED_FOLDER'], encoded_filename)
        
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            # Ensure proper numeric conversion for calculations
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='ignore')
            # Store initial data in session
            session[self.session_key] = df.to_json(orient='split')
            return df
        return None
    
    def _save_data(self):
        """Saves the current state of the dataframe to the session."""
        session[self.session_key] = self.data.to_json(orient='split')

    def reset_data(self):
        """Resets the data to its original state by clearing the session key."""
        if self.session_key in session:
            session.pop(self.session_key)

    def get_variable_types(self) -> dict:
        """
        Categorizes variables based on their data type and statistical role.
        """
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

    def create_composite_variable(self, new_var_name: str, source_vars: list):
        """Creates a new variable by averaging source variables and saves it."""
        if not new_var_name or not new_var_name.strip():
            raise ValueError("New variable name cannot be empty.")
        if new_var_name in self.data.columns:
            raise ValueError(f"Variable '{new_var_name}' already exists.")
        if not source_vars:
            raise ValueError("You must select at least one source variable.")
        
        # Ensure all source variables are numeric
        for var in source_vars:
            if not pd.api.types.is_numeric_dtype(self.data[var]):
                raise TypeError(f"Source variable '{var}' must be numeric to be included in a composite score.")

        self.data[new_var_name] = self.data[source_vars].mean(axis=1)
        self._save_data() # Persist the new column
        return f"Successfully created composite variable '{new_var_name}'."

    def run_categorical_descriptives(self, column: str):
        """Runs descriptive analysis on a single categorical column."""
        series = self.data[column].dropna()
        table_html = utils.generate_frequency_table_html(series)
        plot_url = utils.generate_barchart(series, title=f'Frequency of {column}')
        
        return {
            'title': f'Categorical Analysis for {column}',
            'stats_table_html': table_html,
            'plot_url': plot_url,
            'interpretation': f"The table and bar chart show the frequency distribution for each category in the '{column}' variable."
        }
        
    def run_multi_descriptives(self, columns: list):
        """Runs descriptive analysis on multiple numeric columns."""
        if not columns:
            raise ValueError("Please select at least one variable.")
        stats_table = utils.get_descriptives_for_multiple(self.data, columns)
        
        return {
            'title': 'Descriptive Statistics for Selected Variables',
            'stats_table_html': stats_table.to_html(classes='table table-sm table-striped', index=False, border=0),
            'interpretation': "The table summarizes key statistics (N, Mean, Std. Dev., Min, Max) for the selected variables, providing a quick overview of their central tendency and dispersion."
        }

    def run_correlation(self, var1: str, var2: str):
        """Runs Pearson correlation between two numeric variables."""
        if not pd.api.types.is_numeric_dtype(self.data[var1]) or not pd.api.types.is_numeric_dtype(self.data[var2]):
            raise TypeError("Both variables for correlation analysis must be numeric.")
            
        r, p_val = utils.perform_pearson_correlation(self.data[var1], self.data[var2])
        plot_url = utils.generate_scatterplot(self.data, var1, var2, f'Scatter Plot of {var1} vs. {var2}')
        
        interp = (f"A Pearson correlation was run to determine the relationship between '{var1}' and '{var2}'. "
                  f"The correlation coefficient (r) is {r:.3f} with a p-value of {p_val:.4f}. "
                  "This indicates the strength and direction of the linear relationship. A p-value < 0.05 suggests the correlation is statistically significant. "
                  "Remember, correlation does not imply causation.")
                  
        return {
            'title': f'Correlation: {var1} vs. {var2}',
            'stats_table_html': pd.DataFrame([{'Pearson r': f'{r:.3f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url,
            'interpretation': interp
        }

    def run_one_sample_ttest(self, column: str, popmean: float):
        """Runs a one-sample T-test."""
        if not pd.api.types.is_numeric_dtype(self.data[column]):
            raise TypeError(f"Variable '{column}' must be numeric for a one-sample t-test.")
        
        t_stat, p_val = utils.perform_one_sample_ttest(self.data[column], popmean)
        
        interp = (f"A one-sample t-test was conducted to determine whether the mean of '{column}' was different from the test value of {popmean}. "
                  f"The result, t = {t_stat:.2f}, p = {p_val:.4f}, suggests that "
                  f"{'there is a' if p_val < 0.05 else 'there is not a'} statistically significant difference between the sample mean and {popmean}.")

        return {
            'title': f'One-Sample T-Test for {column}',
            'stats_table_html': pd.DataFrame([{'Test Value': popmean, 'T-statistic': f'{t_stat:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'interpretation': interp
        }
        
    # --- Existing methods (run_descriptive_analysis, run_anova, run_ttest, run_chi_squared) are assumed to be here and are correct. ---
    # For completeness, here they are again.

    def run_descriptive_analysis(self, column: str):
        """Runs descriptive analysis on a single NUMERIC column."""
        series = self.data[column].dropna()
        stats_table = utils.get_descriptives(series)
        plot_url = utils.generate_histogram(series, title=f'Distribution of {column}')
        
        return {
            'title': f'Descriptive Statistics for {column}',
            'stats_table_html': stats_table.to_html(classes='table table-sm table-striped', index=False, border=0),
            'plot_url': plot_url,
            'interpretation': f"The table shows key statistical metrics for the variable '{column}'. The histogram visualizes its distribution."
        }

    def run_anova(self, dependent: str, independent: str):
        """Runs ANOVA and generates a boxplot."""
        if not pd.api.types.is_numeric_dtype(self.data[dependent]):
            raise TypeError(f"ANOVA dependent variable '{dependent}' must be numeric.")

        f_val, p_val = utils.perform_anova(self.data, dependent, independent)
        plot_url = utils.generate_boxplot(self.data, independent, dependent, f'Boxplot of {dependent} by {independent}')
        
        interp = (f"The one-way ANOVA test was conducted to compare the means of '{dependent}' across the different groups of '{independent}'. "
                  f"The result shows an F-statistic of {f_val:.2f} with a p-value of {p_val:.4f}. "
                  f"A p-value less than 0.05 typically indicates a statistically significant difference between group means.")
        
        return {
            'title': f'ANOVA: {dependent} vs. {independent}',
            'stats_table_html': pd.DataFrame([{'F-statistic': f'{f_val:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url,
            'interpretation': interp
        }

    def run_ttest(self, continuous: str, group: str):
        """Runs an independent T-test."""
        if not pd.api.types.is_numeric_dtype(self.data[continuous]):
            raise TypeError(f"T-test continuous variable '{continuous}' must be numeric.")

        t_stat, p_val, groups = utils.perform_ttest_ind(self.data, continuous, group)
        plot_url = utils.generate_boxplot(self.data, group, continuous, f'Boxplot of {continuous} by {group}')

        interp = (f"An independent samples T-test was run to compare the means of '{continuous}' for two groups: '{groups[0]}' and '{groups[1]}'. "
                  f"The result is a T-statistic of {t_stat:.2f} and a p-value of {p_val:.4f}. "
                  f"A p-value less than 0.05 suggests a statistically significant difference in means.")
        
        return {
            'title': f'T-Test: {continuous} vs. {group}',
            'stats_table_html': pd.DataFrame([{'T-statistic': f'{t_stat:.2f}', 'p-value': f'{p_val:.4f}'}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url,
            'interpretation': interp
        }
        
    def run_chi_squared(self, var1: str, var2: str):
        """Runs a Chi-Squared test and generates a heatmap."""
        chi2, p, dof, table = utils.perform_chi_squared(self.data, var1, var2)
        plot_url = utils.generate_heatmap(table, f'Heatmap of {var1} vs. {var2}')

        interp = (f"A Chi-Squared test for independence was performed between '{var1}' and '{var2}'. "
                  f"The test yielded a Chi-Squared value of {chi2:.2f} with {dof} degrees of freedom and a p-value of {p:.4f}. "
                  f"A p-value less than 0.05 suggests that there is a statistically significant association between the two variables.")

        return {
            'title': f'Chi-Squared Test: {var1} vs. {var2}',
            'stats_table_html': pd.DataFrame([{'Chi-Squared': f'{chi2:.2f}', 'p-value': f'{p:.4f}', 'df': dof}]).to_html(classes='table table-sm', index=False),
            'plot_url': plot_url,
            'interpretation': interp,
            'contingency_table_html': table.to_html(classes='table table-sm table-bordered')
        }