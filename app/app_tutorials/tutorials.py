from flask import Blueprint, render_template, abort
from app.app_database.tutorials_models import TutorialLevel, TutorialTopic, TutorialSubtopic

tutorials_bp = Blueprint('tutorials', __name__, template_folder='templates', url_prefix='/tutorials')

@tutorials_bp.route('/')
def index():
    # Load just the levels/sections for the sidebar
    # FIX: Changed .order to .id because 'order' column doesn't exist
    levels = TutorialLevel.query.order_by(TutorialLevel.id).all()
    return render_template('tutorials/base_tutorials.html', levels=levels)

@tutorials_bp.route('/topic/<int:topic_id>')
def view_topic(topic_id):
    """
    Called when clicking a Topic in Col 1.
    Loads Col 2 (Subtopics) but leaves Col 3 (Content) empty or intro.
    """
    # FIX: Changed .order to .id
    levels = TutorialLevel.query.order_by(TutorialLevel.id).all()
    topic = TutorialTopic.query.get_or_404(topic_id)
    
    # Pass 'active_topic' to trigger the 3-column layout
    return render_template('tutorials/base_tutorials.html', 
                           levels=levels, 
                           active_topic=topic)

@tutorials_bp.route('/lesson/<int:subtopic_id>')
def view(subtopic_id):
    """
    Called when clicking a Subtopic in Col 2.
    Loads Col 3 (Content).
    """
    # FIX: Changed .order to .id
    levels = TutorialLevel.query.order_by(TutorialLevel.id).all()
    subtopic = TutorialSubtopic.query.get_or_404(subtopic_id)
    
    # Pass active_subtopic so the template knows what to render in Col 3
    # and what to highlight in Col 2.
    return render_template('tutorials/view_tutorials.html', 
                           levels=levels, 
                           active_subtopic=subtopic)