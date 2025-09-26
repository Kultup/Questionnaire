#!/usr/bin/env python3
"""
Migration runner script
Automatically runs all migrations from the migrations folder
"""

import os
import sys
import importlib.util
import sqlite3
from datetime import datetime

def get_database_path():
    """Get the database file path"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(basedir, 'instance', 'feedback_system.db')

def create_migration_table():
    """Create migration tracking table if it doesn't exist"""
    db_path = get_database_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating migration table: {e}")
        return False

def is_migration_executed(migration_name):
    """Check if migration has already been executed"""
    db_path = get_database_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM migration_history WHERE migration_name = ?",
            (migration_name,)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    except Exception as e:
        print(f"Error checking migration status: {e}")
        return False

def mark_migration_executed(migration_name):
    """Mark migration as executed"""
    db_path = get_database_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO migration_history (migration_name) VALUES (?)",
            (migration_name,)
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking migration as executed: {e}")
        return False

def get_migration_files():
    """Get all migration files from migrations directory"""
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    
    if not os.path.exists(migrations_dir):
        print(f"Migrations directory not found: {migrations_dir}")
        return []
    
    migration_files = []
    for filename in os.listdir(migrations_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            migration_files.append(filename)
    
    # Sort migrations to ensure consistent execution order
    migration_files.sort()
    return migration_files

def run_migration_file(migration_file):
    """Run a single migration file"""
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    migration_path = os.path.join(migrations_dir, migration_file)
    migration_name = migration_file[:-3]  # Remove .py extension
    
    try:
        # Load the migration module
        spec = importlib.util.spec_from_file_location(migration_name, migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Check if migration has run_migration function
        if hasattr(migration_module, 'run_migration'):
            print(f"Running migration: {migration_name}")
            
            # Execute the migration
            result = migration_module.run_migration()
            
            if result:
                # Mark as executed
                if mark_migration_executed(migration_name):
                    print(f"✓ Migration {migration_name} completed successfully")
                    return True
                else:
                    print(f"✗ Failed to mark migration {migration_name} as executed")
                    return False
            else:
                print(f"✗ Migration {migration_name} failed")
                return False
        else:
            print(f"✗ Migration {migration_name} does not have run_migration function")
            return False
            
    except Exception as e:
        print(f"✗ Error running migration {migration_name}: {e}")
        return False

def run_all_migrations():
    """Run all pending migrations"""
    print("Starting migration process...")
    
    # Check if database exists
    db_path = get_database_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Please run init_db.py first to create the database")
        return False
    
    # Create migration tracking table
    if not create_migration_table():
        print("Failed to create migration tracking table")
        return False
    
    # Get all migration files
    migration_files = get_migration_files()
    
    if not migration_files:
        print("No migration files found")
        return True
    
    print(f"Found {len(migration_files)} migration files")
    
    # Run each migration
    executed_count = 0
    skipped_count = 0
    failed_count = 0
    
    for migration_file in migration_files:
        migration_name = migration_file[:-3]  # Remove .py extension
        
        if is_migration_executed(migration_name):
            print(f"⏭ Skipping {migration_name} (already executed)")
            skipped_count += 1
            continue
        
        if run_migration_file(migration_file):
            executed_count += 1
        else:
            failed_count += 1
            break  # Stop on first failure
    
    # Print summary
    print("\n" + "="*50)
    print("Migration Summary:")
    print(f"Executed: {executed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")
    print("="*50)
    
    return failed_count == 0

def main():
    """Main function"""
    print("Database Migration Runner")
    print("="*50)
    
    success = run_all_migrations()
    
    if success:
        print("\n✓ All migrations completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Migration process failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()