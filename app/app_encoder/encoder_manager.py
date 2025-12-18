from app.app_database.encoder_models import db, Study, EncoderPrototype, EncoderDefinition, ColumnEncoding
from typing import Dict, List, Any
from config import AppConfig
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager
from flask_login import current_user
import json




class EncodingConfigManager:
    """
    Manages the entire encoding configuration lifecycle using SQLAlchemy models.
    """

    @staticmethod
    def seed_prototypes():
        """Seeds default encoder prototypes from TOML config."""
        prototypes_data = AppConfig.get_encoder_prototypes()
        if not prototypes_data: return

        existing_names = [p.name for p in EncoderPrototype.query.all()]
        new_prototypes = []
        for p_data in prototypes_data:
            if p_data['name'] not in existing_names:
                new_prototypes.append(EncoderPrototype(
                    name=p_data['name'],
                    encoder_type=p_data['encoder_type'],
                    description=p_data['description']
                ))
        if new_prototypes:
            db.session.add_all(new_prototypes)
            db.session.commit()
            
    @staticmethod
    def get_column_map(study_id: int) -> Dict[str, str]:
        """
        Loads the JSON map from the Workspace Cache.
        """
        study = Study.query.get_or_404(study_id)
        
        # READ FROM WORKSPACE
        content = WorkspaceManager.get_file(current_user.id, study.project_code, study.map_filename)
        
        if not content:
            print(f"WARNING: Map file '{study.map_filename}' not found in workspace.")
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"WARNING: Invalid JSON in map file. Error: {e}")
            return {}

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
        return ColumnEncoding.query.filter_by(study_id=study_id).order_by(ColumnEncoding.id).all()

    @staticmethod
    def initialize_columns_for_study(study: Study, question_map: Dict[str, str]):
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
        definition = EncoderDefinition(study_id=study_id, prototype_id=prototype_id, name=name, configuration=configuration)
        db.session.add(definition)
        db.session.commit()
        return definition
        
    @staticmethod
    def assign_encoder_to_columns(column_ids: List[int], definition_id: int):
        ColumnEncoding.query.filter(ColumnEncoding.id.in_(column_ids)).update({'encoder_definition_id': definition_id}, synchronize_session=False)
        db.session.commit()

    @staticmethod
    def update_encoder_definition(definition_id: int, new_name: str, new_configuration: Dict):
        definition = EncoderDefinition.query.get_or_404(definition_id)
        definition.name = new_name
        definition.configuration = new_configuration
        db.session.commit()

    @staticmethod
    def generate_encoder_class_config(study_id: int) -> Dict[str, Any]:
        """
        Translates DB state into the config dictionary for DataEncoder class.
        """
        encoder_config = {}

        # 1. Get assignments from DB
        column_configs = ColumnEncoding.query.filter(
            ColumnEncoding.study_id == study_id,
            ColumnEncoding.encoder_definition_id.isnot(None)
        ).all()
        
        for config in column_configs:
            prototype_type = config.encoder_definition.prototype.encoder_type
            if prototype_type not in encoder_config:
                encoder_config[prototype_type] = {}

            column_key = config.column_key
            definition_config = config.encoder_definition.configuration
            encoder_config[prototype_type][column_key] = definition_config

        # 2. Get Column Map from Workspace
        encoder_config['column_map'] = EncodingConfigManager.get_column_map(study_id)

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
        if not learned_maps: return
        column_configs = ColumnEncoding.query.filter(
            ColumnEncoding.study_id == study_id,
            ColumnEncoding.column_key.in_(learned_maps.keys())
        ).all()
        config_map = {cc.column_key: cc for cc in column_configs}

        for col_key, new_value_map in learned_maps.items():
            col_config = config_map.get(col_key)
            if not col_config or not col_config.encoder_definition: continue

            definition = col_config.encoder_definition
            current_config = definition.configuration or {}
            
            if 'value_map' in current_config and current_config['value_map']:
                existing_map = current_config['value_map']
                sorted_existing = sorted({str(k): v for k, v in existing_map.items()}.items())
                sorted_new = sorted({str(k): v for k, v in new_value_map.items()}.items())
                if sorted_existing != sorted_new:
                    raise ValueError(f"Incompatible Value Maps for '{definition.name}'. Create a new definition.")
                continue
            else:
                current_config['value_map'] = new_value_map
                definition.configuration = current_config
                db.session.add(definition) 
        db.session.commit()

    @staticmethod
    def delete_encoder_definition(definition_id: int):
        definition = EncoderDefinition.query.get_or_404(definition_id)
        if len(definition.column_assignments) > 0:
            raise ValueError(f"Cannot delete '{definition.name}' because it is assigned to columns.")
        db.session.delete(definition)
        db.session.commit()
