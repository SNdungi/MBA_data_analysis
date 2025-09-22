# File: app/__init__.py

import os
import secrets
from flask import Flask
from flask_migrate import Migrate
# Import the db object from where you defined it (assuming app/models.py)
from app.app_encoder.encoder_models import db 
from datetime import datetime

def create_app():
    """Application Factory Function"""
    app = Flask(__name__)
    
    # --- 1. Basic App Configuration ---
    app.secret_key = secrets.token_hex(16)
    
    # --- 2. Database Configuration ---
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'TXdata.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- 3. Other File Path Configurations ---
    app.config['UPLOADS_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    app.config['GENERATED_FOLDER'] = os.path.join(app.static_folder, 'generated')
    app.config['GRAPHS_FOLDER'] = os.path.join(app.static_folder, 'graphs')

    # --- 4. Initialize Extensions (like SQLAlchemy) ---
    db.init_app(app)
    migrate = Migrate(app, db)
    
    
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    # --- 5. Create the database tables if they don't exist ---
    with app.app_context():
        db.create_all()

        os.makedirs(app.config['UPLOADS_FOLDER'], exist_ok=True)
        os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
        os.makedirs(app.config['GRAPHS_FOLDER'], exist_ok=True)

        # --- NOW it is safe to import and register the blueprints ---
        from app.ops_routes import ops_bp
        app.register_blueprint(ops_bp) # url_prefix defaults to '/'

        from app.app_encoder.encoder_routes import encoding_bp
        app.register_blueprint(encoding_bp)
        
        from app.app_analysis.analysis_routes import analysis_bp
        app.register_blueprint(analysis_bp)
        
        from app.app_encoder.encoder_manager import EncodingConfigManager
        EncodingConfigManager.seed_prototypes()
        
          
    return app