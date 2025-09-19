#!/usr/bin/env python3
"""
Database initialization script for SQLite
"""

import os
import sqlite3
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Create Flask app
app = Flask(__name__)

# Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_file_path = os.path.join(basedir, 'instance', 'feedback_system.db')

# Ensure instance directory exists
instance_dir = os.path.join(basedir, 'instance')
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)
    print(f"Created instance directory: {instance_dir}")

# Configure database
default_db_path = f"sqlite:///{db_file_path.replace(os.sep, '/')}"
app.config['SQLALCHEMY_DATABASE_URI'] = default_db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"Database path: {db_file_path}")
print(f"Database URI: {default_db_path}")

# Initialize SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

# Import models
from models import User, Question, Survey, Answer, QRCode, Admin

def init_database():
    """Initialize the database with tables"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            print("Database tables created successfully!")
            
            # Check if database file was created
            if os.path.exists(db_file_path):
                print(f"Database file created: {db_file_path}")
                file_size = os.path.getsize(db_file_path)
                print(f"Database file size: {file_size} bytes")
            else:
                print("ERROR: Database file was not created!")
                
    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("Initializing SQLite database...")
    success = init_database()
    if success:
        print("Database initialization completed successfully!")
    else:
        print("Database initialization failed!")