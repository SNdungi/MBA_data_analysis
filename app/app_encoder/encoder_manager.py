<<<<<<< HEAD
from app.app_encoder.encoder_model import db, EncodingConfig
from typing import Dict, List, Any

class EncodingConfigManager:
    """
    Provides a high-level API to manage encoding configurations using the
    SQLAlchemy EncodingConfig model.
    """

    @staticmethod
    def initialize_config_for_map(map_filename: str, question_map: Dict[str, str]):
        """
        Populates the database with default entries for a new question map.
        If an entry for a column already exists, it is skipped.
        """
        print(f"Initializing/Verifying encoding configuration for '{map_filename}'...")
        
        # Get existing keys to avoid duplicates
        existing_keys = {
            c.column_key for c in 
            EncodingConfig.query.filter_by(map_filename=map_filename).all()
        }

        new_configs = []
        for key, value in question_map.items():
            if key not in existing_keys:
                new_config = EncodingConfig(
                    map_filename=map_filename,
                    column_key=key,
                    original_name=value,
                    encoder_type='None',
                    encoder_config={}
                )
                new_configs.append(new_config)
        
        if new_configs:
            db.session.add_all(new_configs)
            db.session.commit()
            print(f"Added {len(new_configs)} new column configurations to the database.")
        else:
            print("All columns already exist in the database.")

    @staticmethod
    def get_config_for_map(map_filename: str) -> List[EncodingConfig]:
        """Retrieves all configuration objects for a specific map file, ordered by ID."""
        return EncodingConfig.query.filter_by(map_filename=map_filename).order_by(EncodingConfig.id).all()

    @staticmethod
    def update_column_config(config_id: int, encoder_type: str, config_details: Dict[str, Any]):
        """Updates the encoding configuration for a single column by its ID."""
        config_entry = EncodingConfig.query.get(config_id)
        if config_entry:
            config_entry.encoder_type = encoder_type
            config_entry.encoder_config = config_details
            db.session.commit()

    @staticmethod
    def bulk_update_likert_config(map_filename: str, start_key: str, end_key: str, scale_type: str, is_reverse: bool = False):
        """Applies a Likert configuration to a range of columns."""
        configs_in_range = db.session.query(EncodingConfig).filter(
            EncodingConfig.map_filename == map_filename
        ).order_by(EncodingConfig.id).all()
        
        # Find the start and end indices in the full ordered list
        keys = [c.column_key for c in configs_in_range]
        try:
            start_index = keys.index(start_key)
            end_index = keys.index(end_key)
        except ValueError:
            raise ValueError("Start or end key not found for bulk update.")

        if start_index > end_index:
            raise ValueError("Start column must come before end column.")
        
        # Update each config object in the slice
        for i in range(start_index, end_index + 1):
            configs_in_range[i].encoder_type = 'Likert'
            configs_in_range[i].encoder_config = {
                "scale": scale_type,
                "is_reverse": is_reverse
            }
        
        db.session.commit()
        print(f"Bulk updated {end_index - start_index + 1} columns from '{start_key}' to '{end_key}'.")

    @staticmethod
    def generate_encoder_class_config(map_filename: str) -> Dict[str, Any]:
        """
        Transforms the database configuration into the format required by the DataEncoder class.
        """
        db_configs = EncodingConfigManager.get_config_for_map(map_filename)
        
        encoder_config = {
            "ordinal_cols": [],
            "nominal_cols": [],
            "likert_cols": {"positive": [], "reverse": []},
            "mappings": {}
        }
        
        for config_entry in db_configs:
            key = config_entry.column_key
            etype = config_entry.encoder_type
            econfig = config_entry.encoder_config

            if etype == 'Ordinal':
                encoder_config["ordinal_cols"].append(key)
                encoder_config["mappings"][key] = econfig.get("order", [])
            elif etype == 'Nominal':
                encoder_config["nominal_cols"].append(key)
            elif etype == 'Likert':
                scale_name = econfig.get("scale")
                if scale_name and scale_name not in encoder_config["mappings"]:
                    # In a real app, this would be loaded from a global config
                    if scale_name == "likert_5_point":
                        encoder_config["mappings"][scale_name] = {
                            "Strongly Disagree": 1, "Disagree": 2, "Neutral": 3, "Agree": 4, "Strongly Agree": 5
                        }
                    # Add more scales (3-point, 7-point) here
                
                encoder_config["likert_cols"]["mapping_name"] = scale_name
                if econfig.get("is_reverse"):
                    encoder_config["likert_cols"]["reverse"].append(key)
                else:
                    encoder_config["likert_cols"]["positive"].append(key)

        return encoder_config
=======
from app.app_encoder.encoder_models import db, Study, EncoderPrototype, EncoderDefinition, ColumnEncoding
from typing import Dict, List, Any
from config import AppConfig
import os
import json
from flask import current_app



class EncodingConfigManager:
    """
    Manages the entire encoding configuration lifecycle using SQLAlchemy models.
    """

    @staticmethod
    def seed_prototypes():
        """
        Seeds the database with default encoder prototypes loaded from prototypes.toml.
        """
        # --- THIS IS THE ONLY CHANGE ---
        # Get the prototype data from our centralized config loader
        prototypes_data = AppConfig.get_encoder_prototypes()
        
        if not prototypes_data:
            print("Warning: No prototypes found in config file. Skipping database seeding.")
            return

        # Check which prototypes already exist in the database
        existing_names = [p.name for p in EncoderPrototype.query.all()]
        
        new_prototypes_to_add = []
        for p_data in prototypes_data:
            if p_data['name'] not in existing_names:
                # Create a new EncoderPrototype object using the data from the TOML file
                prototype = EncoderPrototype(
                    name=p_data['name'],
                    encoder_type=p_data['encoder_type'],
                    description=p_data['description']
                )
                new_prototypes_to_add.append(prototype)

        if new_prototypes_to_add:
            db.session.add_all(new_prototypes_to_add)
            db.session.commit()
            print(f"Seeded {len(new_prototypes_to_add)} new encoder prototypes to the database.")
        else:
            print("Encoder prototypes are already up-to-date in the database.")
            
    @staticmethod
    def get_column_map(study_id: int) -> Dict[str, str]:
        """
        Loads the JSON file that maps short keys (q1) to original questions for a study.
        """
        study = Study.query.get_or_404(study_id)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename)
        try:
            with open(map_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"WARNING: Could not load column map file '{map_path}'. Error: {e}")
            return {} # Return an empty dict to prevent crashes

    @staticmethod
    def get_or_create_study(name: str, map_filename: str, topic: str = "", description: str = "") -> Study:
        """Finds a study by name or creates it if it doesn't exist."""
        study = Study.query.filter_by(name=name).first()
        if not study:
            study = Study(name=name, map_filename=map_filename, topic=topic, description=description)
            db.session.add(study)
            db.session.commit()
        return study
    
        
    @staticmethod
    def get_column_configs_for_study(study_id: int) -> List[ColumnEncoding]:
        """Retrieves all column configuration objects for a specific study, ordered by ID."""
        return ColumnEncoding.query.filter_by(study_id=study_id).order_by(ColumnEncoding.id).all()
    

    @staticmethod
    def initialize_columns_for_study(study: Study, question_map: Dict[str, str]):
        """Populates the ColumnEncoding table for a given study."""
        existing_keys = {c.column_key for c in study.column_encodings}
        new_columns = []
        for key, value in question_map.items():
            if key not in existing_keys:
                new_columns.append(ColumnEncoding(study_id=study.id, column_key=key, original_name=value))
        if new_columns:
            db.session.add_all(new_columns)
            db.session.commit()

    @staticmethod
    def create_encoder_definition(study_id: int, prototype_id: int, name: str, configuration: Dict) -> EncoderDefinition:
        """Creates a new, user-defined encoding 'recipe'."""
        definition = EncoderDefinition(
            study_id=study_id,
            prototype_id=prototype_id,
            name=name,
            configuration=configuration
        )
        db.session.add(definition)
        db.session.commit()
        return definition
        
    @staticmethod
    def assign_encoder_to_columns(column_ids: List[int], definition_id: int):
        """Applies a specific EncoderDefinition to one or more columns."""
        ColumnEncoding.query.filter(
            ColumnEncoding.id.in_(column_ids)
        ).update({'encoder_definition_id': definition_id}, synchronize_session=False)
        db.session.commit()

    @staticmethod
    def update_encoder_definition(definition_id: int, new_name: str, new_configuration: Dict):
        """
        Updates an existing EncoderDefinition with a new name and/or configuration.
        """
        definition = EncoderDefinition.query.get_or_404(definition_id)
        definition.name = new_name
        definition.configuration = new_configuration
        db.session.commit()
        return definition

    @staticmethod
    def generate_encoder_class_config(study_id: int) -> Dict[str, Any]:
        """
        Translates the DB state into the EXACT config dictionary the DataEncoder class needs.
        This version correctly traverses the relationships defined in encoder_models.py.
        """
        # Start with an empty dictionary. We will build keys like "Likert", "Ordinal" as needed.
        encoder_config = {}

        # 1. Get all column configurations for the study that have a definition assigned.
        # This query is the starting point.
        column_configs = ColumnEncoding.query.filter(
            ColumnEncoding.study_id == study_id,
            ColumnEncoding.encoder_definition_id.isnot(None)
        ).all()
        
        # 2. Loop through each assignment and follow the relationships.
        for config in column_configs:
            prototype_type = config.encoder_definition.prototype.encoder_type
            if prototype_type not in encoder_config:
                encoder_config[prototype_type] = {}

            column_key = config.column_key
            definition_config = config.encoder_definition.configuration
            encoder_config[prototype_type][column_key] = definition_config

        # 3. Add the crucial column map for translating keys to full question text.
        study = Study.query.get_or_404(study_id)
        map_path = os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename)
        try:
            with open(map_path, 'r', encoding='utf-8') as f:
                encoder_config['column_map'] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"WARNING: Could not load column map file '{map_path}'. Error: {e}")
            encoder_config['column_map'] = {}

        # Add a print statement for easy debugging in your console.
        print("--- Generated Config for DataEncoder ---")
        print(json.dumps(encoder_config, indent=2))
        print("---------------------------------------")

        return encoder_config

    
    @staticmethod
    def apply_definition_to_columns(study_id: int, column_ids: List[int], definition_name: str, definition_config: Dict, prototype_name: str):
        """
        Finds or creates an EncoderDefinition and applies it to the specified columns.
        This one powerful method replaces both old update methods.
        """
        # Find the prototype (e.g., 'Likert', 'Ordinal')
        prototype = EncoderPrototype.query.filter_by(name=prototype_name).first()
        if not prototype:
            raise ValueError(f"Encoder prototype '{prototype_name}' not found.")

        # Find or create the specific user-defined recipe (e.g., "My 5-Point Reverse Scale")
        definition = EncoderDefinition.query.filter_by(study_id=study_id, name=definition_name).first()
        if not definition:
            definition = EncoderDefinition(
                study_id=study_id,
                prototype_id=prototype.id,
                name=definition_name,
                configuration=definition_config
            )
            db.session.add(definition)
            db.session.commit() # Commit to get the ID for the next step

        # Apply this definition to all selected columns
        ColumnEncoding.query.filter(
            ColumnEncoding.study_id == study_id,
            ColumnEncoding.id.in_(column_ids)
        ).update({'encoder_definition_id': definition.id}, synchronize_session=False)
        db.session.commit()
        
    @staticmethod
    def update_definition_configurations(study_id: int, learned_maps: Dict[str, Dict]):
        """
        Updates the configuration of auto-generated encoders (Nominal, Binary)
        in the database. This version correctly handles updating the JSON field.
        """
        if not learned_maps:
            return

        # Get all column configurations for the study in one query
        column_configs = ColumnEncoding.query.filter(
            ColumnEncoding.study_id == study_id,
            ColumnEncoding.column_key.in_(learned_maps.keys())
        ).all()
        
        # Create a dictionary for quick lookup: { 'q1': <ColumnEncoding object>, ... }
        config_map = {cc.column_key: cc for cc in column_configs}

        for col_key, new_value_map in learned_maps.items():
            col_config = config_map.get(col_key)
            if not col_config or not col_config.encoder_definition:
                continue

            definition = col_config.encoder_definition
            
            # --- THE FIX: We must work with a copy and reassign ---
            
            # 1. Get a mutable copy of the current configuration.
            #    If it's None or empty, start with a fresh dictionary.
            current_config = definition.configuration or {}
            
            # 2. Check if the 'value_map' key exists and has content.
            if 'value_map' in current_config and current_config['value_map']:
                # It's not empty, so we must perform the compatibility check.
                existing_map = current_config['value_map']
                
                # Sort items to ensure comparison is not order-dependent.
                # Convert keys to int for a robust comparison if they are strings (from JSON).
                sorted_existing = sorted({str(k): v for k, v in existing_map.items()}.items())
                sorted_new = sorted({str(k): v for k, v in new_value_map.items()}.items())

                if sorted_existing != sorted_new:
                    raise ValueError(
                        f"Incompatible Value Maps for definition '{definition.name}' (used by column {col_key}). "
                        f"The data in this column has different categories than what is already saved in the definition. "
                        f"Please create and assign a new, unique definition for this column."
                    )
                # If they match, there's nothing to do, so we can continue.
                continue
            else:
                # It's empty, so we can safely populate it.
                # 3. Modify the copied dictionary.
                current_config['value_map'] = new_value_map
                
                # 4. Reassign the entire modified dictionary back to the model's attribute.
                #    This is what flags the field as "dirty" for SQLAlchemy to update.
                definition.configuration = current_config
                
                # Add a flag to the session to ensure the change is marked.
                db.session.add(definition) 
                
                print(f"INFO: Staging update for definition '{definition.name}' (column {col_key}).")
        
        # Commit all staged changes at the end of the loop.
        db.session.commit()
        print("INFO: Committed all definition configuration updates to the database.")
        

    @staticmethod
    def delete_encoder_definition(definition_id: int):
        """
        Deletes an EncoderDefinition, but only if it's not currently assigned
        to any columns.
        """
        definition = EncoderDefinition.query.get_or_404(definition_id)
        
        # This is the crucial safety check using the model relationship.
        assignment_count = len(definition.column_assignments)
        
        if assignment_count > 0:
            # If the definition is in use, we raise an error to prevent deletion.
            raise ValueError(
                f"Cannot delete definition '{definition.name}' because it is currently "
                f"assigned to {assignment_count} column(s). Please unassign it first."
            )
        
        # If the check passes (count is 0), we can safely delete it.
        db.session.delete(definition)
        db.session.commit()
>>>>>>> main
