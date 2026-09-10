import os
import sys
import logging
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [INIT_LOCAL_DB] %(message)s'
)
logger = logging.getLogger("InitLocalDB")

# Load environment variables from .env
load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Manish9934")
DB_NAME = os.environ.get("DB_NAME", "smart_village")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "manishmaurya9934@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Manish@9934")

def init_mysql():
    try:
        import mysql.connector
    except ImportError:
        logger.error("mysql-connector-python is not installed. Run: pip install mysql-connector-python")
        return False

    logger.info(f"Connecting to MySQL server at {DB_HOST}:{DB_PORT} as '{DB_USER}'...")
    
    # 1. Connect without selecting database to create database if missing
    try:
        server_conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            connect_timeout=5
        )
        cursor = server_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        logger.info(f"SUCCESS: Database '{DB_NAME}' created or already exists.")
        cursor.close()
        server_conn.close()
    except Exception as e:
        logger.warning(f"Could not connect to MySQL server without database ({e}). Will attempt direct connection to '{DB_NAME}'...")

    # 2. Connect to smart_village database
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connect_timeout=5
        )
        cur = conn.cursor(dictionary=True)

        logger.info(f"Creating required tables in database '{DB_NAME}'...")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                phone VARCHAR(15),
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                complaint_id VARCHAR(40) UNIQUE NOT NULL,
                user_id INT NOT NULL,
                category_id INT NOT NULL,
                description TEXT NOT NULL,
                location VARCHAR(255),
                photo VARCHAR(255),
                status ENUM('Submitted','Under Review','In Progress','Resolved','Closed') DEFAULT 'Submitted',
                assigned_to INT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                complaint_id INT NOT NULL,
                rating INT NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Indexes
        mysql_indexes = [
            ("idx_users_phone", "CREATE INDEX idx_users_phone ON users(phone)"),
            ("idx_complaints_user_id", "CREATE INDEX idx_complaints_user_id ON complaints(user_id)"),
            ("idx_complaints_category_id", "CREATE INDEX idx_complaints_category_id ON complaints(category_id)"),
            ("idx_complaints_status", "CREATE INDEX idx_complaints_status ON complaints(status)"),
            ("idx_complaints_created_at", "CREATE INDEX idx_complaints_created_at ON complaints(created_at)"),
            ("idx_feedback_complaint_id", "CREATE INDEX idx_feedback_complaint_id ON feedback(complaint_id)")
        ]
        for idx_name, idx_sql in mysql_indexes:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass

        # Populate categories
        categories = ['Water Problem', 'Road Issue', 'Street Light', 'Drainage Issue', 'Electricity', 'Garbage', 'Other']
        for cat in categories:
            try:
                cur.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", (cat,))
            except Exception:
                pass

        # Populate/Update Admin user with hashed password
        hashed_admin_pwd = generate_password_hash(ADMIN_PASSWORD)
        admin_emails = [ADMIN_EMAIL, "admin@smartvillage.com"]
        for a_email in admin_emails:
            cur.execute("SELECT id FROM admins WHERE email = %s", (a_email,))
            existing = cur.fetchone()
            if not existing:
                cur.execute(
                    "INSERT INTO admins (name, email, password) VALUES (%s, %s, %s)",
                    ('Village Admin', a_email, hashed_admin_pwd)
                )
                logger.info(f"SUCCESS: Created admin user '{a_email}' in local MySQL.")
            else:
                cur.execute(
                    "UPDATE admins SET password = %s WHERE email = %s",
                    (hashed_admin_pwd, a_email)
                )
                logger.info(f"SUCCESS: Updated password for admin user '{a_email}' in local MySQL.")

        conn.commit()
        cur.close()
        conn.close()
        logger.info("Local MySQL initialization completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize local MySQL database '{DB_NAME}': {e}")
        return False

if __name__ == "__main__":
    success = init_mysql()
    sys.exit(0 if success else 1)
