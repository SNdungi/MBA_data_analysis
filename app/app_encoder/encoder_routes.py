import os
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.app_encoder.encoder_manager import EncodingConfigManager
from app.ops_bootstrap import DataBootstrapper # Needed to get the question map
from app.app_encoder.encoder import DataEncoder  # The main encoding engine class

encoding_bp = Blueprint('encoding', __name__, url_prefix='/encoding',template_folder='templates/encoder')

@encoding_bp.route('/configure/<csv_filename>')
def configure(csv_filename):
    """The main UI page for configuring data encoding for a specific dataset."""
    map_filename = csv_filename.replace('.csv', '.json')
    map_path = os.path.join(current_app.config['GENERATED_FOLDER'], map_filename)
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)

    try:
        # 1. Get the question map (q1: "Full Question")
        # Instantiating the bootstrapper is a neat way to ensure the map is created
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        question_map = bootstrapper.question_map

        # 2. Initialize the DB configuration for this map
        EncodingConfigManager.initialize_config_for_map(map_filename, question_map)

        # 3. Get the current configuration state from the DB
        configs = EncodingConfigManager.get_config_for_map(map_filename)

        # 4. Get a data preview
        df_preview = pd.read_csv(csv_path, encoding='latin1', nrows=5)
        
        return render_template(
            'encoder.html',
            title=f"Configure Encoding for {csv_filename}",
            configs=configs,
            csv_filename=csv_filename,
            map_filename=map_filename,
            df_preview_html=df_preview.to_html(classes='table table-sm table-striped', index=False, border=0)
        )
    except Exception as e:
        flash(f"Error loading configuration page: {e}", "danger")
        return redirect(url_for('ops.index'))


@encoding_bp.route('/update', methods=['POST'])
def update():
    """Handles the form submission to update the encoding configuration."""
    form_data = request.form
    map_filename = form_data.get('map_filename')
    csv_filename = form_data.get('csv_filename')

    try:
        # --- Handle Bulk Likert Update ---
        if 'bulk-update-submit' in form_data:
            start_key = form_data.get('bulk_start_key')
            end_key = form_data.get('bulk_end_key')
            scale_type = form_data.get('bulk_scale_type')
            is_reverse = 'bulk_is_reverse' in form_data

            EncodingConfigManager.bulk_update_likert_config(
                map_filename, start_key, end_key, scale_type, is_reverse
            )
            flash('Bulk Likert configuration updated successfully!', 'success')
        
        # --- Handle Individual Row Updates ---
        elif 'save-all-submit' in form_data:
            # Group form data by config ID
            updates = {}
            for key, value in form_data.items():
                if key.startswith('encoder_type_'):
                    config_id = int(key.split('_')[-1])
                    if config_id not in updates: updates[config_id] = {}
                    updates[config_id]['encoder_type'] = value
                elif key.startswith('ordinal_order_'):
                    config_id = int(key.split('_')[-1])
                    if config_id not in updates: updates[config_id] = {}
                    updates[config_id]['ordinal_order'] = value

            # Process the grouped updates
            for config_id, values in updates.items():
                encoder_type = values.get('encoder_type')
                config_details = {}
                if encoder_type == 'Ordinal':
                    order_list = [item.strip() for item in values.get('ordinal_order', '').split(',') if item.strip()]
                    config_details = {"order": order_list}
                
                EncodingConfigManager.update_column_config(config_id, encoder_type, config_details)
            
            flash('All individual configurations saved successfully!', 'success')

    except Exception as e:
        flash(f"Error updating configuration: {e}", 'danger')

    return redirect(url_for('encoding.configure', csv_filename=csv_filename))
 
@encoding_bp.route('/run', methods=['POST'])
def run_encoding():
    """
    Executes the data encoding process using the saved configuration.
    This is the route that finally uses the DataEncoder class.
    """
    form_data = request.form
    csv_filename = form_data.get('csv_filename')
    map_filename = form_data.get('map_filename')
    
    # Define output file names
    base_name = csv_filename.replace('.csv', '')
    encoded_csv_filename = f"{base_name}_encoded.csv"
    codebook_filename = f"{base_name}_codebook.md"

    try:
        # 1. Generate the final configuration dictionary from the database
        print("--- Generating config for DataEncoder class ---")
        encoder_config = EncodingConfigManager.generate_encoder_class_config(map_filename)

        # 2. Load the raw data to be encoded
        print("--- Loading raw data for encoding ---")
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
        raw_df = pd.read_csv(csv_path, encoding='latin1')
        
        # 3. Instantiate and run the DataEncoder engine
        print("--- Instantiating and running DataEncoder ---")
        engine = DataEncoder(dataframe=raw_df, config=encoder_config)
        encoded_dataframe, codebook_string = engine.encode()
        
        # 4. Save the artifacts (the final products)
        print("--- Saving encoded data and codebook ---")
        encoded_csv_path = os.path.join(current_app.config['GENERATED_FOLDER'], encoded_csv_filename)
        codebook_path = os.path.join(current_app.config['GENERATED_FOLDER'], codebook_filename)
        
        encoded_dataframe.to_csv(encoded_csv_path, index=False)
        with open(codebook_path, 'w', encoding='utf-8') as f:
            f.write(codebook_string)
            
        flash('Data successfully encoded! You can now view the results.', 'success')
        
        # We can create a simple results page for this, or redirect back to the config page
        # Let's create a results page for clarity.
        return redirect(url_for('encoding.encoding_results',
                                encoded_csv=encoded_csv_filename,
                                codebook=codebook_filename))

    except Exception as e:
        flash(f"A critical error occurred during encoding: {e}", "danger")
        return redirect(url_for('encoding.configure', csv_filename=csv_filename))

# --- NEW ROUTE FOR VIEWING ENCODING RESULTS ---
@encoding_bp.route('/results')
def encoding_results():
    """Displays links to the newly created encoded file and codebook."""
    encoded_csv = request.args.get('encoded_csv')
    codebook = request.args.get('codebook')
    
    return render_template('encoding_results.html',
                           title="Encoding Complete",
                           encoded_csv=encoded_csv,
                           codebook=codebook)