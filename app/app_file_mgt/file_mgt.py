import os
import io
import shutil
import zipfile
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from werkzeug.utils import secure_filename
# Added User to imports
from app.app_encoder.encoder_models import db, Study, EncoderDefinition, User
from flask_login import login_required, current_user

file_mgt_bp = Blueprint('file_mgt', __name__, template_folder='templates/file_mgt', url_prefix='/projects')

# --- Helper Functions ---

def _clear_folder_contents(folder_path):
    """Deletes all files and folders inside a directory."""
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

def _get_active_user_id():
    """
    Helper to get a valid user_id. 
    1. Tries flask_login current_user.
    2. If not logged in, returns the first user in DB.
    3. If DB is empty, creates a default Admin user.
    """
    # 1. Check if a user is actually logged in via Flask-Login
    if current_user and current_user.is_authenticated:
        return current_user.id
    
    # 2. Fallback: Get the first user available in the database
    user = User.query.first()
    if user:
        return user.id
    
    # 3. Last Resort: Create a default Admin user so the app doesn't crash
    try:
        print("No users found. Creating default 'admin' user...")
        default_user = User(username='admin', email='admin@example.com')
        default_user.set_password('password') # You can change this later
        db.session.add(default_user)
        db.session.commit()
        return default_user.id
    except Exception as e:
        print(f"Error creating default user: {e}")
        return None

# --- Routes ---

@file_mgt_bp.route('/')
@file_mgt_bp.route('/list')
@login_required  # Protect this route
def list_projects():
    # Only show studies belonging to the current user
    studies = Study.query.filter_by(user_id=current_user.id).order_by(Study.created_at.desc()).all()
    return render_template('list_projects.html', studies=studies, active_page='list')

@file_mgt_bp.route('/new', methods=['GET', 'POST'])
@login_required  # Protect this route
def new_project():
    """Sidebar: New Study. Handles creation form."""
    if request.method == 'POST':
        study_name = request.form.get('study_name')
        uploaded_file = request.files.get('source_csv')
        clone_id = request.form.get('clone_from_study_id')

        # --- 1. Validate Inputs ---
        if not study_name or not uploaded_file or uploaded_file.filename == '':
            flash('Study Name and CSV file are required.', 'danger')
            return redirect(url_for('file_mgt.new_project'))
        
        if not uploaded_file.filename.lower().endswith('.csv'):
            flash('Invalid file type. Please upload a CSV.', 'danger')
            return redirect(url_for('file_mgt.new_project'))

        # --- 2. Get User ID (Fix for IntegrityError) ---
        user_id = _get_active_user_id()
        if not user_id:
            flash('System Error: Could not assign a user owner to this study.', 'danger')
            return redirect(url_for('file_mgt.new_project'))

        try:
            secure_base_name = secure_filename(study_name.lower().replace(' ', '_'))
            csv_filename = f"{secure_base_name}.csv"
            map_filename = f"{secure_base_name}.json"

            # Check duplicates
            if Study.query.filter_by(name=study_name).first():
                flash(f"Study '{study_name}' already exists.", 'warning')
                return redirect(url_for('file_mgt.new_project'))

            # Save File
            csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], csv_filename)
            uploaded_file.save(csv_path)

            # --- 3. Create DB Record with user_id ---
            new_study = Study(
                name=study_name,
                map_filename=map_filename,
                topic=request.form.get('study_topic', ''),
                description=request.form.get('study_description', ''),
                user_id=current_user.id   # <--- THIS WAS MISSING
            )
            db.session.add(new_study)
            db.session.flush() # Get ID

            # Clone Logic
            if clone_id and clone_id.isdigit():
                source = Study.query.get(int(clone_id))
                if source:
                    for s_def in source.definitions:
                        new_def = EncoderDefinition(
                            study_id=new_study.id,
                            prototype_id=s_def.prototype_id,
                            name=s_def.name,
                            configuration=s_def.configuration
                        )
                        db.session.add(new_def)

            db.session.commit()
            flash(f"Project '{study_name}' created successfully.", 'success')
            return redirect(url_for('file_mgt.project_admin', study_id=new_study.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Creation failed: {e}", 'danger')
            return redirect(url_for('file_mgt.new_project'))

    # GET Request: Render Form
    existing_studies = Study.query.order_by(Study.name).all()
    return render_template('new_project.html', existing_studies=existing_studies, active_page='new')

@file_mgt_bp.route('/admin/<int:study_id>')
def project_admin(study_id):
    """Sidebar: Project Admin. Detailed view of a specific project."""
    study = Study.query.get_or_404(study_id)
    
    # Generate Preview
    csv_path = os.path.join(current_app.config['UPLOADS_FOLDER'], study.map_filename.replace('.json', '.csv'))
    preview_html = None
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, encoding='latin1', nrows=5)
            preview_html = df.to_html(classes='table table-sm table-striped small', index=False, border=0)
        except Exception:
            preview_html = "Error reading CSV."

    return render_template('project_admin.html', study=study, preview_html=preview_html, active_page='admin')

@file_mgt_bp.route('/update/<int:study_id>', methods=['POST'])
def update_project(study_id):
    """Handles updating project metadata."""
    study = Study.query.get_or_404(study_id)
    try:
        study.name = request.form.get('study_name')
        study.topic = request.form.get('study_topic')
        study.description = request.form.get('study_description')
        db.session.commit()
        flash('Project details updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Update failed: {e}', 'danger')
    return redirect(url_for('file_mgt.project_admin', study_id=study.id))

@file_mgt_bp.route('/delete/<int:study_id>', methods=['POST'])
def delete_project(study_id):
    """Permanently deletes a project."""
    study = Study.query.get_or_404(study_id)
    try:
        base_name = study.map_filename.replace('.json', '')
        files = [
            os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv"),
            os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename),
            os.path.join(current_app.config['GENERATED_FOLDER'], f"{base_name}_encoded.csv"),
            os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv")
        ]
        for f in files:
            if os.path.exists(f):
                os.remove(f)

        db.session.delete(study)
        db.session.commit()
        flash(f"Deleted '{study.name}'.", 'success')
        return redirect(url_for('file_mgt.list_projects'))
    except Exception as e:
        db.session.rollback()
        flash(f"Delete failed: {e}", 'danger')
        return redirect(url_for('file_mgt.project_admin', study_id=study.id))

@file_mgt_bp.route('/export/<int:study_id>')
def export_project(study_id):
    """Zips project files for download."""
    study = Study.query.get_or_404(study_id)
    try:
        base_name = study.map_filename.replace('.json', '')
        secure_zip_name = f"{secure_filename(study.name)}_export.zip"
        
        files_to_zip = {
            f"{base_name}.csv": os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv"),
            study.map_filename: os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename),
            f"simulated_{base_name}.csv": os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv"),
        }

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname, fpath in files_to_zip.items():
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=fname)
        
        memory_file.seek(0)
        return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=secure_zip_name)
    except Exception as e:
        flash(f"Export error: {e}", 'danger')
        return redirect(url_for('file_mgt.project_admin', study_id=study.id))

@file_mgt_bp.route('/system')
def system_tools():
    """Sidebar: System Tools. Global housekeeping."""
    return render_template('system_tools.html', active_page='system')

@file_mgt_bp.route('/system/purge', methods=['POST'])
def purge_system():
    """Nuclear option: Delete everything."""
    try:
        db.session.query(Study).delete()
        # Note: If you want to keep the admin user, don't delete from User table. 
        # But if you want a full wipe:
        # db.session.query(User).delete() 
        db.session.commit()
        _clear_folder_contents(current_app.config['UPLOADS_FOLDER'])
        _clear_folder_contents(current_app.config['GENERATED_FOLDER'])
        _clear_folder_contents(current_app.config['GRAPHS_FOLDER'])
        flash("System completely purged.", 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f"Purge failed: {e}", 'danger')
    return redirect(url_for('file_mgt.list_projects'))