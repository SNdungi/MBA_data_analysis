from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import JSON # Use the JSON type for our config field

# We will initialize this 'db' object in our app factory
db = SQLAlchemy()

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