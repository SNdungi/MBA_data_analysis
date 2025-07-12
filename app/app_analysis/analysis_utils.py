# --- START OF FILE analysis_utils.py ---

import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

# Set a consistent plot style
sns.set_theme(style="whitegrid")

def get_descriptives(series: pd.Series):
    """Calculates descriptive statistics for a single continuous variable."""
    desc = series.describe().to_frame().reset_index()
    desc.columns = ['Metric', 'Value']
    desc['Value'] = desc['Value'].apply(lambda x: f'{x:,.2f}')
    return desc

def get_descriptives_for_multiple(df: pd.DataFrame, columns: list):
    """Calculates key descriptive statistics for multiple columns."""
    stats = df[columns].describe().T
    stats = stats[['count', 'mean', 'std', 'min', 'max']]
    stats.columns = ['N', 'Mean', 'Std. Dev.', 'Min', 'Max']
    stats['N'] = stats['N'].astype(int)
    stats = stats.round(2)
    return stats.reset_index().rename(columns={'index': 'Variable'})

def generate_frequency_table_html(series: pd.Series):
    """Generates an HTML frequency table for a categorical variable."""
    freq = series.value_counts().to_frame(name='Frequency')
    freq['Percentage (%)'] = (freq['Frequency'] / freq['Frequency'].sum() * 100).round(2)
    return freq.to_html(classes='table table-sm table-striped', border=0)

def generate_histogram(series: pd.Series, title: str):
    """Generates a histogram and returns it as a base64 encoded string."""
    plt.figure(figsize=(8, 5))
    sns.histplot(series, kde=True, bins=20)
    plt.title(title, fontsize=16)
    plt.xlabel(series.name)
    plt.ylabel('Frequency')
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_barchart(series: pd.Series, title: str):
    """Generates a bar chart for a categorical variable."""
    plt.figure(figsize=(10, 6))
    sns.countplot(y=series, order=series.value_counts().index, palette='viridis')
    plt.title(title, fontsize=16)
    plt.xlabel('Count')
    plt.ylabel(series.name)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')
    
def generate_scatterplot(df: pd.DataFrame, x_var: str, y_var: str, title: str):
    """Generates a scatter plot with a regression line."""
    plt.figure(figsize=(8, 6))
    sns.regplot(x=x_var, y=y_var, data=df, line_kws={"color": "red"})
    plt.title(title, fontsize=16)
    plt.xlabel(x_var)
    plt.ylabel(y_var)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def perform_one_sample_ttest(series: pd.Series, popmean: float):
    """Performs a one-sample T-test."""
    t_stat, p_val = stats.ttest_1samp(series.dropna(), popmean)
    return t_stat, p_val

def perform_pearson_correlation(series1: pd.Series, series2: pd.Series):
    """Performs a Pearson correlation test."""
    # Drop rows where either series has a NaN value
    combined = pd.concat([series1, series2], axis=1).dropna()
    r, p_val = stats.pearsonr(combined.iloc[:, 0], combined.iloc[:, 1])
    return r, p_val

def perform_anova(df: pd.DataFrame, dependent_var: str, independent_var: str):
    """Performs a one-way ANOVA test."""
    groups = df.groupby(independent_var)[dependent_var].apply(list)
    # Filter out any empty groups that might result from NaNs
    valid_groups = [g for g in groups if len(g) > 0]
    if len(valid_groups) < 2:
        raise ValueError("ANOVA requires at least two groups with data.")
    f_val, p_val = stats.f_oneway(*valid_groups)
    return f_val, p_val

def generate_boxplot(df: pd.DataFrame, x_var: str, y_var: str, title: str):
    """Generates a boxplot and returns it as a base64 encoded string."""
    plt.figure(figsize=(10, 6))
    sns.boxplot(x=x_var, y=y_var, data=df, palette='pastel')
    plt.title(title, fontsize=16)
    plt.xlabel(x_var)
    plt.ylabel(y_var)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def perform_ttest_ind(df: pd.DataFrame, continuous_var: str, group_var: str):
    """Performs an independent samples T-test for two groups."""
    unique_groups = df[group_var].dropna().unique()
    if len(unique_groups) != 2:
        raise ValueError(f"T-test requires exactly two groups, but found {len(unique_groups)} in '{group_var}'.")
    
    group1 = df[df[group_var] == unique_groups[0]][continuous_var]
    group2 = df[df[group_var] == unique_groups[1]][continuous_var]
    
    t_stat, p_val = stats.ttest_ind(group1.dropna(), group2.dropna())
    return t_stat, p_val, unique_groups

def perform_chi_squared(df: pd.DataFrame, var1: str, var2: str):
    """Performs a Chi-Squared test of independence."""
    contingency_table = pd.crosstab(df[var1], df[var2])
    chi2, p, dof, expected = stats.chi2_contingency(contingency_table)
    return chi2, p, dof, contingency_table

def generate_heatmap(contingency_table: pd.DataFrame, title: str):
    """Generates a heatmap for a contingency table."""
    plt.figure(figsize=(10, 7))
    sns.heatmap(contingency_table, annot=True, fmt='d', cmap='YlGnBu')
    plt.title(title, fontsize=16)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')