# --- START OF FILE analysis_routes.py ---

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .analysis_manager import AnalysisManager

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis', template_folder='templates/analysis')

@analysis_bp.route('/dashboard/<int:study_id>')
def dashboard(study_id):
    """Main dashboard."""
    if request.args.get('reset'):
        session.pop(f"analysis_ops_{study_id}", None) # Fixed key name
        flash("Analysis data reset to original encoded file.", "info")
        return redirect(url_for('analysis.dashboard', study_id=study_id))

    try:
        manager = AnalysisManager(study_id)
        variable_types = manager.get_variable_types()
        
        # Prepare labeled data for JS (e.g. for dynamic dropdowns)
        labeled_data = {}
        for col in variable_types.get('categorical', []):
            labeled_data[col] = manager._apply_value_labels(manager.data[col]).dropna().tolist()
            
        return render_template('analysis_dashboard.html', 
                               study=manager.study,
                               variables=variable_types,
                               data_for_js=labeled_data,
                               result=None)
                               
    except FileNotFoundError:
        flash("Encoded data not found in workspace. Please run the Encoding Workflow first.", "warning")
        return redirect(url_for('encoding.assign', study_id=study_id))
    except PermissionError:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('file_mgt.list_projects'))
    except Exception as e:
        flash(f"Error loading dashboard: {e}", "danger")
        return redirect(url_for('file_mgt.project_admin', study_id=study_id))

@analysis_bp.route('/create_composite/<int:study_id>', methods=['POST'])
def create_composite(study_id):
    try:
        manager = AnalysisManager(study_id)
        msg = manager.create_composite_variable(
            request.form.get('new_var_name'), 
            request.form.getlist('source_vars')
        )
        flash(msg, 'success')
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('analysis.dashboard', study_id=study_id))

@analysis_bp.route('/tamper_data', methods=['POST'])
def tamper_data():
    study_id = request.form.get('study_id')
    try:
        manager = AnalysisManager(int(study_id))
        col = request.form.get('tamper_col')
        val = int(request.form.get('tamper_value'))
        rows = int(request.form.get('tamper_num_rows'))
        
        msg = manager.run_data_tampering(col, val, rows)
        flash(msg, 'success')
    except Exception as e:
        flash(f"Tampering failed: {e}", "danger")
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
            result = manager.run_multi_descriptives(cols)
        
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
            
        elif analysis_type == 'multi_category_descriptive':
            col = request.form.get('multi_cat_var')
            result = manager.run_multi_category_descriptives(col,figure_title=custom_figure_title)
            
        elif analysis_type == 'descriptive_ranking':
            cols = request.form.getlist('ranking_vars')
            result = manager.run_descriptive_ranking(cols)
            
        
        elif analysis_type == 'comparative_multi_category':
            var1 = request.form.get('comp_multi_cat_var1')
            var2 = request.form.get('comp_multi_cat_var2')
            figure_title = request.form.get('figure_title')
            result = manager.run_comparative_multi_category(var1, var2, figure_title)
        
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
            
        elif analysis_type == 'cronbach_alpha':
            cols = request.form.getlist('alpha_vars')
            result = manager.run_cronbach_alpha(cols)
            
        elif analysis_type == 'bivariate_correlation':
            x_vars = request.form.getlist('bivar_x_vars')
            y_var = request.form.get('bivar_y_var')
            result = manager.run_bivariate_correlation(x_vars, y_var)
            
        elif analysis_type == 'linear_regression':
            x_vars = request.form.getlist('reg_x_vars')
            y_var = request.form.get('reg_y_var')
            result = manager.run_linear_regression(x_vars, y_var)
            
        elif analysis_type == 'correlation_matrix':
            row_vars = request.form.getlist('corr_matrix_rows')
            col_vars = request.form.getlist('corr_matrix_cols')
            result = manager.run_correlation_matrix(row_vars, col_vars)
            
        elif analysis_type == 'likert_distribution':
            cols = request.form.getlist('likert_vars')
            figure_title = request.form.get('figure_title')
            result = manager.run_likert_distribution_chart(cols, figure_title)
        
        else:
            flash("Invalid analysis type selected.", "danger")

    except Exception as e:
        flash(f"Analysis failed: {e}", "danger")
    
    # Reload dashboard with result
    try:
        # Re-instantiate manager to get fresh state/variables for template
        manager = AnalysisManager(int(study_id))
        variable_types = manager.get_variable_types()
        labeled_data = {c: manager._apply_value_labels(manager.data[c]).dropna().tolist() for c in variable_types.get('categorical', [])}
        
        return render_template('analysis_dashboard.html',
                           study=manager.study,
                           variables=variable_types,
                           data_for_js=labeled_data,
                           result=result,
                           selected_analysis=analysis_type)
    except:
        return redirect(url_for('analysis.dashboard', study_id=study_id))
    

