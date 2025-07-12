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
    except FileNotFoundError:
        flash("Encoded data not found. Please generate the encoded file from the Encoding Workflow first.", "warning")
        return redirect(url_for('encoding.assign', study_id=study_id))
    
    return render_template('analysis_dashboard.html', 
                           study=manager.study,
                           variables=variable_types,
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
    
    try:
        # --- NEW ANALYSIS TYPES ---
        if analysis_type == 'categorical_descriptive':
            col = request.form.get('cat_descriptive_var')
            result = manager.run_categorical_descriptives(col)
        
        elif analysis_type == 'multi_descriptive':
            cols = request.form.getlist('multi_descriptive_vars')
            result = manager.run_multi_descriptives(cols)
        
        elif analysis_type == 'correlation':
            var1 = request.form.get('corr_var1')
            var2 = request.form.get('corr_var2')
            result = manager.run_correlation(var1, var2)
            
        elif analysis_type == 'one_sample_ttest':
            col = request.form.get('one_sample_var')
            popmean = float(request.form.get('popmean', 3.0)) # Default to 3 as per docs
            result = manager.run_one_sample_ttest(col, popmean)

        # --- EXISTING ANALYSIS TYPES ---
        elif analysis_type == 'descriptive':
            col = request.form.get('descriptive_var')
            result = manager.run_descriptive_analysis(col)
        
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
            result = manager.run_chi_squared(var1, var2)
        
        else:
            flash("Invalid analysis type selected.", "danger")

    except (ValueError, TypeError, Exception) as e:
        flash(f"An error occurred during analysis: {e}", "danger")
        
    return render_template('analysis_dashboard.html',
                           study=manager.study,
                           variables=variable_types,
                           result=result,
                           selected_analysis=analysis_type)
    
# Corrected the documentation route path
@analysis_bp.route('/documentation')
def analysis_documentation():
    """Renders the static documentation page for Chapter 4."""
    return render_template('analysis_docs.html', title='Analysis Documentation')