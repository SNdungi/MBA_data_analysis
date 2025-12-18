import os
import json
import pandas as pd
import io
from flask import current_app, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Blueprint
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

# Import the core logic classes
from .ops_bootstrap import DataBootstrapper 
from app.app_database.encoder_models import Study, db
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager

ops_bp = Blueprint('ops', __name__)

# ==============================================================================
# 1. PUBLIC / LANDING ROUTES
# ==============================================================================

@ops_bp.route('/')
def index():
    """High-impact landing page."""
    return render_template('index.html')

@ops_bp.route('/robots.txt')
def robots():
    """SEO configuration."""
    return send_from_directory(current_app.static_folder, 'robots.txt')

@ops_bp.route('/documentation')
def documentation():
    """Static documentation page."""
    return render_template('documentation.html', title="Encoding Methodology")

@ops_bp.route('/support', methods=['GET', 'POST'])
def support():
    """Support request form."""
    if request.method == 'POST':
        # Logic to save support ticket would go here
        flash('Support request submitted successfully. We will contact you shortly.', 'success')
        return redirect(url_for('ops.support'))
    return render_template('support.html', title='Request Support')


# ==============================================================================
# 2. SIMULATION & BOOTSTRAP LOGIC (Updated for WorkspaceManager)
# ==============================================================================

@ops_bp.route('/view_study_results/<int:study_id>')
@login_required
def view_study_results(study_id):
    """
    Entry point for the Simulation Tool.
    Checks if 'simulated_{filename}' exists in the TEMP WORKSPACE.
    """
    try:
        study = Study.query.get_or_404(study_id)
        
        # Verify ownership
        if study.user_id != current_user.id:
            flash("Unauthorized access to study.", "danger")
            return redirect(url_for('file_mgt.list_projects'))

        base_name = study.map_filename.replace('.json', '')
        simulated_csv = f"simulated_{base_name}.csv"
        
        # 1. Setup Session for this specific study workflow
        session['filenames'] = {
            'study_id': study.id,
            'project_code': study.project_code,
            'original': f"{base_name}.csv",
            'map': study.map_filename,
            'output': simulated_csv
        }
        
        # 2. Check Workspace for existing results
        # We check if the OUTPUT file already exists in the cache
        existing_output = WorkspaceManager.get_file(current_user.id, study.project_code, simulated_csv)
        
        if existing_output:
            # Results exist in cache -> Go to View
            return redirect(url_for('ops.results'))
        else:
            # No results -> Render Tool to run bootstrap
            return render_template('simulation_tool.html', study=study)
        
    except Exception as e:
        flash(f"Error accessing simulation: {e}", "danger")
        return redirect(url_for('file_mgt.project_admin', study_id=study_id))


@ops_bp.route('/run-bootstrap', methods=['POST'])
@login_required
def run_bootstrap():
    """
    Executes the Bootstrap logic using files FROM THE CACHE.
    Writes the result TO THE CACHE.
    """
    form_data = request.form
    study_id = form_data.get('study_id')
    
    try:
        study = Study.query.get_or_404(study_id)
        if study.user_id != current_user.id:
            raise PermissionError("Unauthorized")

        # Get filenames from form
        csv_filename = form_data.get('csv_file')
        map_filename = form_data.get('map_path')
        output_filename = form_data.get('output_file')

        # 1. READ FROM WORKSPACE
        # We need the actual raw content string to pass to our Bootstrapper
        csv_content = WorkspaceManager.get_file(current_user.id, study.project_code, csv_filename)
        map_content = WorkspaceManager.get_file(current_user.id, study.project_code, map_filename)

        if not csv_content or not map_content:
            flash("Source files missing from workspace. Please sync/reload.", "danger")
            return redirect(url_for('ops.view_study_results', study_id=study.id))

        # 2. Initialize Bootstrapper with IN-MEMORY files
        # We wrap strings in StringIO so pandas can read them like files
        csv_file_obj = io.StringIO(csv_content)
        
        # We need to temporarily save the map content to a dummy file because 
        # DataBootstrapper might expect a file path for JSON loading (depending on implementation).
        # However, it's cleaner if DataBootstrapper accepts a dict. 
        # Assuming DataBootstrapper needs a path, we'll use the Workspace's physical path:
        
        # Get physical paths for the library to use directly
        csv_phys_path = WorkspaceManager.get_file_path(current_user.id, study.project_code, csv_filename)
        map_phys_path = WorkspaceManager.get_file_path(current_user.id, study.project_code, map_filename)
        
        bootstrapper = DataBootstrapper(file_path=csv_phys_path, map_path=map_phys_path, encoding='latin1')
        
        # 3. Run selected method
        bootstrap_type = form_data.get('bootstrap_type')
        new_size = int(form_data.get('new_size'))
        random_state = int(form_data.get('random_state'))

        if bootstrap_type == 'remix':
            bootstrapper.bootstrap_remix(
                new_size=new_size,
                start_remix_col=form_data.get('start_remix_col'),
                end_remix_col=form_data.get('end_remix_col'),
                random_state=random_state
            )
        elif bootstrap_type == 'deep_remix':
            bootstrapper.bootstrap_deep_remix(new_size=new_size, random_state=random_state)
        else:
            bootstrapper.bootstrap(new_size=new_size, random_state=random_state)

        # 4. WRITE RESULT TO WORKSPACE
        # Get the result as a CSV string
        output_csv_string = bootstrapper.get_result_as_csv_string()
        
        # Save to Cache
        WorkspaceManager.save_file(current_user.id, study.project_code, output_filename, output_csv_string)

        flash('Simulation completed. Output saved to workspace.', 'success')
        return redirect(url_for('ops.results'))

    except Exception as e:
        flash(f'Simulation Failed: {e}', 'danger')
        return redirect(url_for('ops.view_study_results', study_id=study_id))


@ops_bp.route('/results')
@login_required
def results():
    """Displays the Results Dashboard."""
    if 'filenames' not in session:
        return redirect(url_for('file_mgt.list_projects'))
    
    # We pass the filenames to the template. 
    # The template will use /view_file/<filename> to fetch content via AJAX/iframe
    return render_template('results.html', title="Simulation Results")


# ==============================================================================
# 3. VIEWER ROUTES (Reading from Cache)
# ==============================================================================

@ops_bp.route('/view_file/<filename>')
@login_required
def view_file(filename):
    """
    Generic viewer for CSV/JSON files located in the current study's workspace.
    """
    if 'filenames' not in session:
        flash("Session expired.", "warning")
        return redirect(url_for('file_mgt.list_projects'))
    
    study_id = session['filenames']['study_id']
    project_code = session['filenames']['project_code']

    # READ FROM WORKSPACE
    content_str = WorkspaceManager.get_file(current_user.id, project_code, filename)

    if not content_str:
        flash(f"File not found in workspace: {filename}", "danger")
        return redirect(url_for('ops.results'))

    formatted_content = None
    file_type = 'unknown'

    try:
        if filename.endswith('.csv'):
            file_type = 'csv'
            # Convert string to DataFrame
            df = pd.read_csv(io.StringIO(content_str))
            
            if len(df) > 500:
                flash("Large file preview truncated (first 500 rows).", "info")
                df = df.head(500)
                
            formatted_content = df.to_html(classes='table table-sm table-striped table-hover', index=False, border=0)
            
        elif filename.endswith('.json'):
            file_type = 'json'
            json_data = json.loads(content_str)
            formatted_content = json.dumps(json_data, indent=4)
        
        return render_template('view_file.html', filename=filename, content=formatted_content, file_type=file_type)

    except Exception as e:
        flash(f"Error parsing file: {e}", "danger")
        return redirect(url_for('ops.results'))


# ==============================================================================
# 4. AJAX UTILITIES (For the Simulation Tool UI)
# ==============================================================================

@ops_bp.route('/preview_csv/<filename>')
@login_required
def preview_csv(filename):
    """AJAX: Returns raw HTML table of the first 10 rows for previews."""
    if 'filenames' not in session:
        return jsonify({'error': 'Session expired'})

    project_code = session['filenames']['project_code']
    content = WorkspaceManager.get_file(current_user.id, project_code, filename)
    
    if not content:
        return jsonify({'error': 'File not found in workspace'})

    try:
        df = pd.read_csv(io.StringIO(content), nrows=10)
        return jsonify({'html': df.to_html(classes='table table-sm', index=False)})
    except Exception as e:
        return jsonify({'error': str(e)})


@ops_bp.route('/generate_and_preview_json/<csv_filename>')
@login_required
def generate_and_preview_json(csv_filename):
    """
    AJAX: Forces regeneration of the JSON Map based on the CSV in workspace.
    Useful if the map file is missing or corrupted.
    """
    if 'filenames' not in session:
        return jsonify({'error': 'Session expired'})

    project_code = session['filenames']['project_code']
    map_filename = csv_filename.replace('.csv', '.json')

    # Get physical paths (Bootstrapper currently needs paths)
    csv_path = WorkspaceManager.get_file_path(current_user.id, project_code, csv_filename)
    map_path = WorkspaceManager.get_file_path(current_user.id, project_code, map_filename)
    
    if not os.path.exists(csv_path):
        return jsonify({'error': 'Source CSV missing'})

    try:
        # Initialize bootstrapper (this auto-creates the JSON map if missing)
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        
        # Read the newly created map back from disk
        with open(map_path, 'r') as f:
            map_data = json.load(f)
            
        return jsonify({'map_data': map_data, 'columns': list(bootstrapper.question_map.keys())})
    except Exception as e:
        return jsonify({'error': str(e)})