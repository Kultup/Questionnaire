#!/usr/bin/env python3
"""
Migration: add missing Telegram/email columns to users table if they don't exist.
"""

import os
import sqlite3

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'feedback_system.db'))

def run():
    print("Running migration: add missing columns to users...")
    print(f"DB path: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing user columns: {columns}")

        # Telegram group fields
        if 'telegram_group_name' not in columns:
            print("Adding users.telegram_group_name TEXT...")
            cursor.execute("ALTER TABLE users ADD COLUMN telegram_group_name TEXT")

        if 'telegram_group_link' not in columns:
            print("Adding users.telegram_group_link TEXT...")
            cursor.execute("ALTER TABLE users ADD COLUMN telegram_group_link TEXT")

        if 'telegram_group_enabled' not in columns:
            print("Adding users.telegram_group_enabled BOOLEAN DEFAULT 0 NOT NULL...")
            cursor.execute("ALTER TABLE users ADD COLUMN telegram_group_enabled BOOLEAN NOT NULL DEFAULT 0")

        # Bot token
        if 'bot_token' not in columns:
            print("Adding users.bot_token TEXT...")
            cursor.execute("ALTER TABLE users ADD COLUMN bot_token TEXT")

        # Email fields
        if 'email_address' not in columns:
            print("Adding users.email_address TEXT...")
            cursor.execute("ALTER TABLE users ADD COLUMN email_address TEXT")

        if 'email_enabled' not in columns:
            print("Adding users.email_enabled BOOLEAN DEFAULT 0 NOT NULL...")
            cursor.execute("ALTER TABLE users ADD COLUMN email_enabled BOOLEAN NOT NULL DEFAULT 0")

        # Unique token for survey links
        if 'unique_token' not in columns:
            print("Adding users.unique_token TEXT UNIQUE...")
            cursor.execute("ALTER TABLE users ADD COLUMN unique_token TEXT")
            # Can't add UNIQUE via ALTER in SQLite easily without table rebuild; we skip enforcing UNIQUE here.

        conn.commit()
        print("User migration finished successfully")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"User migration error: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    run()


