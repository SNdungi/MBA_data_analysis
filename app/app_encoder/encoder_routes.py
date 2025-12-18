# app/app_encoder/encoder_routes.py

import os
import io
import pandas as pd
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from markupsafe import Markup

from app.app_encoder.encoder_manager import EncodingConfigManager
from app.ops_bootstrap import DataBootstrapper
from app.app_encoder.encoder import DataEncoder
from app.app_database.encoder_models import Study, EncoderPrototype, EncoderDefinition
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager

# Define the Blueprint
encoding_bp = Blueprint('encoding', __name__, template_folder='templates/encoder')

def _check_workspace_files(study):
    """
    Helper to check if the required encoded results exist in the user's temp workspace.
    """
    base_name = study.map_filename.replace('.json', '')
    encoded_csv = f"{base_name}_encoded.csv"
    codebook_json = f"{base_name}_codebook.json"
    
    # Check if files exist in the ephemeral workspace
    has_encoded = WorkspaceManager.get_file(current_user.id, study.project_code, encoded_csv) is not None
    has_codebook = WorkspaceManager.get_file(current_user.id, study.project_code, codebook_json) is not None
    
    return has_encoded and has_codebook

@encoding_bp.route('/definitions/<int:study_id>')
@login_required
def definitions(study_id):
    """
    (Step 1) UI for creating and managing Encoder Definitions.
    Reads source data directly from the Temp Workspace.
    """
    try:
        study = Study.query.get_or_404(study_id)
        
        # Security Check
        if study.user_id != current_user.id:
            flash("Unauthorized access to this study.", "danger")
            return redirect(url_for('file_mgt.list_projects'))

        result_files_exist = _check_workspace_files(study)
        
        # 1. READ CSV FROM WORKSPACE
        csv_filename = study.map_filename.replace('.json', '.csv')
        csv_content = WorkspaceManager.get_file(current_user.id, study.project_code, csv_filename)
        
        df_preview_html = '<div class="text-muted p-3">Source file not found in workspace.</div>'
        
        if csv_content:
            # Parse the string content into a DataFrame for preview
            df = pd.read_csv(io.StringIO(csv_content), encoding='latin1', nrows=50)
            df_preview_html = df.to_html(classes='table table-sm', index=False, border=0)

        # Fetch Definitions and Prototypes from DB
        study_definitions = EncoderDefinition.query.filter_by(study_id=study.id).order_by(EncoderDefinition.name).all()
        prototypes = EncoderPrototype.query.all()
        
        return render_template(
            'encoder_definitions.html',
            title=f"Define: {study.name}",
            study=study,
            definitions=study_definitions,
            prototypes=prototypes,
            df_preview_html=df_preview_html,
            result_files_exist=result_files_exist
        )
    except Exception as e:
        flash(f"Error loading definitions page: {e}", "danger")
        return redirect(url_for('file_mgt.project_admin', study_id=study_id))


@encoding_bp.route('/assign/<int:study_id>')
@login_required
def assign(study_id):
    """
    (Step 2) UI for assigning Definitions to data columns.
    Uses Workspace paths for the Bootstrapper initialization.
    """
    try:
        study = Study.query.get_or_404(study_id)
        if study.user_id != current_user.id:
            return redirect(url_for('file_mgt.list_projects'))

        result_files_exist = _check_workspace_files(study)
        
        # Get physical paths for DataBootstrapper (requires file paths currently)
        csv_filename = study.map_filename.replace('.json', '.csv')
        map_filename = study.map_filename
        
        csv_path = WorkspaceManager.get_file_path(current_user.id, study.project_code, csv_filename)
        map_path = WorkspaceManager.get_file_path(current_user.id, study.project_code, map_filename)
        
        if not os.path.exists(csv_path):
            flash("Source CSV missing from workspace. Please sync your local folder.", "danger")
            return redirect(url_for('encoding.definitions', study_id=study.id))

        # Initialize Columns using the Bootstrapper logic
        bootstrapper = DataBootstrapper(file_path=csv_path, map_path=map_path, encoding='latin1')
        EncodingConfigManager.initialize_columns_for_study(study, bootstrapper.question_map)

        # Fetch data for UI
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
@login_required
def create_definition():
    """Handles the form submission for creating a new EncoderDefinition."""
    study_id = request.form.get('study_id')
    try:
        prototype_id = request.form.get('prototype_id')
        definition_name = request.form.get('definition_name')
        config_json_str = request.form.get('configuration')

        if not all([study_id, prototype_id, definition_name, config_json_str]):
            raise ValueError("All fields are required.")
        
        try:
            configuration = json.loads(config_json_str)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON configuration.")
        
        EncodingConfigManager.create_encoder_definition(
            study_id=study_id,
            prototype_id=prototype_id,
            name=definition_name,
            configuration=configuration
        )
        flash(f"Definition '{definition_name}' created.", "success")
    except Exception as e:
        flash(f"Error creating definition: {e}", "danger")
    
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/assign_definition', methods=['POST'])
@login_required
def assign_definition():
    """Handles assigning a saved definition to one or more columns."""
    study_id = request.form.get('study_id')
    try:
        definition_id = request.form.get('definition_id')
        column_ids = request.form.getlist('column_ids')

        if not definition_id or not column_ids:
            raise ValueError("Select a definition and at least one column.")

        EncodingConfigManager.assign_encoder_to_columns(column_ids, definition_id)
        flash(f"Assigned definition to {len(column_ids)} columns.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('encoding.assign', study_id=study_id))


@encoding_bp.route('/run-encoding', methods=['POST'])
@login_required
def run_encoding():
    """
    (Step 3) Executes data encoding using Workspace files.
    Reads simulated data -> Encodes -> Saves Result to Workspace.
    """
    study_id = request.form.get('study_id')
    study = Study.query.get_or_404(study_id)
    
    base_name = study.map_filename.replace('.json', '')
    simulated_filename = f"simulated_{base_name}.csv"
    encoded_csv_filename = f"{base_name}_encoded.csv"
    codebook_filename = f"{base_name}_codebook.json"

    try:
        # 1. LOAD SIMULATED DATA FROM WORKSPACE
        sim_content = WorkspaceManager.get_file(current_user.id, study.project_code, simulated_filename)
        if not sim_content:
            flash(f"Simulated data '{simulated_filename}' not found. Run bootstrap simulation first.", "danger")
            return redirect(url_for('encoding.assign', study_id=study.id))

        # 2. LOAD MAP FROM WORKSPACE
        map_content = WorkspaceManager.get_file(current_user.id, study.project_code, study.map_filename)
        if not map_content:
            flash("Map file not found.", "danger")
            return redirect(url_for('encoding.assign', study_id=study.id))
            
        question_map = json.loads(map_content)
        column_keys = list(question_map.keys())
        
        # 3. CREATE DATAFRAME
        raw_df = pd.read_csv(io.StringIO(sim_content), encoding='latin1', header=0, names=column_keys)

        # 4. GENERATE CONFIG AND RUN ENCODER
        encoder_config = EncodingConfigManager.generate_encoder_class_config(study.id)
        engine = DataEncoder(dataframe=raw_df, config=encoder_config)
        
        encoded_dataframe, codebook_dictionary, warnings, learned_maps = engine.encode()
        
        # 5. PERSIST LEARNED MAPS TO DB
        if learned_maps:
            EncodingConfigManager.update_definition_configurations(study.id, learned_maps)
            flash("Encoder definitions updated with learned values.", "info")

        # 6. SAVE OUTPUTS TO WORKSPACE
        # Save CSV
        csv_buffer = io.StringIO()
        encoded_dataframe.to_csv(csv_buffer, index=False)
        WorkspaceManager.save_file(
            current_user.id, 
            study.project_code, 
            encoded_csv_filename, 
            csv_buffer.getvalue()
        )
        
        # Save Codebook JSON
        json_str = json.dumps(codebook_dictionary, indent=4)
        WorkspaceManager.save_file(
            current_user.id, 
            study.project_code, 
            codebook_filename, 
            json_str
        )
        
        # 7. FEEDBACK
        if warnings:
            flash("Encoding complete with warnings. Review below.", "warning")
            for warning in warnings:
                msg = f"Column <b>{warning['column_key']}</b> had unmapped values: {', '.join(warning['unmapped_values'])}"
                flash(Markup(msg), 'danger')
        else:
            flash('Data successfully encoded!', 'success')

        return redirect(url_for('encoding.results', study_id=study.id))

    except Exception as e:
        current_app.logger.error(f"Encoding Error: {e}", exc_info=True)
        flash(f"Critical error during encoding: {e}", "danger")
        return redirect(url_for('encoding.assign', study_id=study.id))


@encoding_bp.route('/update_definition', methods=['POST'])
@login_required
def update_definition():
    """Handles updating an existing EncoderDefinition."""
    study_id = request.form.get('study_id')
    try:
        definition_id = request.form.get('definition_id')
        new_name = request.form.get('edit_definition_name')
        new_config_str = request.form.get('edit_configuration')

        if not all([study_id, definition_id, new_name, new_config_str]):
            raise ValueError("Missing update data.")

        EncodingConfigManager.update_encoder_definition(
            definition_id=definition_id,
            new_name=new_name,
            new_configuration=json.loads(new_config_str)
        )
        flash(f"Definition updated.", "success")
    except Exception as e:
        flash(f"Error updating: {e}", "danger")
    
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/results/<int:study_id>')
@login_required
def results(study_id):
    """
    (Step 4) Displays the results from the Workspace.
    """
    study = Study.query.get_or_404(study_id)
    if study.user_id != current_user.id:
        return redirect(url_for('file_mgt.list_projects'))

    base_name = study.map_filename.replace('.json', '')
    encoded_csv = f"{base_name}_encoded.csv"
    codebook_json = f"{base_name}_codebook.json"
    
    # 1. READ RESULTS FROM WORKSPACE
    csv_content = WorkspaceManager.get_file(current_user.id, study.project_code, encoded_csv)
    json_content = WorkspaceManager.get_file(current_user.id, study.project_code, codebook_json)
    
    if not csv_content or not json_content:
        flash("Result files not found. Please run the encoding process.", "warning")
        return redirect(url_for('encoding.assign', study_id=study.id))

    try:
        # 2. Parse Data
        df = pd.read_csv(io.StringIO(csv_content), dtype=str).fillna('')
        codebook = json.loads(json_content)

        # Map short columns to full text
        column_map = {
            col: codebook.get(col, {}).get('question_text', 'No text')
            for col in df.columns
        }
        
        # 3. Preview Original Data for comparison
        original_csv = study.map_filename.replace('.json', '.csv')
        orig_content = WorkspaceManager.get_file(current_user.id, study.project_code, original_csv)
        df_preview_html = ""
        if orig_content:
            df_preview = pd.read_csv(io.StringIO(orig_content), encoding='latin1', nrows=10)
            df_preview_html = df_preview.to_html(classes='table table-sm', index=False, border=0)
        
        return render_template(
            'encoder_results.html',
            study=study,
            table_headers=list(df.columns),
            column_map=column_map,
            table_data=df.values.tolist(),
            codebook_filename=codebook_json,
            encoded_csv_filename=encoded_csv,
            result_files_exist=True,
            df_preview_html=df_preview_html,
        )

    except Exception as e:
        flash(f"Error loading results: {e}", "danger")
        return redirect(url_for('encoding.assign', study_id=study.id))


@encoding_bp.route('/refresh_prototypes', methods=['POST'])
@login_required
def refresh_prototypes():
    """Manually triggers seeding of encoder prototypes."""
    study_id = request.form.get('study_id')
    try:
        EncodingConfigManager.seed_prototypes()
        flash("Prototypes synchronized.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    
    return redirect(url_for('encoding.definitions', study_id=study_id))


@encoding_bp.route('/delete_definition', methods=['POST'])
@login_required
def delete_definition():
    """Handles deletion of an EncoderDefinition."""
    study_id = request.form.get('study_id')
    try:
        EncodingConfigManager.delete_encoder_definition(request.form.get('definition_id'))
        flash("Definition deleted.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for('encoding.definitions', study_id=study_id))