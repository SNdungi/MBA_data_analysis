from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
import json

db = SQLAlchemy()

# -----------------------------------------------------------------------------
# 1. The Study: The top-level container for a project.
# -----------------------------------------------------------------------------
class Study(db.Model):
    __tablename__ = 'studies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    topic = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    map_filename = db.Column(db.String(255), unique=True, nullable=False)

    # RELATIONSHIPS: A Study has many EncoderDefinitions and many ColumnEncodings.
    # If a study is deleted, all its children definitions and column configs are also deleted.
    definitions = db.relationship('EncoderDefinition', back_populates='study', cascade='all, delete-orphan')
    column_encodings = db.relationship('ColumnEncoding', back_populates='study', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Study(id={self.id}, name='{self.name}')>"

# -----------------------------------------------------------------------------
# 2. Encoder Prototype: The "Dimension Table" of available encoder types.
#    This table is seeded once and rarely changes.
# -----------------------------------------------------------------------------
class EncoderPrototype(db.Model):
    __tablename__ = 'encoder_prototypes'
    id = db.Column(db.Integer, primary_key=True)
    # The name the user sees, e.g., "5-Point Likert", "Yes/No Binary"
    name = db.Column(db.String(100), unique=True, nullable=False)
    # The internal type used by the DataEncoder class: 'Likert', 'Ordinal', 'Nominal', 'Binary'
    encoder_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<EncoderPrototype(name='{self.name}', type='{self.encoder_type}')>"

# -----------------------------------------------------------------------------
# 3. Encoder Definition: A user's specific, saved "recipe" for an encoder.
#    This links a Study to a Prototype and stores the user's custom configuration.
# -----------------------------------------------------------------------------
class EncoderDefinition(db.Model):
    __tablename__ = 'encoder_definitions'
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('studies.id'), nullable=False)
    prototype_id = db.Column(db.Integer, db.ForeignKey('encoder_prototypes.id'), nullable=False)
    # A user-friendly alias, e.g., "My Satisfaction Scale", "Experience Levels"
    name = db.Column(db.String(255), nullable=False)
    # The actual JSON config, e.g., {"Strongly Disagree": 1, ...} or {"order": ["A", "B"]}
    configuration = db.Column(JSON, nullable=False)

    # RELATIONSHIPS
    study = db.relationship('Study', back_populates='definitions')
    prototype = db.relationship('EncoderPrototype')
    # This definition can be assigned to many columns
    column_assignments = db.relationship('ColumnEncoding', back_populates='encoder_definition')
    
    __table_args__ = (db.UniqueConstraint('study_id', 'name', name='_study_definition_name_uc'),)

    def __repr__(self):
        return f"<EncoderDefinition(name='{self.name}', study_id={self.study_id})>"

# -----------------------------------------------------------------------------
# 4. Column Encoding: The final "Fact Table".
#    This maps a specific question/column from a study to a user-defined EncoderDefinition.
# -----------------------------------------------------------------------------
class ColumnEncoding(db.Model):
    __tablename__ = 'column_encodings'
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('studies.id'), nullable=False)
    encoder_definition_id = db.Column(db.Integer, db.ForeignKey('encoder_definitions.id'), nullable=True)
    
    column_key = db.Column(db.String(50), nullable=False)
    original_name = db.Column(db.Text, nullable=False)

    # RELATIONSHIPS
    study = db.relationship('Study', back_populates='column_encodings')
    encoder_definition = db.relationship('EncoderDefinition', back_populates='column_assignments')

    __table_args__ = (db.UniqueConstraint('study_id', 'column_key', name='_study_column_key_uc'),)

    def __repr__(self):
        return f"<ColumnEncoding(key='{self.column_key}', definition_id={self.encoder_definition_id})>"