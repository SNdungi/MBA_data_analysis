import os
import io
import zipfile
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, session,jsonify,send_file
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager
from werkzeug.utils import secure_filename
from app.app_file_mgt.file_workspace_mgt import WorkspaceManager # Ensure this import exists
from app.app_database.encoder_models import db, Study,  User
from flask_login import login_required, current_user
import hashlib
from app.app_file_mgt.file_workspace_mgt import SecurityException



file_mgt_bp = Blueprint('file_mgt', __name__, template_folder='templates/file_mgt', url_prefix='/projects')

# --- Helper Functions ---

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
@login_required
def new_project():
    if request.method == 'POST':
        study_name = request.form.get('study_name')
        uploaded_file = request.files.get('source_csv')
        
        # ... validations ...
        user_id = _get_active_user_id()

        try:
            # 1. Generate Metadata
            project_code = Study.generate_project_code(user_id)
            
            # CONSISTENT NAMING LOGIC:
            # strictly use secure_filename to avoid "tudy" vs "Study" issues
            safe_name = secure_filename(study_name) 
            map_filename = f"{safe_name}.json"
            base_csv_name = f"{safe_name}.csv"

            # 2. Create DB Record
            new_study = Study(
                name=study_name,
                map_filename=map_filename, # This is the Source of Truth
                topic=request.form.get('study_topic', ''),
                description=request.form.get('study_description', ''),
                user_id=user_id,
                project_code=project_code,
            )
            db.session.add(new_study)
            db.session.commit()

            # 3. Seed the TEMP Workspace
            # Use exactly the same 'base_csv_name' derived from the 'safe_name'
            WorkspaceManager.save_file(user_id, project_code, base_csv_name, uploaded_file)
            
            flash(f"Project initialized. Workspace ready.", 'success')
            return redirect(url_for('file_mgt.project_admin', study_id=new_study.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Creation failed: {e}", 'danger')
            return redirect(url_for('file_mgt.new_project'))

    return render_template('new_project.html', existing_studies=Study.query.all(), active_page='new')

@file_mgt_bp.route('/admin/<int:study_id>')
@login_required
def project_admin(study_id):
    study = Study.query.get_or_404(study_id)
    
    # Check if we have data in the TEMP workspace
    base_filename = study.map_filename.replace('.json', '.csv')
    content = WorkspaceManager.get_file(current_user.id, study.project_code, base_filename)
    
    preview_html = "Waiting for Local Sync..."
    if content:
        import pandas as pd
        import io
        try:
            df = pd.read_csv(io.StringIO(content), nrows=5)
            preview_html = df.to_html(classes='table table-sm table-striped small', index=False, border=0)
        except Exception as e:
            preview_html = f"Error reading cached data: {e}"

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




#===========================================================

#SIMULATION

#========================================================
@file_mgt_bp.route('/simulation/<int:study_id>')
@login_required
def simulation_setup(study_id):
    """
    Renders the Legacy Simulation Tool within the File Management context.
    """
    study = Study.query.get_or_404(study_id)
    
    # 1. Setup Session Data required by the tool/previews
    # This mimics what ops_routes used to do so previews work immediately
    base_name = study.map_filename.replace('.json', '')
    simulated_csv = f"simulated_{base_name}.csv"
    
    session['filenames'] = {
        'study_id': study.id,
        'original': f"{base_name}.csv",
        'map': study.map_filename,
        'output': simulated_csv,
        'graphs': [] 
    }

    # 2. Render the template you moved
    return render_template('simulation_tool.html', study=study, active_page='simulation')


#===========================================================
# SERVER WORKSPACE MANAGEMENT
#===========================================================

@file_mgt_bp.route('/workspace/sync_up/<int:study_id>', methods=['POST'])
@login_required
def sync_up(study_id):
    """
    Client -> Server (Hydration).
    The client pushes their local file to the server's temp workspace.
    """
    study = Study.query.get_or_404(study_id)
    
    files = request.files
    results = []
    
    try:
        for filename, file_obj in files.items():
            meta = WorkspaceManager.save_file(current_user.id, study.project_code, filename, file_obj)
            results.append(meta)
            
        return jsonify({'status': 'synced', 'files': results})
    except SecurityException as e:
        return jsonify({'error': str(e)}), 403

@file_mgt_bp.route('/workspace/sync_down/<int:study_id>/<filename>', methods=['GET'])
@login_required
def sync_down(study_id, filename):
    """
    Server -> Client (Persistence).
    The client pulls the calculated result from temp workspace to save locally.
    """
    study = Study.query.get_or_404(study_id)
    content = WorkspaceManager.get_file(current_user.id, study.project_code, filename)
    
    if content is None:
        return jsonify({'error': 'File not found in active workspace'}), 404
    
    # Calculate checksum for client verification
    checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    return jsonify({
        'filename': filename, 
        'content': content, 
        'checksum': checksum
    })

@file_mgt_bp.route('/workspace/close/<int:study_id>', methods=['POST'])
@login_required
def close_workspace(study_id):
    """
    Cleanup Hook. Called on logout or project switch.
    """
    study = Study.query.get_or_404(study_id)
    success = WorkspaceManager.destroy_workspace(current_user.id, study.project_code)
    return jsonify({'status': 'destroyed' if success else 'error'})