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