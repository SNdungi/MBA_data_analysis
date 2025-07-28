# --- START OF FILE analysis_utils.py ---
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import pingouin as pg # Use Counter for efficient counting

# Set a consistent plot style
sns.set_theme(style="whitegrid")

FLUID_CORE_PALETTE = [
    "#02AEB4", 
    "#10f7ff",  
    "#caf8fa",  
    "#DCEEEE",  
    "#cceff0",  
    "#792c00",  
    "#FF4F03",   
    "#FFAB87", 
    "#E7E0DC",
    "#410077",     
]

FIGSIZE_RECT = (6, 4)  # For most standard plots (bar, line, scatter)
FIGSIZE_SQUARE = (5,5)


# --- NO CHANGES TO THESE FUNCTIONS ---
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



# --- REUSABLE STYLING HELPER ---
def _get_base_table_style() -> str:
    """Returns a string of CSS for styling pandas DataFrames into beautiful HTML tables."""
    return """
    <style>
        .styled-table {
            border-collapse: collapse;
            width: 100%;
            font-size: 0.9em;
            margin: 0;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        .styled-table thead th {
            background-color: #f7f1ee; /* Your light theme color */
            color: #333333;
            font-weight: bold;
            border: 1px solid #dddddd;
            padding: 10px 12px;
            text-align: left; /* Justify header to start */
        }
        .styled-table tbody td, .styled-table tbody th {
            border: 1px solid #dddddd;
            padding: 10px 12px;
            text-align: left; /* Justify body cells to start */
        }
        .styled-table tbody tr {
            border-bottom: 1px solid #f0f0f0;
        }
        .styled-table tbody tr:nth-of-type(even) {
            background-color: #f8f8f8;
        }
        .styled-table tbody tr:last-of-type {
            border-bottom: 2px solid #23797c; /* Your theme teal color */
        }
        .styled-table .wrap-text {
            white-space: normal;
            word-break: break-word;
        }
    </style>
    """

# --- NEW GENERIC STYLED TABLE GENERATOR ---
def generate_styled_html_table(dataframe: pd.DataFrame, wrap_column: str = None) -> str:
    """
    Takes a pandas DataFrame and returns a fully styled HTML table string.
    Optionally wraps text in a specified column.
    """
    formatters = {}
    if wrap_column and wrap_column in dataframe.columns:
        formatters[wrap_column] = lambda x: f'<div class="wrap-text">{x}</div>'
    
    html_table = dataframe.to_html(
        classes='styled-table',
        index=False,
        border=0,
        escape=False,
        formatters=formatters if formatters else None
    )
    return _get_base_table_style() + html_table


# --- UPDATED FREQUENCY TABLE FUNCTION ---
def generate_frequency_table_html(series: pd.Series):
    """
    Generates a visually appealing frequency table with WHOLE NUMBER percentages.
    """
    freq_df = series.value_counts().to_frame(name='Frequency')
    # FIX: Round percentage to 0 decimal places for whole numbers
    freq_df['Percentage (%)'] = (freq_df['Frequency'] / freq_df['Frequency'].sum() * 100).round(0).astype(int)
    freq_df.index.name = 'Category'
    freq_df.reset_index(inplace=True)
    return generate_styled_html_table(freq_df, wrap_column='Category')

# --- UPDATED MULTI-CATEGORY FREQUENCY TABLE FUNCTION ---
def generate_multicategory_frequency_table(cleaned_items_series: pd.Series) -> str:
    """
    Generates a frequency table from a pre-cleaned Series of individual items
    with WHOLE NUMBER percentages.
    """
    freq_df = cleaned_items_series.value_counts().to_frame(name='Frequency')
    total_items = freq_df['Frequency'].sum()
    # FIX: Round percentage to 0 decimal places for whole numbers
    freq_df['Percentage of Total Selections (%)'] = (freq_df['Frequency'] / total_items * 100).round(0).astype(int)
    freq_df.index.name = 'Category'
    freq_df.reset_index(inplace=True)
    return generate_styled_html_table(freq_df, wrap_column='Category')



def generate_histogram(series: pd.Series, title: str):
    """Generates a histogram using the consistent app palette and size."""
    plt.figure(figsize=FIGSIZE_RECT) # <-- USE GLOBAL FIGSIZE
    sns.histplot(series, kde=True, bins=20, color=FLUID_CORE_PALETTE[0])
    plt.title(title, fontsize=14)
    plt.xlabel(series.name)
    plt.ylabel('Frequency')
    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_barchart(series: pd.Series, title: str, orientation: str = 'horizontal'):
    """
    Generates a bar chart and annotates each bar with its WHOLE NUMBER percentage.
    """
    plt.figure(figsize=FIGSIZE_RECT)
    
    if orientation == 'vertical':
        ax = sns.countplot(x=series, order=series.value_counts().index, palette=FLUID_CORE_PALETTE)
        plt.xticks(rotation=45, ha='right')
    else:
        ax = sns.countplot(y=series, order=series.value_counts().index, palette=FLUID_CORE_PALETTE)

    total = len(series.dropna())

    for patch in ax.patches:
        if orientation == 'vertical':
            count = patch.get_height()
            x = patch.get_x() + patch.get_width() / 2
            y = patch.get_height()
            ha, va = 'center', 'bottom'
            # FIX: Format percentage as a whole number
            percentage = f'{100 * count / total:.0f}%' 
            ax.text(x, y + (ax.get_ylim()[1] * 0.01), percentage, 
                    ha=ha, va=va, color='dimgrey', fontweight='bold', fontsize=10)
        else: # Horizontal
            count = patch.get_width()
            x, y = patch.get_width(), patch.get_y() + patch.get_height() / 2
            ha, va = 'left', 'center'
            # FIX: Format percentage as a whole number
            percentage = f'{100 * count / total:.0f}%'
            ax.text(x + (ax.get_xlim()[1] * 0.01), y, percentage, 
                    va=va, ha=ha, color='dimgrey', fontweight='bold', fontsize=10)

    # ... (rest of the function is unchanged)
    if orientation == 'vertical': ax.set_ylim(top=ax.get_ylim()[1] * 1.1)
    else: ax.set_xlim(right=ax.get_xlim()[1] * 1.15)
    plt.title(title, fontsize=16)
    plt.xlabel('Count' if orientation == 'horizontal' else series.name)
    plt.ylabel(series.name if orientation == 'horizontal' else 'Count')
    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')
    
def generate_piechart(series: pd.Series, title: str, style: str = 'pie', explode_label: str = None):
    plt.figure(figsize=FIGSIZE_SQUARE)
    value_counts = series.value_counts()
    if len(value_counts) > 8:
        top_7 = value_counts.nlargest(7)
        other_sum = value_counts.nsmallest(len(value_counts) - 7).sum()
        top_7['Other'] = other_sum
        data_to_plot = top_7
    else:
        data_to_plot = value_counts
    colors = FLUID_CORE_PALETTE[0:len(data_to_plot)]
    wedgeprops = None
    if style == 'donut': wedgeprops = {'width': 0.6, 'edgecolor': 'white'}
    explode = [0] * len(data_to_plot)
    if explode_label and explode_label in data_to_plot.index:
        explode_index = data_to_plot.index.get_loc(explode_label)
        explode[explode_index] = 0.1
    plt.pie(data_to_plot, labels=data_to_plot.index, colors=colors, autopct='%.0f%%', startangle=90, wedgeprops=wedgeprops, shadow=False, explode=tuple(explode))
    plt.title(title, fontsize=14)
    plt.ylabel('')
    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_scatterplot(df: pd.DataFrame, x_var: str, y_var: str, title: str):
    """Generates a scatter plot using the consistent app palette and size."""
    plt.figure(figsize=FIGSIZE_RECT) # <-- USE GLOBAL FIGSIZE
    sns.regplot(x=x_var, y=y_var, data=df, 
                scatter_kws={'color': FLUID_CORE_PALETTE[0]}, 
                line_kws={"color": FLUID_CORE_PALETTE[1]})
    plt.title(title, fontsize=16)
    plt.xlabel(x_var)
    plt.ylabel(y_var)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_boxplot(df: pd.DataFrame, x_var: str, y_var: str, title: str):
    """Generates a boxplot using the consistent app palette and size."""
    plt.figure(figsize=FIGSIZE_RECT) # <-- USE GLOBAL FIGSIZE
    sns.boxplot(x=x_var, y=y_var, data=df, palette=FLUID_CORE_PALETTE)
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

def generate_heatmap(contingency_table: pd.DataFrame, title: str):
    """Generates a heatmap using a standard palette and consistent size."""
    plt.figure(figsize=FIGSIZE_SQUARE) # <-- USE GLOBAL FIGSIZE
    sns.heatmap(contingency_table, annot=True, fmt='d', cmap='YlGnBu')
    plt.title(title, fontsize=16)
    plt.tight_layout()
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_comparison_kde_plot(series1: pd.Series, series2: pd.Series, title: str, series1_name: str, series2_name: str):
    """Generates a side-by-side KDE plot using the consistent app size."""
    plt.figure(figsize=FIGSIZE_RECT) # <-- USE GLOBAL FIGSIZE
    sns.kdeplot(series1, label=series1_name, color=FLUID_CORE_PALETTE[0], fill=True, alpha=0.1)
    sns.kdeplot(series2, label=series2_name, color=FLUID_CORE_PALETTE[1], linestyle='--')
    plt.title(title, fontsize=16)
    plt.xlabel("Encoded Value")
    plt.ylabel("Density")
    plt.legend()
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

def generate_enhanced_crosstab(contingency_table: pd.DataFrame) -> str:
    """
    Creates a detailed HTML crosstabulation table with counts, row percentages,
    and column percentages, similar to SPSS output.
    """
    # Create a copy with totals
    ct_total = contingency_table.copy()
    ct_total['Total'] = ct_total.sum(axis=1)
    ct_total.loc['Total'] = ct_total.sum()

    total_n = ct_total.loc['Total', 'Total']

    # Calculate percentages based on the original table (without totals)
    row_pct = (contingency_table.div(contingency_table.sum(axis=1), axis=0) * 100).round(1)
    col_pct = (contingency_table.div(contingency_table.sum(axis=0), axis=1) * 100).round(1)

    # Begin building the HTML string
    style = """
    <style>
        .crosstab-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        .crosstab-table th, .crosstab-table td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        .crosstab-table thead th { background-color: #f2f2f2; font-weight: bold; }
        .crosstab-table .row-header { font-weight: bold; }
        .crosstab-table .cell-block { line-height: 1.4; }
        .crosstab-table .cell-label { color: #666; font-size: 0.85em; display: inline-block; width: 55px; }
        .crosstab-table .total-row th, .crosstab-table .total-row td { font-weight: bold; background-color: #f2f2f2; }
    </style>
    """
    html = f'{style}<table class="crosstab-table"><thead><tr><th></th>'
    
    # Header row
    for col_name in ct_total.columns:
        html += f'<th>{col_name}</th>'
    html += '</tr></thead><tbody>'

    # Table body rows
    for row_idx, row in ct_total.iterrows():
        is_total_row = row_idx == 'Total'
        html += f'<tr class="{"total-row" if is_total_row else ""}">'
        html += f'<th class="row-header">{row_idx}</th>'
        
        for col_idx, count in row.items():
            html += '<td><div class="cell-block">'
            html += f'<div><span class="cell-label">Count</span> <b>{count:,.0f}</b></div>'
            
            # Add percentages only for non-total cells
            if not is_total_row and col_idx != 'Total':
                html += f'<div><span class="cell-label">% w/in Row</span> {row_pct.loc[row_idx, col_idx]:.1f}%</div>'
                html += f'<div><span class="cell-label">% w/in Col</span> {col_pct.loc[row_idx, col_idx]:.1f}%</div>'
            
            html += '</div></td>'
        html += '</tr>'
        
    html += '</tbody></table>'
    return html
#______________________________________________________________________________
#-------------------------------------------------------------------------------

#DUAL VIEWER
#______________________________________________________________________________
#--------------------------------------------------------------------------------
def generate_dual_barchart(series1: pd.Series, series2: pd.Series, title1: str, title2: str) -> str:
    """
    Generates a single figure with two side-by-side horizontal bar charts.
    """
    # Prepare data for both series
    items1 = series1.str.split(',').explode().str.strip().loc[lambda x: x != ''].value_counts()
    items2 = series2.str.split(',').explode().str.strip().loc[lambda x: x != ''].value_counts()

    # Create a figure with 1 row and 2 columns of subplots
    fig, axes = plt.subplots(1, 2, figsize=(FIGSIZE_RECT[0] * 1.8, FIGSIZE_RECT[1] * 1.2)) # Wider figure
    
    # --- Plot 1 ---
    sns.barplot(x=items1.values, y=items1.index, ax=axes[0], palette=FLUID_CORE_PALETTE)
    axes[0].set_title(title1, fontsize=14)
    axes[0].set_xlabel('Frequency')
    axes[0].set_ylabel('')

    # --- Plot 2 ---
    sns.barplot(x=items2.values, y=items2.index, ax=axes[1], palette=FLUID_CORE_PALETTE)
    axes[1].set_title(title2, fontsize=14)
    axes[1].set_xlabel('Frequency')
    axes[1].set_ylabel('')

    plt.tight_layout(pad=3.0) # Add padding between plots
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')

def generate_combined_frequency_table(series1: pd.Series, series2: pd.Series) -> str:
    """
    Generates a single HTML table comparing the frequencies of items from two
    multi-category columns.
    """
    # Prepare counts for both series
    counts1 = series1.str.split(',').explode().str.strip().loc[lambda x: x != ''].value_counts()
    counts2 = series2.str.split(',').explode().str.strip().loc[lambda x: x != ''].value_counts()
    
    # Create a DataFrame from the two count series
    combined_df = pd.DataFrame({
        f'Frequency ({series1.name})': counts1,
        f'Frequency ({series2.name})': counts2
    })
    
    # Fill NaN with 0 for items not present in one of the lists, then convert to int
    combined_df.fillna(0, inplace=True)
    combined_df = combined_df.astype(int)
    
    # Sort by the frequency of the first column
    combined_df.sort_values(by=f'Frequency ({series1.name})', ascending=False, inplace=True)
    
    combined_df.index.name = 'Category'
    combined_df.reset_index(inplace=True)

    return generate_styled_html_table(combined_df, wrap_column='Category')

#______________________________________________________________________________
#-------------------------------------------------------------------------------

# === NEW FUNCTION FOR DESCRIPTIVE RANKING ANALYSIS ===
#______________________________________________________________________________
#-------------------------------------------------------------------------------

def perform_descriptive_ranking(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Performs a descriptive ranking analysis based on the Coefficient of Variation.
    
    Args:
        df: The input DataFrame.
        columns: A list of column names (e.g., ['q9', 'q10']) to analyze.
        
    Returns:
        A pandas DataFrame with N, Mean, Std Dev, CV, and Ranking.
    """
    if not columns:
        raise ValueError("Column list cannot be empty.")
    
    # 1. Select the relevant columns and calculate stats
    analysis_df = df[columns]
    descriptive_stats = analysis_df.agg(['count', 'mean', 'std']).T

    # 2. Rename columns for clarity
    descriptive_stats.rename(columns={
        'count': 'N', 'mean': 'Mean', 'std': 'Std Dev'
    }, inplace=True)
    descriptive_stats['N'] = descriptive_stats['N'].astype(int)

    # 3. Calculate the Coefficient of Variation (CV)
    # Handle potential division by zero if mean is 0
    descriptive_stats['CV'] = (descriptive_stats['Std Dev'] / descriptive_stats['Mean']).fillna(0)

    # 4. Rank by CV (lowest CV = Rank 1, indicating highest consensus)
    descriptive_stats['Ranking'] = descriptive_stats['CV'].rank(method='min').astype(int)
    
    # 5. Sort by the new ranking
    ranked_table = descriptive_stats.sort_values(by='Ranking')
    
    return ranked_table

#___________________________________________________________

# ===  RELIABILITY ANALYSIS ===

#_________________________________________________________

def calculate_cronbach_alpha(df: pd.DataFrame, items: list) -> pd.DataFrame:
    """
    Calculates Cronbach's Alpha for a set of items (columns).
    
    Args:
        df: The DataFrame containing the data.
        items: A list of column names that make up the scale.
        
    Returns:
        A pandas DataFrame with the Cronbach's Alpha results, ready for display.
    """
    if not items or len(items) < 2:
        raise ValueError("Cronbach's Alpha requires at least two items (columns).")
    
    # Select only the relevant columns and drop rows with any missing values
    # This is crucial for an accurate calculation.
    scale_df = df[items].dropna()
    
    if len(scale_df) < 2:
        raise ValueError("Not enough valid data (after dropping missing values) to calculate Cronbach's Alpha.")

    # Use pingouin to calculate Cronbach's Alpha
    # pg.cronbach_alpha returns a tuple: (alpha, confidence_interval)
    alpha_results = pg.cronbach_alpha(data=scale_df)
    
    # Format the results into a nice DataFrame for display
    results_df = pd.DataFrame({
        'Metric': ["Cronbach's Alpha", "95% Confidence Interval", "Number of Items"],
        'Value': [
            f"{alpha_results[0]:.3f}",
            f"[{alpha_results[1][0]:.3f}, {alpha_results[1][1]:.3f}]",
            len(items)
        ]
    })
    
    return results_df

import scipy.stats as stats

#===============================================================================
# === BIVARIATE CORRELATION MATRIX ===
#================================================================================

def perform_bivariate_correlations(df: pd.DataFrame, x_vars: list, y_var: str) -> pd.DataFrame:
    """
    Calculates Pearson correlation between a list of independent variables (x_vars)
    and a single dependent variable (y_var).
    
    Args:
        df: The input DataFrame.
        x_vars: A list of independent variable column names.
        y_var: The single dependent variable column name.
        
    Returns:
        A DataFrame summarizing the correlation results for each pair.
    """
    if not x_vars:
        raise ValueError("You must select at least one independent variable.")
    if y_var in x_vars:
        raise ValueError("The dependent variable cannot also be in the list of independent variables.")
        
    results = []
    
    for x in x_vars:
        # Drop missing values pair-wise
        clean_df = df[[x, y_var]].dropna()
        
        if len(clean_df) < 3: # Not enough data to correlate
            r, p_val, sig = 'N/A', 'N/A', 'Not enough data'
        else:
            r, p_val = stats.pearsonr(clean_df[x], clean_df[y_var])
            # Determine significance level for easy interpretation
            if p_val < 0.001:
                sig = 'p < .001'
            elif p_val < 0.01:
                sig = 'p < .01'
            elif p_val < 0.05:
                sig = 'p < .05'
            else:
                sig = 'Not Significant'

        results.append({
            'Independent Variable': x,
            'Pearson r': r,
            'p-value': p_val,
            'Significance': sig
        })
        
    results_df = pd.DataFrame(results)
    return results_df

import statsmodels.api as sm # Add this import


def perform_linear_regression(df: pd.DataFrame, x_vars: list, y_var: str) -> dict:
    """
    Performs an OLS linear regression and returns the results formatted into three
    distinct SPSS-style tables: Model Summary, ANOVA, and Coefficients.
    """

    if not x_vars:
        raise ValueError("You must select at least one independent variable.")
    if y_var in x_vars:
        raise ValueError("The dependent variable cannot also be in the list of independent variables.")
    
    model_df = df[[y_var] + x_vars].dropna()
    if len(model_df) < len(x_vars) + 2:
        raise ValueError("Not enough data to run the regression.")

    Y = model_df[y_var]
    X = model_df[x_vars]
    X = sm.add_constant(X)
    model = sm.OLS(Y, X).fit()

    # --- 1. Build the Model Summary Table ---
    model_summary_df = pd.DataFrame({
        'R': [np.sqrt(model.rsquared)],
        'R Square': [model.rsquared],
        'Adjusted R Square': [model.rsquared_adj],
        'Std. Error of the Estimate': [np.sqrt(model.mse_resid)]
    }).applymap('{:.3f}'.format)
    
    # --- 2. Build the ANOVA Table ---
    anova_df = pd.DataFrame({
        'Source': ['Regression', 'Residual', 'Total'],
        'Sum of Squares': [model.ess, model.ssr, model.centered_tss],
        'df': [model.df_model, model.df_resid, model.nobs - 1],
        'Mean Square': [model.mse_model, model.mse_resid, '—'],
        'F': [model.fvalue, '—', '—'],
        'Sig.': [model.f_pvalue, '—', '—']
    })
    # Formatting the ANOVA table
    for col in ['Sum of Squares', 'Mean Square']:
        anova_df[col] = anova_df[col].apply(lambda x: f'{x:.3f}' if isinstance(x, (int, float)) else x)
    anova_df['F'] = anova_df['F'].apply(lambda x: f'{x:.2f}' if isinstance(x, (int, float)) else x)
    anova_df['Sig.'] = anova_df['Sig.'].apply(lambda x: f'{x:.3f}'.lstrip('0') if isinstance(x, (int, float)) else x)


    # --- 3. Build the Coefficients Table ---
    coeffs_df = pd.DataFrame({
        'Predictor': model.params.index.str.replace('const', '(Constant)'),
        'B': model.params.values,
        'Std. Error': model.bse.values,
        't': model.tvalues.values,
        'Sig.': model.pvalues.values
    })
    # Formatting the Coefficients table
    for col in ['B', 'Std. Error', 't']:
        coeffs_df[col] = coeffs_df[col].apply('{:.3f}'.format)
    coeffs_df['Sig.'] = coeffs_df['Sig.'].apply(lambda x: f'{x:.3f}'.lstrip('0'))
    # Add the Beta column (Standardized Coefficients)
    # Note: statsmodels doesn't calculate this by default. For simplicity, we'll add it as a placeholder.
    # A full implementation would require standardizing the data first.
    coeffs_df.insert(3, 'Beta', '—')


    # --- 4. Convert all DataFrames to styled HTML ---
    model_summary_html = generate_styled_html_table(model_summary_df)
    anova_html = generate_styled_html_table(anova_df)
    coeffs_html = generate_styled_html_table(coeffs_df, wrap_column='Predictor')

    return {
        'model_summary_table': model_summary_html,
        'anova_table': anova_html,
        'coeffs_table': coeffs_html,
        'adj_r_squared': f"{model.rsquared_adj:.3f}", # Keep raw values for interpretation
        'f_pvalue': f"{model.f_pvalue:.4f}"
    }
    

from itertools import product # To get all pairs of variables


# === NEW FUNCTION FOR SPSS-STYLE CORRELATION MATRIX ===
def generate_spss_correlation_matrix(df: pd.DataFrame, row_vars: list, col_vars: list) -> str:
    """
    Generates an SPSS-style correlation matrix as a styled HTML table.
    
    Args:
        df: The input DataFrame.
        row_vars: A list of variables for the table rows.
        col_vars: A list of variables for the table columns.
        
    Returns:
        A styled HTML table string.
    """
    if not row_vars or not col_vars:
        raise ValueError("Both row and column variable lists are required.")

    # --- 1. Calculate all pairwise correlations ---
    results_data = []
    for row_var, col_var in product(row_vars, col_vars):
        if row_var == col_var: # Skip self-correlation
            r, p_val, n = 1.0, 0.0, len(df[[row_var]].dropna())
        else:
            clean_df = df[[row_var, col_var]].dropna()
            n = len(clean_df)
            if n < 3:
                r, p_val = float('nan'), float('nan')
            else:
                r, p_val = stats.pearsonr(clean_df[row_var], clean_df[col_var])
        
        results_data.append({'row_var': row_var, 'col_var': col_var, 'r': r, 'p': p_val, 'n': n})

    results_df = pd.DataFrame(results_data)

    # --- 2. Build the HTML Table Manually for SPSS-style formatting ---
    style = """
    <style>
        .spss-corr-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
        .spss-corr-table th, .spss-corr-table td { border: 1px solid #999; padding: 6px; text-align: left; }
        .spss-corr-table thead th { background-color: #f2f2f2; font-weight: bold; text-align: center; }
        .spss-corr-table .row-header { font-weight: bold; vertical-align: middle; }
        .spss-corr-table .metric-header { font-weight: normal; font-style: italic; color: #333; padding-left: 20px; border-right: none; }
        .spss-corr-table .cell-value { text-align: right; }
        .spss-corr-table .footnote { font-size: 0.85em; margin-top: 10px; }
    </style>
    """
    html = f'{style}<table class="spss-corr-table"><thead><tr><th></th><th></th>'
    
    for col_var in col_vars: html += f'<th>{col_var}</th>'
    html += '</tr></thead><tbody>'

    for row_var in row_vars:
        html += f'<tr>'
        html += f'<td rowspan="3" class="row-header">{row_var}</td>'
        
        # Pearson Correlation row
        html += '<td class="metric-header">Pearson Correlation</td>'
        for col_var in col_vars:
            res = results_df[(results_df.row_var == row_var) & (results_df.col_var == col_var)].iloc[0]
            r_val, p_val = res['r'], res['p']
            r_str = f"{r_val:.3f}".lstrip('0') if not pd.isna(r_val) else ""
            if p_val < 0.01: r_str += "**"
            elif p_val < 0.05: r_str += "*"
            html += f'<td class="cell-value">{r_str}</td>'
        html += '</tr><tr>'
        
        # Sig. (2-tailed) row
        html += '<td class="metric-header">Sig. (2-tailed)</td>'
        for col_var in col_vars:
            res = results_df[(results_df.row_var == row_var) & (results_df.col_var == col_var)].iloc[0]
            p_val = res['p']
            p_str = f"{p_val:.3f}".lstrip('0') if not pd.isna(p_val) else ""
            html += f'<td class="cell-value">{p_str}</td>'
        html += '</tr><tr>'

        # N row
        html += '<td class="metric-header">N</td>'
        for col_var in col_vars:
            res = results_df[(results_df.row_var == row_var) & (results_df.col_var == col_var)].iloc[0]
            n_val = res['n']
            html += f'<td class="cell-value">{n_val}</td>'
        html += '</tr>'

    html += '</tbody></table>'
    html += '<p class="footnote">*. Correlation is significant at the 0.05 level (2-tailed).<br>**. Correlation is significant at the 0.01 level (2-tailed).</p>'
    
    return html




# === THIS IS THE CORRECTED AND FINAL PLOTTING FUNCTION ===
def generate_diverging_stacked_bar(freq_df: pd.DataFrame, title: str) -> str:
    """
    Generates a clean diverging stacked bar chart with the legend at the bottom.
    The DataFrame index is expected to be the short keys (e.g., 'q30').
    """
    # --- Color and Data Preparation (Unchanged) ---
    if freq_df.shape[1] == 5: # 5-point scale
        neg_colors = plt.get_cmap('Reds_r')(np.linspace(0.6, 0.9, 2))
        neu_color = plt.get_cmap('Greys')(0.4)
        pos_colors = plt.get_cmap('Blues')(np.linspace(0.6, 0.9, 2))
        colors = np.vstack((neg_colors, neu_color, pos_colors))
        neg_cols = freq_df.columns[0:2].tolist()
        neu_col = freq_df.columns[2]
        pos_cols = freq_df.columns[3:5].tolist()
    else: # Fallback for other scales
        num_neg = freq_df.shape[1] // 2
        neg_cols = freq_df.columns[0:num_neg].tolist()
        neu_col = None
        pos_cols = freq_df.columns[num_neg:].tolist()
        colors = FLUID_CORE_PALETTE
    
    plot_data = freq_df.copy()
    if neu_col:
        plot_data.insert(0, f'-{neu_col}', -plot_data[neu_col] / 2)
        plot_data[neu_col] = plot_data[neu_col] / 2
        neg_cols_with_neutral = [f'-{neu_col}'] + neg_cols
    else:
        neg_cols_with_neutral = neg_cols
    neg_cumulative = plot_data[neg_cols_with_neutral].cumsum(axis=1)
    pos_cumulative = plot_data[pos_cols].cumsum(axis=1)

    # --- Create the Plot ---
    # Adjust figure height based on the number of questions
    fig_height = len(freq_df) * 0.7 + 2 # Base height + per-question height
    fig, ax = plt.subplots(figsize=(FIGSIZE_RECT[0] * 1.5, fig_height))

    # Plot negative and neutral bars
    for i, col in enumerate(neg_cols_with_neutral):
        left = neg_cumulative.iloc[:, i-1] if i > 0 else 0
        ax.barh(plot_data.index, plot_data[col], left=left, color=colors[i], label=col.strip('-'))

    # Plot positive bars
    for i, col in enumerate(pos_cols):
        left = pos_cumulative.iloc[:, i-1] if i > 0 else plot_data.get(neu_col, 0)
        ax.barh(plot_data.index, plot_data[col], left=left, color=colors[len(neg_cols_with_neutral) + i], label=col)
    
    # --- CLEANED UP FORMATTING ---
    ax.set_title(title, fontsize=16, pad=20)
    
    # FIX: Move the legend back to the bottom, outside the plot area
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=freq_df.shape[1], frameon=False)
    
    ax.axvline(0, color='grey', linewidth=0.8)
    ax.set_xticks(np.arange(-100, 101, 25))
    ax.set_xticklabels([f'{abs(x)}%' for x in np.arange(-100, 101, 25)])
    ax.set_xlabel('Percentage of Responses')
    ax.invert_yaxis()
    
    # FIX: Remove the fig.text block for the question key
    
    plt.tight_layout()
    # Adjust layout to make room for the bottom legend
    plt.subplots_adjust(bottom=0.2)
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf8')


# === NEW FUNCTION FOR DATA TAMPERING ===
def tamper_data(df: pd.DataFrame, column: str, new_value, num_rows: int, random_state=None) -> pd.DataFrame:
    """
    Randomly selects a specified number of rows in a column and changes their
    value to a new specified value.
    
    Args:
        df: The input DataFrame.
        column: The name of the column to tamper with.
        new_value: The new value to assign.
        num_rows: The number of rows to randomly change.
        random_state: An integer for reproducible randomness.
        
    Returns:
        The tampered DataFrame.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in the DataFrame.")
    
    # Ensure num_rows is not greater than the total number of rows
    num_rows = min(num_rows, len(df))
    
    # Get the indices of the rows to change
    indices_to_change = df.sample(n=num_rows, random_state=random_state).index
    
    # Create a copy to avoid modifying the original DataFrame in place
    df_tampered = df.copy()
    
    # Apply the change
    df_tampered.loc[indices_to_change, column] = new_value
    
    return df_tampered
