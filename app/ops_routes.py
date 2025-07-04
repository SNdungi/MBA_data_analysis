# File: app/ops_routes.py
import os
import json
import pandas as pd
from flask import current_app, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Blueprint
from .ops_bootstrap import DataBootstrapper # Relative import

ops_bp = Blueprint('ops', __name__)



@ops_bp.route('/documentation')
def documentation():
    """Renders the methodology documentation page."""
    return render_template('documentation.html', title="Encoding Methodology")

@ops_bp.route('/')
def index():
    # --- This part is the same ---
    uploads_dir = current_app.config['UPLOADS_FOLDER']
    csv_files = [f for f in os.listdir(uploads_dir) if f.endswith('.csv')]

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
                           csv_files=csv_files,
                           show_last_result_link=has_active_session)

# ... (all other routes remain unchanged) ...

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
        
        # Now read the content of the (newly created or existing) map file
        with open(map_path, 'r') as f:
            map_data = json.load(f)

        return jsonify({
            'map_data': map_data,
            'columns': list(bootstrapper.question_map.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)})



@ops_bp.route('/run', methods=['POST'])
def run_bootstrap():
    form_data = request.form
    try:
        # --- 1. Gather Common Configuration ---
        bootstrap_type = form_data.get('bootstrap_type') # <-- THE NEW KEY
        csv_file = form_data.get('csv_file')
        map_file = form_data.get('map_path')
        output_file = form_data.get('output_file')

        if not bootstrap_type:
            raise ValueError("Bootstrap type was not selected. Please choose Standard or Remix.")

        # These are always required, so we can get them here
        new_size = int(form_data.get('new_size'))
        random_state = int(form_data.get('random_state'))

        # --- 2. Build Paths (same as before) ---
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_file)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_file)
        output_path = os.path.join(current_app.config['GENERATED_FOLDER'], output_file)

        # --- 3. Instantiate and Run based on TYPE ---
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        
        start_remix_col = None # Initialize for graph logic later

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
        
        elif bootstrap_type == 'standard':
            bootstrapper.bootstrap(new_size=new_size, random_state=random_state)

        # --- 4. Save and Generate Graphs (same logic, but now it's safe) ---
        bootstrapper.save_simulated_data(output_path)
        flash('Bootstrap process completed successfully!', 'success')

        graph_paths = []
        all_cols = list(bootstrapper.question_map.keys())
        cols_to_plot = []
        
        if bootstrap_type == 'remix':
            start_index = all_cols.index(start_remix_col)
            if start_index > 0: cols_to_plot.append(all_cols[start_index - 1])
            cols_to_plot.append(start_remix_col)
        else: # Standard bootstrap
            cols_to_plot = all_cols[:2]

        for col in cols_to_plot:
            graph_filename = f"comparison_{col}.png"
            graph_save_path = os.path.join(current_app.config['GRAPHS_FOLDER'], graph_filename)
            bootstrapper.plot_comparison(column_name=col, save_path=graph_save_path)
            graph_paths.append(os.path.join('graphs', graph_filename))
        
        # --- 5. Store results in session (same as before) ---
        session['filenames'] = {
            'original': csv_file,
            'map': map_file,
            'output': output_file,
            'graphs': graph_paths
        }
        return redirect(url_for('ops.results'))

    except (ValueError, TypeError) as e: # Catch specific errors
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
    # This route is correct as is!
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
    # ... your logic is correct ...
    # FIX: Add 'ops.' namespace to url_for
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



# --- NEW ROUTE TO VIEW RAW FILES LIKE JSON ---
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
        # send_from_directory is the secure way to send files
        return send_from_directory(directory, filename, as_attachment=False)
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

# ... (Make sure your other routes are still here) ...