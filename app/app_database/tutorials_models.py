from datetime import datetime
from app.app_database.extensions import db
from sqlalchemy.dialects.sqlite import JSON


class TutorialLevel(db.Model):
    """
    Macro tutorial levels:
    - Elementary (pre-graduate)
    - Graduate
    - Postgraduate/PhD
    """
    __tablename__ = "tutorial_levels"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)

    # RELATIONSHIPS
    sections = db.relationship(
        "TutorialSection",
        back_populates="level",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<TutorialLevel {self.title}>"


class TutorialSection(db.Model):
    """
    Major sections within each level:
    - Foundations
    - Probability
    - Inference
    - Regression
    - Time Series, etc.
    """
    __tablename__ = "tutorial_sections"

    id = db.Column(db.Integer, primary_key=True)
    level_id = db.Column(db.Integer, db.ForeignKey("tutorial_levels.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # RELATIONSHIPS
    level = db.relationship("TutorialLevel", back_populates="sections")
    topics = db.relationship(
        "TutorialTopic",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<TutorialSection {self.title}>"


class TutorialTopic(db.Model):
    """
    Topics under each section:
    - Central Tendency
    - Probability Distributions
    - Regression Concepts
    - Inference Basics, etc.
    """
    __tablename__ = "tutorial_topics"

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("tutorial_sections.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # RELATIONSHIPS
    section = db.relationship("TutorialSection", back_populates="topics")
    subtopics = db.relationship(
        "TutorialSubtopic",
        back_populates="topic",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<TutorialTopic {self.title}>"


class TutorialSubtopic(db.Model):
    """
    Actual educational content units:
    Example:
      - Topic: Central Tendency
      - Subtopic: Arithmetic Mean

    Each includes:
      - Definition text (MathText/LaTeX/plain)
      - Video link
      - JSON-based examples structure
    """
    __tablename__ = "tutorial_subtopics"

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("tutorial_topics.id"), nullable=False)

    # Basic metadata
    title = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.Text)

    # Core educational content
    definition_text = db.Column(db.Text)         # Supports MathText, LaTeX, plain text
    video_url = db.Column(db.String(300))        # External video link or embed URL

    # JSON: supports formulas, text examples, images, exam question excerpts
    examples = db.Column(JSON, default=dict)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # RELATIONSHIPS
    topic = db.relationship("TutorialTopic", back_populates="subtopics")

    def __repr__(self):
        return f"<TutorialSubtopic {self.title}>"
