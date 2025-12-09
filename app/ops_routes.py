import os
import json
import pandas as pd
from flask import current_app, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Blueprint
from .ops_bootstrap import DataBootstrapper 
from app.app_encoder.encoder_models import Study, db
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

@ops_bp.route('/guide')
def guide():
    return render_template('analysis_docs.html', title="Results and Summary")

# --- Legacy Simulation Logic (Kept here for specific calculation operations) ---

@ops_bp.route('/view_study_results/<int:study_id>')
def view_study_results(study_id):
    """
    Sets up the session for the simulation tool based on a selected study 
    and redirects to the simulation results page.
    """
    try:
        study = Study.query.get_or_404(study_id)
        base_name = study.map_filename.replace('.json', '')
        
        # Check if simulation exists (optional, could just point to original)
        simulated_csv = f"simulated_{base_name}.csv"
        
        session['filenames'] = {
            'study_id': study.id,
            'original': f"{base_name}.csv",
            'map': study.map_filename,
            'output': simulated_csv,
            'graphs': [] 
        }
        return render_template('index.html', studies=[study], show_last_result_link=True) 
        # Note: We reuse index.html here purely for the bootstrap tool interface if needed, 
        # or you might want to redirect straight to 'results' if data exists.
        
    except Exception as e:
        flash(f"Error accessing simulation: {e}", "danger")
        return redirect(url_for('file_mgt.dashboard'))

@ops_bp.route('/run-bootstrap', methods=['POST'])
def run_bootstrap():
    """Handles the actual Bootstrap calculation."""
    form_data = request.form
    try:
        bootstrap_type = form_data.get('bootstrap_type')
        csv_file = form_data.get('csv_file')
        map_file = form_data.get('map_path')
        output_file = form_data.get('output_file')
        study_id = form_data.get('study_id')

        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_file)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_file)
        output_path = os.path.join(current_app.config['GENERATED_FOLDER'], output_file)

        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        
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
        else:
            bootstrapper.bootstrap(new_size=int(form_data.get('new_size')), random_state=int(form_data.get('random_state')))

        bootstrapper.save_simulated_data(output_path)
        flash('Bootstrap simulation completed!', 'success')
        
        session['filenames'] = {
            'study_id': study_id,
            'original': csv_file,
            'map': map_file,
            'output': output_file,
        }
        return redirect(url_for('ops.results'))

    except Exception as e:
        flash(f'Simulation Error: {e}', 'danger')
        return redirect(url_for('file_mgt.dashboard'))

@ops_bp.route('/results')
def results():
    if 'filenames' not in session:
        return redirect(url_for('file_mgt.dashboard'))
    return render_template('results.html', title="Results")

# --- Helper Routes for the Simulation Tool (AJAX) ---

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