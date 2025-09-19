#!/usr/bin/env python3
"""
SQLite migration script to add telegram_group_enabled field
"""

import os
import sqlite3
from app import app, db

def migrate_sqlite():
    """Add telegram_group_enabled column to users table"""
    
    with app.app_context():
        # Get the database path
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        print(f"Migrating SQLite database: {db_path}")
        
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'telegram_group_enabled' not in columns:
                # Add the new column
                cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN telegram_group_enabled BOOLEAN DEFAULT 0 NOT NULL
                """)
                
                print("✓ Added telegram_group_enabled column to users table")
                
                # Update existing users to have telegram_group_enabled = True if they have a group_id
                cursor.execute("""
                    UPDATE users 
                    SET telegram_group_enabled = 1 
                    WHERE telegram_group_id IS NOT NULL AND telegram_group_id != ''
                """)
                
                updated_rows = cursor.rowcount
                print(f"✓ Updated {updated_rows} existing users with group IDs")
                
                conn.commit()
            else:
                print("✓ telegram_group_enabled column already exists")
                
        except Exception as e:
            print(f"ERROR: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
            
        return True

if __name__ == '__main__':
    print("🚀 Running SQLite migration...")
    print("=" * 40)
    
    if migrate_sqlite():
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")