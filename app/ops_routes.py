# File: app/ops_routes.py
import os
import json
import pandas as pd
from flask import current_app, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Blueprint, send_file
from .ops_bootstrap import DataBootstrapper # Relative import
from app.app_encoder.encoder_models import Study
from app.app_encoder.encoder_manager import EncodingConfigManager
from werkzeug.utils import secure_filename
from werkzeug.exceptions import NotFound
import shutil # Import shutil for directory operations
from app.app_encoder.encoder_models import db, Study,EncoderDefinition



ops_bp = Blueprint('ops', __name__)



@ops_bp.route('/documentation')
def documentation():
    """Renders the methodology documentation page."""
    return render_template('documentation.html', title="Encoding Methodology")

@ops_bp.route('/guide')
def guide():
    """Renders the methodology documentation page."""
    return render_template('analysis_docs.html', title="Results and Summary")

@ops_bp.route('/')
def index():
    # --- This part is the same ---
    uploads_dir = current_app.config['UPLOADS_FOLDER']
    csv_files = [f for f in os.listdir(uploads_dir) if f.endswith('.csv')]
    all_studies = Study.query.order_by(Study.created_at.desc()).all()

    # --- NEW ROBUST LOGIC TO FIND AND RECONSTRUCT LAST SESSION ---
    
    # First, we check if a valid session already exists. If so, we're good.
    has_active_session = 'filenames' in session and session['filenames'].get('output')

    # If no active session, we try to find the last run from the filesystem
    if not has_active_session:
        generated_dir = current_app.config['GENERATED_FOLDER']
        last_simulated_file = None
        latest_time = 0

        if os.path.exists(generated_dir):
            try:
                # Find the most recently modified simulated CSV
                for filename in os.listdir(generated_dir):
                    if filename.startswith('simulated_') and filename.endswith('.csv'):
                        file_path = os.path.join(generated_dir, filename)
                        mod_time = os.path.getmtime(file_path)
                        if mod_time > latest_time:
                            latest_time = mod_time
                            last_simulated_file = filename
            except FileNotFoundError:
                # This can happen in a race condition, so we handle it gracefully
                pass

        # If we found a file, reconstruct the session data
        if last_simulated_file:
            print(f"--- Reconstructing session from last file: {last_simulated_file} ---")
            # Infer original filenames from the simulated filename
            # e.g., 'simulated_my_data.csv' -> 'my_data.csv'
            base_name = last_simulated_file.replace('simulated_', '').replace('.csv', '')
            original_csv = f"{base_name}.csv"
            json_map = f"{base_name}.json"
            
            # Reconstruct the filenames dictionary and save it to the session
            # We assume no graphs for a reconstructed session for simplicity,
            # but they will still be on disk.
            session['filenames'] = {
                'original': original_csv,
                'map': json_map,
                'output': last_simulated_file,
                'graphs': [] # Graphs are not part of the reconstructed session link
            }
            has_active_session = True

    return render_template('index.html',
                           studies=all_studies,
                           csv_files=csv_files,
                           show_last_result_link=has_active_session)

@ops_bp.route('/create_study', methods=['POST'])
def create_study():
    """Handles the form submission for creating a new study, with an option to clone encoders."""
    study_name = request.form.get('study_name')
    uploaded_file = request.files.get('source_csv')
    clone_from_study_id = request.form.get('clone_from_study_id') # Get the new optional field

    if not study_name or not uploaded_file or uploaded_file.filename == '':
        flash('Study Name and a CSV file are required.', 'danger')
        return redirect(url_for('ops.index'))
    
    if not uploaded_file.filename.lower().endswith('.csv'):
        flash('Invalid file type. Please upload a CSV file.', 'danger')
        return redirect(url_for('ops.index'))

    try:
        secure_base_name = secure_filename(study_name.lower().replace(' ', '_'))
        csv_filename = f"{secure_base_name}.csv"
        map_filename = f"{secure_base_name}.json"

        if Study.query.filter_by(name=study_name).first() or Study.query.filter_by(map_filename=map_filename).first():
             flash(f"A study named '{study_name}' or with a conflicting filename already exists.", 'warning')
             return redirect(url_for('ops.index'))

        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
        uploaded_file.save(csv_path)

        # Create the new study object BUT DON'T COMMIT YET
        new_study = Study(
            name=study_name,
            map_filename=map_filename,
            topic=request.form.get('study_topic', ''),
            description=request.form.get('study_description', '')
        )
        db.session.add(new_study)
        # Flush the session to get the new_study.id for the cloned definitions
        db.session.flush()

        # --- NEW CLONING LOGIC ---
        source_study_name = None
        if clone_from_study_id and clone_from_study_id.isdigit():
            source_study = Study.query.get(int(clone_from_study_id))
            if source_study:
                source_study_name = source_study.name
                # Iterate and create deep copies of each definition
                for source_def in source_study.definitions:
                    new_def = EncoderDefinition(
                        study_id=new_study.id, # Link to the NEW study
                        prototype_id=source_def.prototype_id,
                        name=source_def.name,
                        configuration=source_def.configuration # This copies the JSON data
                    )
                    db.session.add(new_def)
                print(f"Cloning {len(source_study.definitions)} definitions from '{source_study.name}' to '{new_study.name}'.")

        # Now commit the new study and all cloned definitions in one transaction
        db.session.commit()
        
        if source_study_name:
            flash(f"Study '{study_name}' created successfully, cloning definitions from '{source_study_name}'.", 'success')
        else:
            flash(f"Study '{study_name}' created successfully with a blank slate!", 'success')

    except Exception as e:
        db.session.rollback() # Rollback in case of an error during cloning
        flash(f"An error occurred while creating the study: {e}", 'danger')

    return redirect(url_for('ops.index'))



# === NEW ROUTE TO VIEW RESULTS FOR A SPECIFIC STUDY ===
@ops_bp.route('/view_study_results/<int:study_id>')
def view_study_results(study_id):
    """
    Finds a study, checks for its simulated data file, reconstructs the
    session, and redirects to the results page.
    """
    try:
        study = Study.query.get_or_404(study_id)

        base_name = study.map_filename.replace('.json', '')
        original_csv = f"{base_name}.csv"
        simulated_csv = f"simulated_{base_name}.csv"
        simulated_path = os.path.join(current_app.config['GENERATED_FOLDER'], simulated_csv)

        if not os.path.exists(simulated_path):
            flash(f"No simulation results found for study '{study.name}'. Please run a simulation first.", 'warning')
            return redirect(url_for('ops.index'))

        # --- THIS IS THE FIX ---
        # Reconstruct the session dictionary, now including the study_id
        session['filenames'] = {
            'study_id': study.id, # <-- ADD THIS LINE
            'original': original_csv,
            'map': study.map_filename,
            'output': simulated_csv,
            'graphs': [] 
        }

        return redirect(url_for('ops.results'))

    except NotFound:
        flash("The requested study does not exist.", "danger")
        return redirect(url_for('ops.index'))
    except Exception as e:
        flash(f"An error occurred while trying to view results: {e}", "danger")
        return redirect(url_for('ops.index'))



@ops_bp.route('/preview_csv/<filename>')
def preview_csv(filename):
    """Reads the first few rows of a CSV and returns it as HTML."""
    file_path = os.path.join(current_app.config['UPLOADS_FOLDER'], filename)
    try:
        df = pd.read_csv(file_path, encoding='latin1', nrows=10)
        df_html = df.to_html(classes='table table-sm table-striped table-hover', index=False, border=0)
        return jsonify({'html': df_html})
    except Exception as e:
        return jsonify({'error': f'Could not read file: {e}'})

# --- NEW PREVIEW ROUTE ---
@ops_bp.route('/generate_and_preview_json/<csv_filename>')
def generate_and_preview_json(csv_filename):
    """Generates the map if needed, then returns its content and keys."""
    map_filename = csv_filename.replace('.csv', '.json')
    map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_filename)
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
    try:
        # Instantiating the class handles creation logic automatically
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        with open(map_path, 'r') as f:
            map_data = json.load(f)

        return jsonify({
            'map_data': map_data,
            'columns': list(bootstrapper.question_map.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@ops_bp.route('/run-bootstrap', methods=['POST'])
def run_bootstrap():
    form_data = request.form
    try:
        # --- 1. Gather Common Configuration ---
        bootstrap_type = form_data.get('bootstrap_type')
        csv_file = form_data.get('csv_file')
        map_file = form_data.get('map_path')
        output_file = form_data.get('output_file')
        study_id = form_data.get('study_id')

        if not bootstrap_type:
            raise ValueError("Bootstrap type was not selected.")

        new_size = int(form_data.get('new_size'))
        random_state = int(form_data.get('random_state'))

        # --- 2. Build Paths ---
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_file)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_file)
        output_path = os.path.join(current_app.config['GENERATED_FOLDER'], output_file)

        # --- 3. Instantiate and Run based on TYPE ---
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        
        start_remix_col = None

        if bootstrap_type == 'remix':
            start_remix_col = form_data.get('start_remix_col')
            end_remix_col = form_data.get('end_remix_col')
            if not start_remix_col or not end_remix_col:
                raise ValueError("For Remix Bootstrap, you must select a start and end column.")
            
            bootstrapper.bootstrap_remix(
                new_size=new_size,
                start_remix_col=start_remix_col,
                end_remix_col=end_remix_col,
                random_state=random_state
            )
        
        # --- NEW LOGIC FOR DEEP REMIX ---
        elif bootstrap_type == 'deep_remix':
            bootstrapper.bootstrap_deep_remix(
                new_size=new_size, 
                random_state=random_state
            )

        elif bootstrap_type == 'standard':
            bootstrapper.bootstrap(new_size=new_size, random_state=random_state)

        # --- (Rest of the function is unchanged) ---
        bootstrapper.save_simulated_data(output_path)
        flash('Bootstrap process completed successfully!', 'success')
        
        session['filenames'] = {
            'study_id': study_id,
            'original': csv_file,
            'map': map_file,
            'output': output_file,
        }
        return redirect(url_for('ops.results'))

    except (ValueError, TypeError) as e:
        flash(f'Configuration Error: {e}', 'danger')
        return redirect(url_for('ops.index'))
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        return redirect(url_for('ops.index'))

@ops_bp.route('/results')
def results():
    if 'filenames' not in session:
        # FIX: Add 'ops.' namespace to url_for
        return redirect(url_for('ops.index'))
    return render_template('results.html', title="Results")



@ops_bp.route('/get_columns/<csv_file>')
def get_columns(csv_file):
    map_filename = csv_file.replace('.csv', '.json')
    map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_filename)
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_file)
    try:
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        return jsonify({'columns': list(bootstrapper.question_map.keys())})
    except Exception as e:
        return jsonify({'error': str(e)})


@ops_bp.route('/recreate_map', methods=['POST'])
def recreate_map():
    map_file = request.form.get('map_path')
    if not map_file:
        flash('Please select a CSV file first.', 'warning')
        return redirect(url_for('ops.index'))
    map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_file)
    try:
        if os.path.exists(map_path):
            os.remove(map_path)
            flash(f"Deleted '{map_file}'. It will be regenerated on CSV selection.", 'success')
        else:
            flash(f"'{map_file}' did not exist; it will be created on selection.", 'info')
    except Exception as e:
        flash(f"Error: {e}", 'danger')
    return redirect(url_for('ops.index'))



@ops_bp.route('/view_file/<type>/<filename>')
def view_file(type, filename):
    """
    Serves a raw file (like JSON or plain text) from the appropriate directory.
    This is used for viewing the generated JSON map.
    """
    if type == 'generated':
        directory = current_app.config['GENERATED_FOLDER']
    elif type == 'uploads':
        directory = current_app.config['UPLOADS_FOLDER']
    else:
        flash('Invalid file type specified.', 'danger')
        return redirect(url_for('ops.results'))

    try:
        return send_from_directory(directory, filename, as_attachment=request.args.get('as_attachment', default=False, type=bool))
    except FileNotFoundError:
        flash(f"File not found: {filename}", 'danger')
        return redirect(url_for('ops.results'))


@ops_bp.route('/view_df/<filename>')
def view_df(filename):
    """Renders a CSV file as an HTML table."""
    type = request.args.get('type', 'uploads')
    directory = current_app.config['GENERATED_FOLDER'] if type == 'generated' else current_app.config['UPLOADS_FOLDER']
    file_path = os.path.join(directory, filename)
    try:
        df = pd.read_csv(file_path, encoding='latin1')
        df_html = df.to_html(classes='table table-striped table-hover', index=False, border=0)
        return render_template('view_df.html', df_html=df_html, filename=filename, title=f"View: {filename}")
    except Exception as e:
        flash(f"Could not display file: {e}", "danger")
        return redirect(url_for('ops.results'))


# =============================================================================
# NEW HOUSEKEEPING ROUTES
# =============================================================================

def _clear_folder_contents(folder_path):
    """Helper function to delete all files and subdirectories in a folder."""
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')


@ops_bp.route('/housekeeping')
def housekeeping():
    """Renders the data cleanup page."""
    studies = Study.query.order_by(Study.name).all()
    return render_template('housekeeping.html', studies=studies, title="Housekeeping")


@ops_bp.route('/perform_cleanup', methods=['POST'])
def perform_cleanup():
    """Handles the deletion of studies and/or all associated data."""
    action = request.form.get('action')

    try:
        if action == 'delete_one':
            study_id = request.form.get('study_id')
            if not study_id:
                flash('You must select a study to delete.', 'warning')
                return redirect(url_for('ops.housekeeping'))

            study_to_delete = Study.query.get_or_404(study_id)
            study_name = study_to_delete.name
            
            # 1. Delete associated files from disk
            base_name = study_to_delete.map_filename.replace('.json', '')
            files_to_check = [
                os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv"),
                os.path.join(current_app.config['GENERATED_FOLDER'], study_to_delete.map_filename),
                os.path.join(current_app.config['GENERATED_FOLDER'], f"{base_name}_encoded.csv"),
                os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv")
            ]
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # 2. Delete the study from the database (cascades will handle children)
            db.session.delete(study_to_delete)
            db.session.commit()
            
            flash(f"Successfully deleted study '{study_name}' and all its associated data.", 'success')

        elif action == 'delete_all':
            # 1. Delete all records from the database
            # Deleting all studies will cascade and delete all children definitions and encodings
            num_studies = db.session.query(Study).delete()
            db.session.commit()

            # 2. Clear the contents of the data folders
            _clear_folder_contents(current_app.config['UPLOADS_FOLDER'])
            _clear_folder_contents(current_app.config['GENERATED_FOLDER'])
            _clear_folder_contents(current_app.config['GRAPHS_FOLDER'])
            
            flash(f"Successfully purged {num_studies} studies and all associated files.", 'success')
            # Also clear the session in case it holds stale data
            session.clear()

        else:
            flash('Invalid cleanup action specified.', 'danger')

    except NotFound:
        flash("The study you tried to delete could not be found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred during cleanup: {e}", "danger")

    return redirect(url_for('ops.housekeeping'))

# In app/ops_routes.py, add these imports at the top
import io
import zipfile

# ... (keep all existing routes) ...

# =============================================================================
# NEW EXPORT/IMPORT ROUTES
# =============================================================================

@ops_bp.route('/export_study/<int:study_id>')
def export_study(study_id):
    """
    Finds a study, gathers all its associated files, zips them in memory,
    and sends the zip file to the user for download.
    """
    try:
        study = Study.query.get_or_404(study_id)
        
        # --- 1. Define file paths based on study data ---
        base_name = study.map_filename.replace('.json', '')
        secure_zip_name = f"{secure_filename(study.name.lower().replace(' ', '_'))}.zip"

        files_to_zip = {
            # "filename_in_zip": "full_path_on_server"
            f"{base_name}.csv": os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv"),
            study.map_filename: os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename),
            f"simulated_{base_name}.csv": os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv"),
            # You could add logic here to find and include graph files too
        }

        # --- 2. Create a zip file in memory ---
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename_in_zip, full_path in files_to_zip.items():
                if os.path.exists(full_path):
                    # zf.write adds the file from full_path into the zip
                    # using the name specified by filename_in_zip
                    zf.write(full_path, arcname=filename_in_zip)
                else:
                    print(f"Warning: File not found and will be skipped in export: {full_path}")
        
        memory_file.seek(0) # Rewind the buffer to the beginning

        # In the export_study route...

        # --- 3. Send the in-memory zip file to the user ---
        # The send_file function is perfect for this.
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=secure_zip_name
        )

    except NotFound:
        flash("The study you tried to export could not be found.", "danger")
        return redirect(url_for('ops.housekeeping'))
    except Exception as e:
        flash(f"An error occurred during the export process: {e}", "danger")
        return redirect(url_for('ops.housekeeping'))
