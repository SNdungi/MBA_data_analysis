import os
import pandas as pd
<<<<<<< HEAD
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
=======
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, json
from app.app_encoder.encoder_manager import EncodingConfigManager
from app.ops_bootstrap import DataBootstrapper
from app.app_encoder.encoder import DataEncoder
from app.app_encoder.encoder_models import db, Study, EncoderPrototype, EncoderDefinition
from markupsafe import Markup

# The template_folder is set to 'templates' so we can use the 'encoding/' prefix in render_template calls.
encoding_bp = Blueprint('encoding', __name__, template_folder='templates/encoder')

def _get_study_and_check_files(study_id):
    """Helper to get study and check for result files."""
    study = Study.query.get_or_404(study_id)
    base_name = study.map_filename.replace('.json', '')

    encoded_csv_filename = f"{base_name}_encoded.csv"
    codebook_filename = f"{base_name}_codebook.json" # Use .json extension

    generated_folder = current_app.config['GENERATED_FOLDER']
    encoded_csv_path = os.path.join(generated_folder, encoded_csv_filename)
    codebook_path = os.path.join(generated_folder, codebook_filename)
    
    return study, os.path.exists(encoded_csv_path) and os.path.exists(codebook_path)

@encoding_bp.route('/definitions/<int:study_id>')
def definitions(study_id):
    """(Step 1) UI for creating and managing Encoder Definitions."""
    try:
        study, result_files_exist = _get_study_and_check_files(study_id)
        csv_filename = study.map_filename.replace('.json', '.csv')
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)

        # Fetch all necessary data for the UI
        study_definitions = EncoderDefinition.query.filter_by(study_id=study.id).order_by(EncoderDefinition.name).all()
        prototypes = EncoderPrototype.query.all()
        df_preview = pd.read_csv(csv_path, encoding='latin1', nrows=100)
        
        return render_template(
            'encoder_definitions.html',
            title=f"Define: {study.name}",
            study=study,
            definitions=study_definitions,
            prototypes=prototypes,
            df_preview_html=df_preview.to_html(classes='table table-sm', index=False, border=0),
            result_files_exist=result_files_exist
        )
    except Exception as e:
        flash(f"Error loading definitions page: {e}", "danger")
        return redirect(url_for('ops.index')) # Redirect to a safe main page

@encoding_bp.route('/assign/<int:study_id>')
def assign(study_id):
    """(Step 2) UI for assigning Definitions to data columns."""
    try:
        study, result_files_exist = _get_study_and_check_files(study_id)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename)
        csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], study.map_filename.replace('.json', '.csv'))
        
        # Get question map and initialize columns if they don't exist for this study
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        EncodingConfigManager.initialize_columns_for_study(study, bootstrapper.question_map)

        # Fetch data for the assignment table and dropdown
        column_configs = EncodingConfigManager.get_column_configs_for_study(study.id)
        study_definitions = EncoderDefinition.query.filter_by(study_id=study.id).order_by(EncoderDefinition.name).all()

        return render_template(
            'encoder_assign.html',
            title=f"Assign: {study.name}",
            study=study,
            configs=column_configs,
            definitions=study_definitions,
            result_files_exist=result_files_exist
        )
    except Exception as e:
        flash(f"Error loading assignment page: {e}", "danger")
        return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/create_definition', methods=['POST'])
def create_definition():
    """Handles the form submission for creating a new EncoderDefinition."""
    study_id = request.form.get('study_id')
    try:
        prototype_id = request.form.get('prototype_id')
        definition_name = request.form.get('definition_name')
        config_json_str = request.form.get('configuration')

        if not all([study_id, prototype_id, definition_name, config_json_str]):
            raise ValueError("All fields are required to create a definition.")
        
        # Validate and parse the JSON configuration
        try:
            configuration = json.loads(config_json_str)
        except json.JSONDecodeError:
            raise ValueError("The provided configuration is not valid JSON.")
        
        EncodingConfigManager.create_encoder_definition(
            study_id=study_id,
            prototype_id=prototype_id,
            name=definition_name,
            configuration=configuration
        )
        flash(f"Encoder Definition '{definition_name}' created successfully.", "success")
    except Exception as e:
        flash(f"Error creating definition: {e}", "danger")
    
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/assign_definition', methods=['POST'])
def assign_definition():
    """Handles assigning a saved definition to one or more columns."""
    study_id = request.form.get('study_id')
    try:
        definition_id = request.form.get('definition_id')
        column_ids = request.form.getlist('column_ids')

        if not definition_id or not column_ids:
            raise ValueError("You must select a definition and at least one column to assign.")

        EncodingConfigManager.assign_encoder_to_columns(column_ids, definition_id)
        flash(f"Successfully assigned definition to {len(column_ids)} columns.", "success")
    except Exception as e:
        flash(f"Error assigning definition: {e}", "danger")

    return redirect(url_for('encoding.assign', study_id=study_id))

# In app/app_encoder/encoder_routes.py

# In app/app_encoder/encoder_routes.py

@encoding_bp.route('/run-encoding', methods=['POST'])
def run_encoding():
    """
    (Step 3) Executes data encoding, persists learned value maps to the database,
    and saves the encoded data and codebook.
    """
    study_id = request.form.get('study_id')
    study = Study.query.get_or_404(study_id)
    
    # 1. DEFINE ALL FILENAMES BASED ON STUDY
    base_name = study.map_filename.replace('.json', '')
    
    # Input file for this process is the simulated data
    simulated_filename = f"simulated_{base_name}.csv"
    
    # Output files for this process
    encoded_csv_filename = f"{base_name}_encoded.csv"
    codebook_filename = f"{base_name}_codebook.json"
    
    # Define full paths to the files
    generated_folder = current_app.config['GENERATED_FOLDER']
    simulated_path = os.path.join(generated_folder, simulated_filename)
    map_path = os.path.join(generated_folder, study.map_filename)

    try:
        # 2. ENSURE THE SIMULATED INPUT FILE EXISTS
        if not os.path.exists(simulated_path):
            flash(f"Simulated data file '{simulated_filename}' not found. Please run a bootstrap simulation first.", "danger")
            return redirect(url_for('encoding.assign', study_id=study.id))

        # 3. PREPARE THE RAW DATAFRAME FOR THE ENCODER
        # The encoder class expects column names to be the short keys ('q1', 'q2', etc.)
        with open(map_path, 'r', encoding='utf-8') as f:
            question_map = json.load(f)
        column_keys = list(question_map.keys())
        
        # Load the simulated CSV, forcing the column names to be our short keys
        raw_df = pd.read_csv(simulated_path, encoding='latin1', header=0, names=column_keys)

        # 4. GENERATE CONFIG AND RUN THE ENCODER
        # This config tells the encoder which definition to use for each column
        encoder_config = EncodingConfigManager.generate_encoder_class_config(study.id)
        engine = DataEncoder(dataframe=raw_df, config=encoder_config)
        
        # The .encode() method now returns the learned maps as its fourth value
        encoded_dataframe, codebook_dictionary, warnings, learned_maps = engine.encode()
        
        # 5. PERSIST THE LEARNED MAPS BACK TO THE DATABASE
        # This is the crucial step that updates the definitions for Nominal/Binary encoders
        if learned_maps:
            EncodingConfigManager.update_definition_configurations(study.id, learned_maps)
            flash("Encoder definitions have been successfully updated with learned value maps.", "info")

        # 6. HANDLE WARNINGS AND PROVIDE FEEDBACK
        if warnings:
            flash("Encoding complete, but with warnings. Please review the messages below.", "warning")
            for warning in warnings:
                unmapped_str = ", ".join([f"'{v}'" for v in warning['unmapped_values']])
                message = (
                    f"<b>For column <code>{warning['column_key']}</code>:</b> The value(s) {unmapped_str} "
                    f"were found in your data but could not be mapped. They are now missing (NaN). "
                    f"Please check for typos or add them to your definition."
                )
                flash(Markup(message), 'danger')
        else:
            flash('Data successfully encoded with no issues!', 'success')

        # 7. SAVE THE OUTPUT FILES
        encoded_csv_path = os.path.join(generated_folder, encoded_csv_filename)
        codebook_path = os.path.join(generated_folder, codebook_filename)
        
        # Save the final encoded data
        encoded_dataframe.to_csv(encoded_csv_path, index=False)
        
        # Save the final codebook
        with open(codebook_path, 'w', encoding='utf-8') as f:
            json.dump(codebook_dictionary, f, indent=4)
            
        # 8. REDIRECT TO RESULTS
        return redirect(url_for('encoding.results', study_id=study.id))

    except ValueError as e: 
        # This specifically catches the incompatibility error from the manager
        flash(f"Compatibility Error: {e}", "danger")
        return redirect(url_for('encoding.assign', study_id=study.id))
    except FileNotFoundError as e:
         flash(f"A required file was not found: {e}", "danger")
         return redirect(url_for('encoding.assign', study_id=study.id))
    except Exception as e:
        # A general catch-all for any other unexpected errors
        current_app.logger.error(f"A critical error occurred during encoding: {e}", exc_info=True)
        flash(f"A critical error occurred during encoding: {e}", "danger")
        return redirect(url_for('encoding.assign', study_id=study.id))
    

@encoding_bp.route('/update_definition', methods=['POST'])
def update_definition():
    """Handles the form submission for updating an existing EncoderDefinition."""
    study_id = request.form.get('study_id')
    definition_id = request.form.get('definition_id')
    try:
        new_name = request.form.get('edit_definition_name')
        new_config_str = request.form.get('edit_configuration')

        if not all([study_id, definition_id, new_name, new_config_str]):
            raise ValueError("Missing data to update the definition.")

        # Validate and parse the JSON configuration
        try:
            new_configuration = json.loads(new_config_str)
        except json.JSONDecodeError:
            raise ValueError("The provided configuration is not valid JSON.")

        # Call the new manager method to perform the update
        EncodingConfigManager.update_encoder_definition(
            definition_id=definition_id,
            new_name=new_name,
            new_configuration=new_configuration
        )
        flash(f"Definition '{new_name}' updated successfully.", "success")

    except Exception as e:
        flash(f"Error updating definition: {e}", "danger")
    
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/results/<int:study_id>')
def results(study_id):
    """
    (Step 4) Displays the results of an encoding process in an interactive table.
    This replaces the old simple links page and the separate encoder_results_view.
    """
    study = Study.query.get_or_404(study_id)
    
    # <<< CHANGE 4: USE STANDARDIZED FILENAMES FOR SEEKING >>>
    base_name = study.map_filename.replace('.json', '')
    encoded_csv_filename = f"{base_name}_encoded.csv"
    codebook_filename = f"{base_name}_codebook.json" # Look for .json
    
    generated_folder = current_app.config['GENERATED_FOLDER']
    encoded_csv_path = os.path.join(generated_folder, encoded_csv_filename)
    codebook_path = os.path.join(generated_folder, codebook_filename)
    
    csv_filename = study.map_filename.replace('.json', '.csv')
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
    df_preview = pd.read_csv(csv_path, encoding='latin1', nrows=10)
    
    # Check if the necessary result files exist
    if not os.path.exists(encoded_csv_path) or not os.path.exists(codebook_path):
        flash("Result files for the interactive table were not found. Please run the encoding process first.", "warning")
        return redirect(url_for('encoding.assign', study_id=study.id))

    try:
        # Read the encoded data as strings and the codebook
        df = pd.read_csv(encoded_csv_path, dtype=str).fillna('')
        with open(codebook_path, 'r', encoding='latin1') as f:
            codebook = json.load(f)

        # Create a mapping from the short column name to the full question text
        column_map = {
            col: codebook.get(col, {}).get('question_text', 'No question text found.')
            for col in df.columns
        }
        
        return render_template(
            'encoder_results.html',
            study=study,
            table_headers=list(df.columns),
            column_map=column_map,
            table_data=df.values.tolist(),
            codebook_filename=codebook_filename,
            encoded_csv_filename=encoded_csv_filename,
            result_files_exist=True,
            df_preview_html=df_preview.to_html(classes='table table-sm', index=False, border=0),
        )

    except Exception as e:
        current_app.logger.error(f"Error loading encoder results for study {study_id}: {e}")
        flash(f"An error occurred while loading the results: {e}", "danger")
        return redirect(url_for('encoding.assign', study_id=study.id))

@encoding_bp.route('/refresh_prototypes', methods=['POST'])
def refresh_prototypes():
    """
    Manually triggers the seeding/updating of encoder prototypes from the config file.
    """
    study_id = request.form.get('study_id') # Get study_id to redirect back correctly
    try:
        # The seed_prototypes method is idempotent, so it's safe to call again.
        EncodingConfigManager.seed_prototypes()
        flash("Encoder prototypes have been synchronized with the configuration file.", "success")
    except Exception as e:
        flash(f"An error occurred while refreshing prototypes: {e}", "danger")
    
    # Redirect back to the definitions page for the current study
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/delete_definition', methods=['POST'])
def delete_definition():
    """Handles the form submission for deleting an EncoderDefinition."""
    study_id = request.form.get('study_id')
    definition_id = request.form.get('definition_id')
    try:
        if not all([study_id, definition_id]):
            raise ValueError("Missing data to delete the definition.")

        # The manager method contains the safety check logic.
        EncodingConfigManager.delete_encoder_definition(definition_id)
        
        flash("Definition deleted successfully.", "success")
    except Exception as e:
        # This will catch the ValueError from the manager and display it to the user.
        flash(f"Error: {e}", "danger")

    return redirect(url_for('encoding.definitions', study_id=study_id))
>>>>>>> main
