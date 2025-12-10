import os
import secrets
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager # Import LoginManager
from app.app_tutorials.tutorials_models import TutorialLevel
from app.app_encoder.encoder_models import User # Import User model
from datetime import datetime

def create_app():
    """Application Factory Function"""
    app = Flask(__name__)
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app.config['BASE_DIR'] = BASE_DIR

    # --- 1. Basic App Configuration ---
    app.secret_key = secrets.token_hex(16)
    
    # --- 2. Database Configuration ---
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///TXdata.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- 3. Other File Path Configurations ---
    app.config['UPLOADS_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    app.config['GENERATED_FOLDER'] = os.path.join(app.static_folder, 'generated')
    app.config['GRAPHS_FOLDER'] = os.path.join(app.static_folder, 'graphs')

    # --- 4. Initialize Extensions ---
    from app.app_database.extensions import db
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # --- Initialize Login Manager ---
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login' # Where to redirect if user isn't logged in
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}
    
    

    # --- 5. Create DB and Register Blueprints ---
    with app.app_context():
        db.create_all()

        os.makedirs(app.config['UPLOADS_FOLDER'], exist_ok=True)
        os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
        os.makedirs(app.config['GRAPHS_FOLDER'], exist_ok=True)

        # Register Auth Blueprint
        from app.app_auth.auth_routes import auth_bp
        app.register_blueprint(auth_bp)

        from app.ops_routes import ops_bp
        app.register_blueprint(ops_bp) 

        from app.app_encoder.encoder_routes import encoding_bp
        app.register_blueprint(encoding_bp)
        
        from app.app_analysis.analysis_routes import analysis_bp
        app.register_blueprint(analysis_bp)
        
        from app.app_encoder.encoder_manager import EncodingConfigManager
        EncodingConfigManager.seed_prototypes()
        
        from app.app_file_mgt.file_mgt import file_mgt_bp
        app.register_blueprint(file_mgt_bp)
        
        from app.app_tutorials.tutorials import tutorials_bp
        app.register_blueprint(tutorials_bp)
        
        from app.commands import seed_tutorials
        app.cli.add_command(seed_tutorials)
        
    return app