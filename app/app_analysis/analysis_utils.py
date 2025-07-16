# --- START OF FILE analysis_utils.py ---
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

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

FIGSIZE_RECT = (8, 4)  # For most standard plots (bar, line, scatter)
FIGSIZE_SQUARE = (6,6)


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


def generate_frequency_table_html(series: pd.Series):
    """
    Generates a visually appealing frequency table.
    Now uses the generic styling function.
    """
    freq_df = series.value_counts().to_frame(name='Frequency')
    freq_df['Percentage (%)'] = (freq_df['Frequency'] / freq_df['Frequency'].sum() * 100).round(2)
    freq_df.index.name = 'Category'
    freq_df.reset_index(inplace=True)
    # Use the new generic styler, telling it to wrap the 'Category' column
    return generate_styled_html_table(freq_df, wrap_column='Category')



def generate_histogram(series: pd.Series, title: str):
    """Generates a histogram using the consistent app palette and size."""
    plt.figure(figsize=FIGSIZE_RECT) # <-- USE GLOBAL FIGSIZE
    sns.histplot(series, kde=True, bins=20, color=FLUID_CORE_PALETTE[0])
    plt.title(title, fontsize=16)
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
    Generates a bar chart with selectable orientation (horizontal or vertical)
    and annotates each bar with its percentage.
    """
    plt.figure(figsize=FIGSIZE_RECT)
    
    if orientation == 'vertical':
        ax = sns.countplot(x=series, order=series.value_counts().index, palette=FLUID_CORE_PALETTE)
        plt.xticks(rotation=45, ha='right') # Rotate labels for vertical chart
    else: # Default to horizontal
        ax = sns.countplot(y=series, order=series.value_counts().index, palette=FLUID_CORE_PALETTE)

    total = len(series.dropna())

    for patch in ax.patches:
        if orientation == 'vertical':
            count = patch.get_height()
            x = patch.get_x() + patch.get_width() / 2
            y = patch.get_height()
            ha = 'center'
            va = 'bottom'
            percentage = f'{100 * count / total:.1f}%'
            ax.text(x, y + (ax.get_ylim()[1] * 0.01), percentage, 
                    ha=ha, va=va, color='dimgrey', fontweight='bold', fontsize=10)
        else: # Horizontal
            count = patch.get_width()
            x = patch.get_width()
            y = patch.get_y() + patch.get_height() / 2
            ha = 'left'
            va = 'center'
            percentage = f'{100 * count / total:.1f}%'
            ax.text(x + (ax.get_xlim()[1] * 0.01), y, percentage, 
                    va=va, ha=ha, color='dimgrey', fontweight='bold', fontsize=10)

    if orientation == 'vertical':
        ax.set_ylim(top=ax.get_ylim()[1] * 1.1)
    else:
        ax.set_xlim(right=ax.get_xlim()[1] * 1.15)
    
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
    """
    Generates a pie chart with selectable styles (pie or donut) and an
    option to "explode" a specific slice for emphasis.
    """
    plt.figure(figsize=FIGSIZE_SQUARE)
    
    value_counts = series.value_counts()
    
    if len(value_counts) > 8: # Increased slightly to allow for more categories
        top_7 = value_counts.nlargest(7)
        other_sum = value_counts.nsmallest(len(value_counts) - 7).sum()
        top_7['Other'] = other_sum
        data_to_plot = top_7
    else:
        data_to_plot = value_counts

    colors = FLUID_CORE_PALETTE[0:len(data_to_plot)]
    
    # --- CLEANER STYLE AND EXPLODE LOGIC ---
    wedgeprops = None
    if style == 'donut':
        # Create a donut chart by drawing a white circle in the center
        wedgeprops = {'width': 0.6, 'edgecolor': 'white'}

    # Create the explode tuple based on the user's selection
    explode = [0] * len(data_to_plot) # Start with no explosion
    if explode_label and explode_label in data_to_plot.index:
        # Find the index of the label to explode
        explode_index = data_to_plot.index.get_loc(explode_label)
        explode[explode_index] = 0.1 # Set the explode value for that slice
        
    elif style == '3d':
        # Simulate a 3D effect with shadow and exploding the first slice
        shadow = True
        explode_values = [0.05] * len(data_to_plot) # Explode the first slice slightly
        explode = tuple(explode_values)
        
    plt.pie(data_to_plot, labels=data_to_plot.index, colors=colors, 
            autopct='%.1f%%', startangle=90, 
            wedgeprops=wedgeprops, 
            shadow=False, # Removed shadow for a cleaner look
            explode=tuple(explode)) # Pass the created explode tuple
    
    plt.title(title, fontsize=16)
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

