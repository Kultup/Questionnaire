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

def migrate_database():
    """Apply database migrations for new fields and tables"""
    
    try:
        # Import Flask app and database
        from app import app, db
        
        with app.app_context():
            # Check if we're using SQLite (development) or PostgreSQL (production)
            database_url = os.getenv('DATABASE_URL', '')
            
            print("🔄 Starting database migration process...")
            
            # Create migration version table if it doesn't exist
            create_migration_table()
            
            # Get current migration version
            current_version = get_migration_version()
            print(f"📊 Current migration version: {current_version}")
            
            # Apply migrations based on database type
            if database_url.startswith('postgresql://'):
                print("🐘 Applying PostgreSQL migrations...")
                success = migrate_postgresql(current_version)
            else:
                print("🗃️ Applying SQLite migrations...")
                success = migrate_sqlite(current_version)
            
            if success:
                print("✅ Database migrations applied successfully")
                return True
            else:
                print("❌ Some migrations failed")
                return False
                
    except ImportError as e:
        print(f"ERROR: Failed to import required modules: {e}")
        print("Make sure Flask app and models are properly configured")
        return False
    except Exception as e:
        print(f"ERROR: Failed to apply migrations: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_migration_table():
    """Create migration version tracking table"""
    
    try:
        import sqlite3
        
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            # PostgreSQL version
            conn = get_postgresql_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_versions (
                    id SERIAL PRIMARY KEY,
                    version INTEGER NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
        else:
            # SQLite version - use direct sqlite3 connection
            
            # Extract database path from URL
            if database_url.startswith('sqlite:///'):
                db_path = database_url[10:]  # Remove 'sqlite:///'
            else:
                db_path = 'instance/feedback_system.db'
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
                
        print("✓ Migration version table ready")
        
    except Exception as e:
        print(f"WARNING: Could not create migration table: {e}")
        import traceback
        traceback.print_exc()

def get_migration_version():
    """Get current migration version"""
    
    try:
        import sqlite3
        
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            # PostgreSQL version
            conn = get_postgresql_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT MAX(version) FROM migration_versions")
            result = cursor.fetchone()
            version = result[0] if result and result[0] is not None else 0
            
            cursor.close()
            conn.close()
            
        else:
            # SQLite version - use direct connection
            
            # Extract database path from URL
            if database_url.startswith('sqlite:///'):
                db_path = database_url[10:]  # Remove 'sqlite:///'
            else:
                db_path = 'instance/feedback_system.db'
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM migration_versions")
            result = cursor.fetchone()
            version = result[0] if result and result[0] is not None else 0
            cursor.close()
            conn.close()
                
        return version
        
    except Exception as e:
        print(f"INFO: Could not get migration version (probably first run): {e}")
        return 0

def set_migration_version(version, description=""):
    """Set migration version as completed"""
    
    try:
        import sqlite3
        
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            # PostgreSQL version
            conn = get_postgresql_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO migration_versions (version, description) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                (version, description)
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
        else:
            # SQLite version - use direct connection
            
            # Extract database path from URL
            if database_url.startswith('sqlite:///'):
                db_path = database_url[10:]  # Remove 'sqlite:///'
            else:
                db_path = 'instance/feedback_system.db'
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO migration_versions (version, description) VALUES (?, ?)",
                (version, description)
            )
            conn.commit()
            cursor.close()
            conn.close()
                
        print(f"✓ Migration version {version} marked as completed")
        
    except Exception as e:
        print(f"WARNING: Could not set migration version: {e}")

def get_postgresql_connection():
    """Get PostgreSQL connection from DATABASE_URL"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL not found")
    
    # Parse DATABASE_URL
    url_parts = database_url.replace('postgresql://', '').split('/')
    db_name = url_parts[1] if len(url_parts) > 1 else 'feedback_system_prod'
    
    connection_part = url_parts[0]
    auth_part, host_part = connection_part.split('@')
    username, password = auth_part.split(':')
    
    if ':' in host_part:
        host, port = host_part.split(':')
    else:
        host = host_part
        port = '5432'
    
    return psycopg2.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=db_name
    )

def migrate_postgresql(current_version=0):
    """Apply PostgreSQL specific migrations"""
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        
        success = True
        
        # Migration version 1: Basic tables
        if current_version < 1:
            print("Applying migration 1: Basic tables...")
            
            # Check if tables exist and create if needed
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # Create tables if they don't exist
            if 'users' not in existing_tables:
                cursor.execute("""
                    CREATE TABLE users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(80) UNIQUE NOT NULL,
                        email VARCHAR(120) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        is_admin BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✓ Created users table")
            
            if 'questionnaires' not in existing_tables:
                cursor.execute("""
                    CREATE TABLE questionnaires (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        user_id INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                print("✓ Created questionnaires table")
            
            if 'questions' not in existing_tables:
                cursor.execute("""
                    CREATE TABLE questions (
                        id SERIAL PRIMARY KEY,
                        questionnaire_id INTEGER REFERENCES questionnaires(id),
                        question_text TEXT NOT NULL,
                        question_type VARCHAR(50) DEFAULT 'text',
                        options TEXT,
                        is_required BOOLEAN DEFAULT FALSE,
                        order_index INTEGER DEFAULT 0
                    )
                """)
                print("✓ Created questions table")
            
            if 'responses' not in existing_tables:
                cursor.execute("""
                    CREATE TABLE responses (
                        id SERIAL PRIMARY KEY,
                        questionnaire_id INTEGER REFERENCES questionnaires(id),
                        user_id INTEGER REFERENCES users(id),
                        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✓ Created responses table")
            
            if 'answers' not in existing_tables:
                cursor.execute("""
                    CREATE TABLE answers (
                        id SERIAL PRIMARY KEY,
                        response_id INTEGER REFERENCES responses(id),
                        question_id INTEGER REFERENCES questions(id),
                        answer_text TEXT
                    )
                """)
                print("✓ Created answers table")
            
            set_migration_version(1, "Basic tables created")
        
        # Migration version 2: Enhanced user features
        if current_version < 2:
            print("Applying migration 2: Enhanced user features...")
            
            # Add new columns to users table if they don't exist
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
            """)
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            if 'last_login' not in existing_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
                print("✓ Added last_login column to users")
            
            if 'profile_picture' not in existing_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(255)")
                print("✓ Added profile_picture column to users")
            
            if 'bio' not in existing_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
                print("✓ Added bio column to users")
            
            set_migration_version(2, "Enhanced user features")
        
        # Migration version 3: Questionnaire improvements
        if current_version < 3:
            print("Applying migration 3: Questionnaire improvements...")
            
            # Add new columns to questionnaires table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'questionnaires' AND table_schema = 'public'
            """)
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            if 'category' not in existing_columns:
                cursor.execute("ALTER TABLE questionnaires ADD COLUMN category VARCHAR(100)")
                print("✓ Added category column to questionnaires")
            
            if 'tags' not in existing_columns:
                cursor.execute("ALTER TABLE questionnaires ADD COLUMN tags TEXT")
                print("✓ Added tags column to questionnaires")
            
            if 'max_responses' not in existing_columns:
                cursor.execute("ALTER TABLE questionnaires ADD COLUMN max_responses INTEGER")
                print("✓ Added max_responses column to questionnaires")
            
            if 'expires_at' not in existing_columns:
                cursor.execute("ALTER TABLE questionnaires ADD COLUMN expires_at TIMESTAMP")
                print("✓ Added expires_at column to questionnaires")
            
            set_migration_version(3, "Questionnaire improvements")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✓ PostgreSQL migration completed successfully")
        return success
        
    except Exception as e:
        print(f"ERROR: PostgreSQL migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrate_sqlite(current_version=0):
    """Apply SQLite specific migrations"""
    
    try:
        import os
        import sqlite3
        
        database_url = os.getenv('DATABASE_URL', '')
        
        # Extract database path from URL
        if database_url.startswith('sqlite:///'):
            db_path = database_url[10:]  # Remove 'sqlite:///'
        else:
            db_path = 'instance/feedback_system.db'
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        success = True
        
        # Migration version 1: Basic tables
        if current_version < 1:
            print("Applying migration 1: Basic tables...")
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    profile_picture VARCHAR(255),
                    bio TEXT
                )
            """)
            
            # Create questionnaires table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questionnaires (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    category VARCHAR(100),
                    tags TEXT,
                    max_responses INTEGER,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            """)
            
            # Create questions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    questionnaire_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type VARCHAR(50) NOT NULL,
                    options TEXT,
                    is_required BOOLEAN DEFAULT FALSE,
                    order_index INTEGER DEFAULT 0,
                    FOREIGN KEY (questionnaire_id) REFERENCES questionnaires (id)
                )
            """)
            
            # Create responses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    questionnaire_id INTEGER NOT NULL,
                    user_id INTEGER,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    FOREIGN KEY (questionnaire_id) REFERENCES questionnaires (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Create answers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT,
                    FOREIGN KEY (response_id) REFERENCES responses (id),
                    FOREIGN KEY (question_id) REFERENCES questions (id)
                )
            """)
            
            conn.commit()
            print("✓ Created all basic tables")
            set_migration_version(1, "Basic tables created")
        
        # Migration version 2: Enhanced user features (already included in v1)
        if current_version < 2:
            print("Applying migration 2: Enhanced user features...")
            print("✓ User enhancements already included in table structure")
            set_migration_version(2, "Enhanced user features")
        
        # Migration version 3: Questionnaire improvements (already included in v1)
        if current_version < 3:
            print("Applying migration 3: Questionnaire improvements...")
            print("✓ Questionnaire improvements already included in table structure")
            set_migration_version(3, "Questionnaire improvements")
        
        cursor.close()
        conn.close()
        
        print("✓ SQLite migration completed successfully")
        return success
        
    except Exception as e:
        print(f"ERROR: SQLite migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_and_apply_migrations():
    """Check current migration version and apply pending migrations"""
    
    try:
        print("Checking migration status...")
        
        # Create migration table if it doesn't exist
        create_migration_table()
        
        # Get current migration version
        current_version = get_migration_version()
        print(f"Current migration version: {current_version}")
        
        # Define latest migration version
        latest_version = 3
        
        if current_version >= latest_version:
            print("✓ Database is up to date!")
            return True
        
        print(f"Applying migrations from version {current_version} to {latest_version}...")
        
        # Apply migrations based on database type
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            success = migrate_postgresql(current_version)
        else:
            success = migrate_sqlite(current_version)
        
        if success:
            print("✓ All migrations applied successfully!")
        else:
            print("✗ Some migrations failed!")
        
        return success
        
    except Exception as e:
        print(f"ERROR: Migration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def rollback_migration(target_version):
    """Rollback to a specific migration version (for development)"""
    
    try:
        print(f"Rolling back to migration version {target_version}...")
        
        current_version = get_migration_version()
        
        if target_version >= current_version:
            print("Target version is not lower than current version")
            return False
        
        # For safety, we'll just update the version number
        # In production, you'd want proper rollback scripts
        from app import app, db
        
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            conn = get_postgresql_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM migration_versions WHERE version > %s", (target_version,))
            conn.commit()
            cursor.close()
            conn.close()
        else:
            with app.app_context():
                db.engine.execute("DELETE FROM migration_versions WHERE version > ?", (target_version,))
        
        print(f"✓ Rolled back to version {target_version}")
        return True
        
    except Exception as e:
        print(f"ERROR: Rollback failed: {e}")
        return False

def get_migration_status():
    """Get detailed migration status information"""
    
    try:
        create_migration_table()
        
        current_version = get_migration_version()
        latest_version = 3
        
        print(f"Migration Status:")
        print(f"  Current Version: {current_version}")
        print(f"  Latest Version: {latest_version}")
        print(f"  Status: {'Up to date' if current_version >= latest_version else 'Pending migrations'}")
        
        # Show applied migrations
        from app import app, db
        
        database_url = os.getenv('DATABASE_URL', '')
        
        if database_url.startswith('postgresql://'):
            conn = get_postgresql_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT version, description, applied_at FROM migration_versions ORDER BY version")
            migrations = cursor.fetchall()
            cursor.close()
            conn.close()
        else:
            with app.app_context():
                result = db.engine.execute("SELECT version, description, applied_at FROM migration_versions ORDER BY version")
                migrations = result.fetchall()
        
        if migrations:
            print("\nApplied Migrations:")
            for version, description, applied_at in migrations:
                print(f"  Version {version}: {description} (applied: {applied_at})")
        else:
            print("\nNo migrations applied yet")
        
        return {
            'current_version': current_version,
            'latest_version': latest_version,
            'is_up_to_date': current_version >= latest_version,
            'applied_migrations': migrations
        }
        
    except Exception as e:
        print(f"ERROR: Could not get migration status: {e}")
        return None

def main():
    """Main setup function"""
    
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        print("🚀 Setting up production PostgreSQL database...")
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
        
        print("\nNext steps:")
        print("1. Update your .env file with correct DATABASE_URL")
        print("2. Set FLASK_ENV=production")
        print("3. Run your application")
    else:
        print("🚀 Setting up SQLite database...")
        print("=" * 50)
        
        # For SQLite, we just need to run migrations
        print("1. Setting up database and applying migrations...")
    
    # Step 3: Apply migrations (works for both PostgreSQL and SQLite)
    print("\n2. Applying database migrations...")
    if not check_and_apply_migrations():
        print("❌ Migration failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ Database setup completed successfully!")
    
    if not database_url.startswith('postgresql://'):
        print("\nSQLite database created in instance/ folder")
        print("You can now run your application with: python app.py")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            get_migration_status()
        elif command == "migrate":
            check_and_apply_migrations()
        elif command == "rollback" and len(sys.argv) > 2:
            target_version = int(sys.argv[2])
            rollback_migration(target_version)
        else:
            print("Usage:")
            print("  python database_setup.py          - Run migrations")
            print("  python database_setup.py status   - Show migration status")
            print("  python database_setup.py migrate  - Apply pending migrations")
            print("  python database_setup.py rollback <version> - Rollback to version")
    else:
        main()