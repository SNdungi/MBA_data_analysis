import json
import os
import shutil
from flask import render_template, request, jsonify, flash, redirect, url_for, Blueprint,current_app
from flask_login import login_required, current_user
from app.app_database.extensions import db
from app.app_database.encoder_models import Study, ColumnEncoding, EncodingConfig,EncoderDefinition
from app.app_database.tutorials_models import TutorialLevel, TutorialSection, TutorialTopic, TutorialSubtopic
from app.app_utils import process_and_save_image

tuit_setup_bp = Blueprint('tuit_setup', __name__, template_folder='templates/tuit_setup', url_prefix='/tutorial_admin')



# =========================================================
#  TUTORIAL EDITOR ROUTES
# =========================================================

@tuit_setup_bp.route('/')
@login_required
def index():
    """Tutorial Editor Dashboard."""
    # CHANGED HERE: Use has_role()
    if not current_user.has_role('Admin'):
        flash("Access restricted.", "danger")
        return redirect(url_for('file_mgt.list_projects'))
        
    levels = TutorialLevel.query.order_by(TutorialLevel.id).all()
    return render_template('tuit_setup.html', levels=levels, active_page='tutorials')

@tuit_setup_bp.route('/api/sections/<int:level_id>')
@login_required
def get_sections(level_id):
    sections = TutorialSection.query.filter_by(level_id=level_id).order_by(TutorialSection.id).all()
    return jsonify([{'id': s.id, 'title': s.title} for s in sections])

@tuit_setup_bp.route('/api/topics/<int:section_id>')
@login_required
def get_topics(section_id):
    topics = TutorialTopic.query.filter_by(section_id=section_id).order_by(TutorialTopic.id).all()
    return jsonify([{'id': t.id, 'title': t.title} for t in topics])

@tuit_setup_bp.route('/api/subtopics/<int:topic_id>')
@login_required
def get_subtopics(topic_id):
    subs = TutorialSubtopic.query.filter_by(topic_id=topic_id).order_by(TutorialSubtopic.id).all()
    return jsonify([{'id': s.id, 'title': s.title} for s in subs])

@tuit_setup_bp.route('/api/subtopic_details/<int:sub_id>')
@login_required
def get_subtopic_details(sub_id):
    sub = TutorialSubtopic.query.get_or_404(sub_id)
    return jsonify({
        'id': sub.id,
        'title': sub.title,
        'short_description': sub.short_description,
        'definition_text': sub.definition_text,
        'video_url': sub.video_url,
        'examples': sub.examples if sub.examples else {} 
    })

# --- API: CRUD ACTIONS ---


# =========================================================
#  IMAGE UPLOAD ROUTE (Optimized)
# =========================================================

@tuit_setup_bp.route('/action/upload_image', methods=['POST'])
@login_required
def upload_image():
    """
    Handles async image uploads with compression.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        # Define absolute upload path
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'tutorials')
        
        # Call the Utility Function
        # This handles: validation, resizing (max 1200px), compression (80%), and saving
        filename = process_and_save_image(file, upload_dir, max_width=1200, quality=80)
        
        # Generate the Web URL
        url_path = url_for('static', filename=f'uploads/tutorials/{filename}')
        
        return jsonify({'location': url_path})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Upload Error: {e}") # Log error for server admin
        return jsonify({'error': 'Server could not process image.'}), 500

# ================================================================
# API: CRUD ACTIONS 
# -=============================================================

@tuit_setup_bp.route('/action/add_section', methods=['POST'])
@login_required
def add_section():
    try:
        title = request.form.get('title')
        level_id = request.form.get('level_id')
        new_sec = TutorialSection(title=title, level_id=level_id, description="")
        db.session.add(new_sec)
        db.session.commit()
        return jsonify({'status': 'success', 'id': new_sec.id, 'title': new_sec.title})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@tuit_setup_bp.route('/action/delete_section/<int:id>', methods=['DELETE'])
@login_required
def delete_section(id):
    sec = TutorialSection.query.get_or_404(id)
    if sec.topics:
        return jsonify({'status': 'error', 'message': 'Cannot delete: Section has Topics.'}), 400
    db.session.delete(sec)
    db.session.commit()
    return jsonify({'status': 'success'})

@tuit_setup_bp.route('/action/add_topic', methods=['POST'])
@login_required
def add_topic():
    try:
        title = request.form.get('title')
        section_id = request.form.get('section_id')
        new_topic = TutorialTopic(title=title, section_id=section_id, description="")
        db.session.add(new_topic)
        db.session.commit()
        return jsonify({'status': 'success', 'id': new_topic.id, 'title': new_topic.title})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@tuit_setup_bp.route('/action/delete_topic/<int:id>', methods=['DELETE'])
@login_required
def delete_topic(id):
    topic = TutorialTopic.query.get_or_404(id)
    if topic.subtopics:
        return jsonify({'status': 'error', 'message': 'Cannot delete: Topic has Subtopics.'}), 400
    db.session.delete(topic)
    db.session.commit()
    return jsonify({'status': 'success'})

@tuit_setup_bp.route('/action/save_subtopic', methods=['POST'])
@login_required
def save_subtopic():
    try:
        sub_id = request.form.get('subtopic_id') 
        topic_id = request.form.get('topic_id')
        
        examples_raw = request.form.get('examples')
        try:
            # Handle empty strings gracefully
            examples_json = json.loads(examples_raw) if examples_raw and examples_raw.strip() else {}
        except json.JSONDecodeError:
            return jsonify({'status': 'error', 'message': 'Invalid JSON in Examples field'}), 400

        if sub_id:
            # UPDATE
            sub = TutorialSubtopic.query.get_or_404(sub_id)
            sub.title = request.form.get('title')
            sub.short_description = request.form.get('short_description')
            sub.definition_text = request.form.get('definition_text')
            sub.video_url = request.form.get('video_url')
            sub.examples = examples_json
            msg = "Subtopic Updated"
        else:
            # CREATE
            sub = TutorialSubtopic(
                topic_id=topic_id,
                title=request.form.get('title'),
                short_description=request.form.get('short_description'),
                definition_text=request.form.get('definition_text'),
                video_url=request.form.get('video_url'),
                examples=examples_json
            )
            db.session.add(sub)
            msg = "Subtopic Created"

        db.session.commit()
        
        # CHANGE: Return the ID so the frontend knows which item to select
        return jsonify({'status': 'success', 'message': msg, 'id': sub.id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@tuit_setup_bp.route('/action/delete_subtopic/<int:id>', methods=['DELETE'])
@login_required
def delete_subtopic(id):
    sub = TutorialSubtopic.query.get_or_404(id)
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'status': 'success'})


# =========================================================
#  SYSTEM TOOLS & PURGE ROUTES (Moved from file_mgt)
# =========================================================

# --- HELPER ---
def _clear_folder_contents(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

# =========================================================
# ROUTES
# =========================================================

@tuit_setup_bp.route('/system')
@login_required
def system_tools():
    """Admin Dashboard: System Tools."""
    if not current_user.has_role('Admin'):
        flash("Access Denied: Administrative privileges required.", "danger")
        return redirect(url_for('file_mgt.list_projects'))

    all_studies = Study.query.all()
    return render_template('system_tools.html', active_page='system', studies=all_studies)

@tuit_setup_bp.route('/system/purge', methods=['POST'])
@login_required
def purge_system():
    """Secure Data Purge Logic."""
    if not current_user.has_role('Admin'):
        flash("Unauthorized action.", "danger")
        return redirect(url_for('file_mgt.list_projects'))
    
    retrieve_sec_key = current_app.config.get('PURGE_DATA_PW')

    security_key = request.form.get('security_key')
    if security_key != retrieve_sec_key:
        flash("Invalid Security Key.", "warning")
        return redirect(url_for('tuit_setup.system_tools'))

    target_id = request.form.get('study_id')

    try:
        if target_id == 'ALL_DATA':
            db.session.query(Study).delete()
            db.session.query(ColumnEncoding).delete()
            db.session.query(EncodingConfig).delete()
            db.session.query(EncoderDefinition).delete()
            db.session.commit()
            flash("SYSTEM PURGE COMPLETE. All data wiped.", "success")
        
        elif target_id and target_id.isdigit():
            study = Study.query.get(int(target_id))
            if study:
                # Delete associated files logic (simplified for brevity, assume same logic as before)
                base_name = study.map_filename.replace('.json', '')
                files = [
                    os.path.join(current_app.config['UPLOADS_FOLDER'], f"{base_name}.csv"),
                    os.path.join(current_app.config['GENERATED_FOLDER'], study.map_filename),
                    os.path.join(current_app.config['GENERATED_FOLDER'], f"simulated_{base_name}.csv")
                ]
                for f in files:
                    if os.path.exists(f): os.remove(f)

                db.session.delete(study)
                db.session.commit()
                flash(f"Purged study: '{study.name}'", "success")
            else:
                flash("Study ID not found.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Purge failed: {e}", 'danger')

    return redirect(url_for('tuit_setup.system_tools'))