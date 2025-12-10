import os
import json
import pandas as pd
from flask import current_app, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Blueprint
from .ops_bootstrap import DataBootstrapper 
from app.app_database.encoder_models import Study, db
from werkzeug.utils import secure_filename
from werkzeug.exceptions import NotFound

ops_bp = Blueprint('ops', __name__)

@ops_bp.route('/')
def index():
    """Redirects root to the new File Management Dashboard."""
    return redirect(url_for('file_mgt.list_projects'))

@ops_bp.route('/documentation')
def documentation():
    return render_template('documentation.html', title="Encoding Methodology")

# --- Simulation Logic ---

@ops_bp.route('/view_study_results/<int:study_id>')
def view_study_results(study_id):
    """
    Entry point for the Legacy Simulation tool.
    1. Sets up session for the specific study.
    2. Checks if results exist.
       - If YES: Redirects to Results page.
       - If NO: Renders the Simulation Tool form to generate them.
    """
    try:
        study = Study.query.get_or_404(study_id)
        base_name = study.map_filename.replace('.json', '')
        simulated_csv = f"simulated_{base_name}.csv"
        
        # 1. Setup Session
        session['filenames'] = {
            'study_id': study.id,
            'original': f"{base_name}.csv",
            'map': study.map_filename,
            'output': simulated_csv,
            'graphs': [] 
        }
        
        # 2. Check if output exists
        sim_path = os.path.join(current_app.config['GENERATED_FOLDER'], simulated_csv)
        
        if os.path.exists(sim_path):
            # Results exist -> Go to View
            return redirect(url_for('ops.results'))
        else:
            # No results -> Go to Tool to run bootstrap
            # We pass 'study' so the template knows what we are working on
            return render_template('simulation_tool.html', study=study)
        
    except Exception as e:
        flash(f"Error accessing simulation: {e}", "danger")
        return redirect(url_for('file_mgt.project_admin', study_id=study_id))

@ops_bp.route('/run-bootstrap', methods=['POST'])
def run_bootstrap():
    """Handles the actual Bootstrap calculation."""
    form_data = request.form
    try:
        # Get data from form
        bootstrap_type = form_data.get('bootstrap_type')
        csv_file = form_data.get('csv_file')
        map_file = form_data.get('map_path')
        output_file = form_data.get('output_file')
        study_id = form_data.get('study_id')

        # Paths
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_file)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_file)
        output_path = os.path.join(current_app.config['GENERATED_FOLDER'], output_file)

        # Initialize Bootstrapper
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        
        # Run selected method
        if bootstrap_type == 'remix':
            bootstrapper.bootstrap_remix(
                new_size=int(form_data.get('new_size')),
                start_remix_col=form_data.get('start_remix_col'),
                end_remix_col=form_data.get('end_remix_col'),
                random_state=int(form_data.get('random_state'))
            )
        elif bootstrap_type == 'deep_remix':
            bootstrapper.bootstrap_deep_remix(
                new_size=int(form_data.get('new_size')), 
                random_state=int(form_data.get('random_state'))
            )
        else: # Standard
            bootstrapper.bootstrap(new_size=int(form_data.get('new_size')), random_state=int(form_data.get('random_state')))

        # Save
        bootstrapper.save_simulated_data(output_path)
        flash('Bootstrap simulation completed successfully.', 'success')
        
        # Refresh session just in case
        session['filenames'] = {
            'study_id': study_id,
            'original': csv_file,
            'map': map_file,
            'output': output_file,
        }
        return redirect(url_for('ops.results'))

    except Exception as e:
        flash(f'Simulation Error: {e}', 'danger')
        # On error, go back to the tool page for this study
        return redirect(url_for('ops.view_study_results', study_id=form_data.get('study_id')))

@ops_bp.route('/results')
def results():
    if 'filenames' not in session:
        return redirect(url_for('file_mgt.list_projects'))
    return render_template('results.html', title="Results")

# --- Viewer Routes ---

@ops_bp.route('/view_file/<filename>')
def view_file(filename):
    folder_type = request.args.get('folder', 'uploads')
    directory = current_app.config['GENERATED_FOLDER'] if folder_type == 'generated' else current_app.config['UPLOADS_FOLDER']
    file_path = os.path.join(directory, filename)
    
    if not os.path.exists(file_path):
        flash(f"File not found: {filename}", "danger")
        return redirect(url_for('ops.results'))

    content = None
    file_type = 'unknown'

    try:
        if filename.endswith('.csv'):
            file_type = 'csv'
            df = pd.read_csv(file_path, encoding='latin1')
            if len(df) > 500:
                flash("File too large. Showing first 500 rows.", "info")
                df = df.head(500)
            content = df.to_html(classes='table table-sm table-striped table-hover', index=False, border=0)
            
        elif filename.endswith('.json'):
            file_type = 'json'
            with open(file_path, 'r') as f:
                json_data = json.load(f)
            content = json.dumps(json_data, indent=4)
        
        return render_template('view_file.html', filename=filename, content=content, file_type=file_type)

    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for('ops.results'))

# --- AJAX Routes for Tool Logic ---

@ops_bp.route('/preview_csv/<filename>')
def preview_csv(filename):
    file_path = os.path.join(current_app.config['UPLOADS_FOLDER'], filename)
    try:
        df = pd.read_csv(file_path, encoding='latin1', nrows=10)
        return jsonify({'html': df.to_html(classes='table table-sm', index=False)})
    except Exception as e:
        return jsonify({'error': str(e)})

@ops_bp.route('/generate_and_preview_json/<csv_filename>')
def generate_and_preview_json(csv_filename):
    map_filename = csv_filename.replace('.csv', '.json')
    map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_filename)
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
    try:
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        with open(map_path, 'r') as f:
            return jsonify({'map_data': json.load(f), 'columns': list(bootstrapper.question_map.keys())})
    except Exception as e:
        return jsonify({'error': str(e)})