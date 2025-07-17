# --- START OF FILE analysis_utils.py ---
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from collections import Counter # Use Counter for efficient counting

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
