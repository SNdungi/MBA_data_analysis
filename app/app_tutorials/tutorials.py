from flask import Blueprint, render_template, abort
from app.app_database.tutorials_models import TutorialLevel, TutorialSubtopic

tutorials_bp = Blueprint('tutorials', __name__, template_folder='templates', url_prefix='/tutorials')

def get_sidebar_data():
    """Helper to fetch the full curriculum hierarchy for the sidebar."""
    # We order by ID to ensure they appear in the logical order of insertion/seeding
    return TutorialLevel.query.order_by(TutorialLevel.id).all()

@tutorials_bp.route('/')
def index():
    """Landing page: Show sidebar but no active topic."""
    levels = get_sidebar_data()
    return render_template('tutorials/view_tutorials.html', 
                           levels=levels, 
                           active_subtopic=None)

@tutorials_bp.route('/<int:subtopic_id>')
def view(subtopic_id):
    """View a specific subtopic content."""
    levels = get_sidebar_data()
    
    # Fetch the specific subtopic or 404 if not found
    subtopic = TutorialSubtopic.query.get_or_404(subtopic_id)
    
    return render_template('tutorials/view_tutorials.html', 
                           levels=levels, 
                           active_subtopic=subtopic)