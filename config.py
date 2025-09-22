import toml
import os

class AppConfig:
    """
    A centralized class to load and provide configuration from TOML files.
    """  
    _prototypes = None

    @staticmethod
    def get_encoder_prototypes():
        """
        Loads the encoder prototypes from 'prototypes.toml'.
        
        It caches the result after the first read to avoid redundant file I/O.
        """
        if AppConfig._prototypes is None:
            # Construct the path relative to this file's location
            # This makes it robust to where the app is run from.
            try:
                # Assuming config.py is in the 'app' directory
                # and prototypes.toml is in the root directory
                config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
                
                with open(config_path, 'r') as f:
                    data = toml.load(f)
                    AppConfig._prototypes = data.get("prototypes", [])
                
                print(f"--- Successfully loaded {len(AppConfig._prototypes)} encoder prototypes from TOML file. ---")

            except FileNotFoundError:
                print(f"CRITICAL ERROR: 'config.toml' not found at '{config_path}'. Seeding will fail.")
                AppConfig._prototypes = [] # Return empty list to prevent crash
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to parse 'config.toml'. Error: {e}")
                AppConfig._prototypes = []
        
        return AppConfig._prototypes