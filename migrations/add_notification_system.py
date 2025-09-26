"""
Database migration to add notification system tables
"""

import sqlite3
import os
from datetime import datetime

def run_migration():
    """Run the migration to add notification system tables"""
    
    # Get database path
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'feedback_system.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create notification_settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_enabled BOOLEAN DEFAULT 1,
                email_enabled BOOLEAN DEFAULT 1,
                max_retries INTEGER DEFAULT 3,
                retry_delay INTEGER DEFAULT 60,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Create notification_queue table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notification_type VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP NULL,
                error_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_status ON notification_queue(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_scheduled ON notification_queue(scheduled_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_user ON notification_queue(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_settings_user ON notification_settings(user_id)')
        
        # Create default notification settings for existing users
        cursor.execute('''
            INSERT INTO notification_settings (user_id, telegram_enabled, email_enabled)
            SELECT id, 
                   CASE WHEN telegram_group_enabled = 1 AND bot_token IS NOT NULL AND bot_token != '' THEN 1 ELSE 0 END,
                   CASE WHEN email_enabled = 1 AND email_address IS NOT NULL AND email_address != '' THEN 1 ELSE 0 END
            FROM users 
            WHERE id NOT IN (SELECT user_id FROM notification_settings)
        ''')
        
        conn.commit()
        print("Migration completed successfully!")
        print(f"- Created notification_settings table")
        print(f"- Created notification_queue table")
        print(f"- Created indexes for performance")
        print(f"- Migrated existing user notification settings")
        
        # Show statistics
        cursor.execute('SELECT COUNT(*) FROM notification_settings')
        settings_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM notification_queue')
        queue_count = cursor.fetchone()[0]
        
        print(f"- {settings_count} notification settings created")
        print(f"- {queue_count} items in notification queue")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("Running notification system migration...")
    success = run_migration()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")