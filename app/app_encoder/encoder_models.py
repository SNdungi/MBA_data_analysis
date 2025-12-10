from app.app_database.extensions import db
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin 



# -----------------------------------------------------------------------------  
# User model  
# -----------------------------------------------------------------------------  
class User(UserMixin, db.Model):  
    __tablename__ = 'users'  
    id = db.Column(db.Integer, primary_key=True)  
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)  
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)  
    password_hash = db.Column(db.String(256))  

    # A user can have many studies  
    studies = db.relationship('Study', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')  

    def set_password(self, password):  
        self.password_hash = generate_password_hash(password)  

    def check_password(self, password):  
        return check_password_hash(self.password_hash, password)  

    def __repr__(self):  
        return f'<User {self.username}>'  


# -----------------------------------------------------------------------------  
# Study model  
# -----------------------------------------------------------------------------  
class Study(db.Model):  
    __tablename__ = 'studies'  
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(255), unique=True, nullable=False)  
    topic = db.Column(db.String(255))  
    description = db.Column(db.Text)  
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())  
    map_filename = db.Column(db.String(255), unique=True, nullable=False)  

    # Foreign key to User  
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  

    # Relationships  
    user = db.relationship('User', back_populates='studies')  
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
    
class EncodingConfig(db.Model):
    """
    SQLAlchemy ORM model for storing encoding configurations for dataset columns.
    Each row represents the configuration for a single column.
    """
    __tablename__ = 'encoding_configs'

    id = db.Column(db.Integer, primary_key=True)
    map_filename = db.Column(db.String(255), nullable=False)
    column_key = db.Column(db.String(50), nullable=False)
    original_name = db.Column(db.String, nullable=False)
    
    # The type of encoding to apply: 'None', 'Ordinal', 'Nominal', 'Likert'
    encoder_type = db.Column(db.String(50), default='None', nullable=False)
    
    # A flexible JSON field to store metadata for the encoder
    # e.g., {"order": ["Low", "High"]}, {"scale": "likert_5_point", "is_reverse": false}
    encoder_config = db.Column(JSON, default=lambda: {})

    # Ensures that you can't have two rows with the same map_filename and column_key
    __table_args__ = (db.UniqueConstraint('map_filename', 'column_key', name='_map_column_uc'),)

    def __repr__(self):
        return f"<EncodingConfig(map='{self.map_filename}', key='{self.column_key}', type='{self.encoder_type}')>"