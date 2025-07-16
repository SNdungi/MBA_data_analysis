# --- START OF FILE analysis_routes.py ---

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .analysis_manager import AnalysisManager

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis', template_folder='templates/analysis')

@analysis_bp.route('/dashboard/<int:study_id>')
def dashboard(study_id):
    """Main dashboard. Clears old data if requested."""
    if request.args.get('reset'):
        session.pop(f"analysis_data_{study_id}", None)
        flash("Analysis data has been reset to the original file.", "info")
        return redirect(url_for('analysis.dashboard', study_id=study_id))

    try:
        manager = AnalysisManager(study_id)
        variable_types = manager.get_variable_types()
        labeled_data = {}
        for col in variable_types.get('categorical', []):
            labeled_data[col] = manager._apply_value_labels(manager.data[col]).dropna().tolist()
    except FileNotFoundError:
        flash("Encoded data not found. Please generate the encoded file from the Encoding Workflow first.", "warning")
        return redirect(url_for('encoding.assign', study_id=study_id))
    
    return render_template('analysis_dashboard.html', 
                           study=manager.study,
                           variables=variable_types,
                           data_for_js=labeled_data,
                           result=None)

@analysis_bp.route('/create_composite/<int:study_id>', methods=['POST'])
def create_composite(study_id):
    """Handles the form submission to create a composite variable."""
    try:
        manager = AnalysisManager(study_id)
        new_var_name = request.form.get('new_var_name')
        source_vars = request.form.getlist('source_vars')
        message = manager.create_composite_variable(new_var_name, source_vars)
        flash(message, 'success')
    except (ValueError, TypeError, Exception) as e:
        flash(f"Error creating composite variable: {e}", "danger")
    
    return redirect(url_for('analysis.dashboard', study_id=study_id))


@analysis_bp.route('/run', methods=['POST'])
def run_analysis():
    """Handles the form submission to run a specific analysis."""
    study_id = request.form.get('study_id')
    analysis_type = request.form.get('analysis_type')
    
    manager = AnalysisManager(int(study_id))
    variable_types = manager.get_variable_types()
    result = None
    
    custom_figure_title = request.form.get('figure_title')
    
    try:
        if analysis_type == 'categorical_descriptive':
            col = request.form.get('cat_descriptive_var')
            plot_type = request.form.get('plot_type', 'bar')
            bar_orientation = request.form.get('bar_orientation', 'horizontal')
            pie_style = request.form.get('pie_style', 'pie')
            pie_explode = request.form.get('pie_explode') # Get the new value
            
            result = manager.run_categorical_descriptives(
                col, plot_type=plot_type, figure_title=custom_figure_title,
                bar_orientation=bar_orientation, pie_style=pie_style,
                pie_explode=pie_explode # Pass it to the manager
            )
            
        elif analysis_type == 'ordinal_analysis':
            col = request.form.get('ordinal_var')
            result = manager.run_ordinal_analysis(col, figure_title=custom_figure_title)
        
        elif analysis_type == 'multi_descriptive':
            cols = request.form.getlist('multi_descriptive_vars')
            result = manager.run_multi_descriptives(cols, figure_title=custom_figure_title)
        
        elif analysis_type == 'correlation':
            var1 = request.form.get('corr_var1')
            var2 = request.form.get('corr_var2')
            result = manager.run_correlation(var1, var2, figure_title=custom_figure_title)
            
        elif analysis_type == 'one_sample_ttest':
            col = request.form.get('one_sample_var')
            popmean = float(request.form.get('popmean', 3.0)) # Default to 3 as per docs
            result = manager.run_one_sample_ttest(col, popmean)

        elif analysis_type == 'descriptive':
            col = request.form.get('descriptive_var')
            result = manager.run_descriptive_analysis(col,figure_title=custom_figure_title)
        
        elif analysis_type == 'anova':
            dep = request.form.get('anova_dependent_var')
            indep = request.form.get('anova_independent_var')
            result = manager.run_anova(dep, indep)
            
        elif analysis_type == 'ttest':
            cont = request.form.get('ttest_continuous_var')
            group = request.form.get('ttest_group_var')
            result = manager.run_ttest(cont, group)

        elif analysis_type == 'chi2':
            var1 = request.form.get('chi2_var1')
            var2 = request.form.get('chi2_var2')
            result = manager.run_chi_squared(var1, var2,figure_title=custom_figure_title)
            
        elif analysis_type == 'comparison_plot':
            col_key = request.form.get('comparison_var')
            result = manager.run_comparison_plot(col_key)
        
        else:
            flash("Invalid analysis type selected.", "danger")

    except (ValueError, TypeError, Exception) as e:
        flash(f"An error occurred during analysis: {e}", "danger")
        
    labeled_data = {}
    for col in variable_types.get('categorical', []):
        labeled_data[col] = manager._apply_value_labels(manager.data[col]).dropna().tolist()
        
    return render_template('analysis_dashboard.html',
                           study=manager.study,
                           variables=variable_types,
                           data_for_js=labeled_data,
                           result=result,
                           selected_analysis=analysis_type)
    
# Corrected the documentation route path
@analysis_bp.route('/documentation')
def analysis_documentation():
    """Renders the static documentation page for Chapter 4."""
    return render_template('analysis_docs.html', title='Analysis Documentation')