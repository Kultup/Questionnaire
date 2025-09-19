#!/usr/bin/env python3
"""
Database setup script for production PostgreSQL configuration
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
load_dotenv()

def create_database():
    """Create PostgreSQL database if it doesn't exist"""
    
    # Parse DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        return False
    
    # Extract connection parameters
    try:
        # Format: postgresql://username:password@host:port/database
        url_parts = database_url.replace('postgresql://', '').split('/')
        db_name = url_parts[1] if len(url_parts) > 1 else 'feedback_system_prod'
        
        connection_part = url_parts[0]
        if '@' in connection_part:
            auth_part, host_part = connection_part.split('@')
            username, password = auth_part.split(':')
            
            if ':' in host_part:
                host, port = host_part.split(':')
            else:
                host = host_part
                port = '5432'
        else:
            print("ERROR: Invalid DATABASE_URL format")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to parse DATABASE_URL: {e}")
        return False
    
    try:
        # Connect to PostgreSQL server (not to specific database)
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database='postgres'  # Connect to default postgres database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()
        
        if not exists:
            # Create database
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✓ Database '{db_name}' created successfully")
        else:
            print(f"✓ Database '{db_name}' already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"ERROR: Failed to create database: {e}")
        return False

def setup_database_tables():
    """Initialize database tables using Flask app context"""
    
    try:
        # Import Flask app and initialize database
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✓ Database tables created successfully")
            return True
            
    except Exception as e:
        print(f"ERROR: Failed to create tables: {e}")
        return False

def main():
    """Main setup function"""
    
    print("🚀 Setting up production database...")
    print("=" * 50)
    
    # Step 1: Create database
    print("1. Creating PostgreSQL database...")
    if not create_database():
        print("❌ Database creation failed")
        sys.exit(1)
    
    # Step 2: Create tables
    print("\n2. Creating database tables...")
    if not setup_database_tables():
        print("❌ Table creation failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ Database setup completed successfully!")
    print("\nNext steps:")
    print("1. Update your .env file with correct DATABASE_URL")
    print("2. Set FLASK_ENV=production")
    print("3. Run your application")

if __name__ == '__main__':
    main()