import os
import sys
import sqlite3
import logging
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configure logging for DB transaction tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [SMART_VILLAGE_DB] %(message)s'
)
logger = logging.getLogger("SmartVillageDB")

# Helper for PyInstaller resource resolution
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# Load environment variables
env_file = get_resource_path(".env")
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    load_dotenv()

template_dir = get_resource_path("templates")
static_dir = get_resource_path("static")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "smart-village-secret-2026"
)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response



# Helper to obtain a writable application data directory (%LOCALAPPDATA%\SmartVillage)
def get_user_data_dir():
    try:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = os.path.expanduser("~")
        user_data_dir = os.path.join(local_app_data, "SmartVillage")
        os.makedirs(user_data_dir, exist_ok=True)
        return user_data_dir
    except Exception:
        fallback = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(fallback, exist_ok=True)
        return fallback

USER_DATA_DIR = get_user_data_dir()

# Upload folder - stored in %LOCALAPPDATA%\SmartVillage\uploads for Windows permission safety
UPLOAD_FOLDER = os.path.join(USER_DATA_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception:
    pass

# Central Database Configuration Helper
def parse_db_url(url):
    parsed = urlparse(url)
    user = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    dbname = parsed.path.lstrip("/") if parsed.path else "smart_village"
    return host, user, password, dbname, port

# Database Setup & Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "smart_village")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
PREFER_MYSQL = os.environ.get("DB_TYPE", "mysql").lower() != "sqlite"

DB_TYPE = "sqlite"

# SQLite Adapters for unified dictionary cursor & %s parameter handling
class SQLiteCursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        sqlite_query = query.replace("%s", "?")
        if params is not None:
            return self.cursor.execute(sqlite_query, params)
        return self.cursor.execute(sqlite_query)

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self.cursor.close()

class SQLiteConnectionAdapter:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self, dictionary=True):
        return SQLiteCursorAdapter(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

# Test MySQL Availability & Connection Pool Setup
mysql_module = None
mysql_pool = None

if PREFER_MYSQL:
    try:
        import mysql.connector
        from mysql.connector.pooling import MySQLConnectionPool
        mysql_module = mysql.connector
    except ImportError:
        mysql_module = None

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB upload limit

import time
_categories_cache = None
_categories_cache_time = 0
CACHE_TTL_SECONDS = 300

def get_categories_cached():
    global _categories_cache, _categories_cache_time
    now = time.time()
    if _categories_cache is not None and (now - _categories_cache_time) < CACHE_TTL_SECONDS:
        return _categories_cache
    
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM categories ORDER BY name ASC")
        categories = cur.fetchall()
        cur.close(); db.close()
        _categories_cache = categories
        _categories_cache_time = now
        return categories
    except Exception as e:
        logger.error(f"[CATEGORY CACHE ERROR] {e}")
        return _categories_cache or []

def save_optimized_photo(photo_file):
    if not photo_file or not photo_file.filename or not allowed_file(photo_file.filename):
        return None
    safe_name = secure_filename(photo_file.filename)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    
    if HAS_PIL:
        try:
            photo_file.stream.seek(0)
            img = Image.open(photo_file.stream)
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            img.save(filepath, "JPEG", optimize=True, quality=85)
            return filename
        except Exception as e:
            logger.warning(f"[PHOTO PROCESS NOTICE] PIL optimization failed ({e}), falling back to direct save.")
            photo_file.stream.seek(0)
    
    photo_file.save(filepath)
    return filename

def get_mysql_pool(connect_kwargs):
    global mysql_pool
    if mysql_pool is None and mysql_module is not None:
        try:
            from mysql.connector.pooling import MySQLConnectionPool
            pool_kwargs = dict(connect_kwargs)
            pool_kwargs["pool_name"] = "smart_village_pool"
            pool_kwargs["pool_size"] = 5
            mysql_pool = MySQLConnectionPool(**pool_kwargs)
            logger.info("[DB POOL SUCCESS] Initialized MySQL Connection Pool (size=5)")
        except Exception as e:
            logger.warning(f"[DB POOL NOTICE] Could not initialize pool ({e}), using direct connections")
            mysql_pool = None
    return mysql_pool

def get_db():
    global DB_TYPE
    db_url = os.environ.get("MYSQL_URL") or os.environ.get("DATABASE_URL")
    if db_url and (db_url.startswith("mysql://") or db_url.startswith("mysql+pymysql://")):
        host, user, password, dbname, port = parse_db_url(db_url)
    else:
        host = os.environ.get("DB_HOST", "")
        user = os.environ.get("DB_USER", "")
        password = os.environ.get("DB_PASSWORD", "")
        dbname = os.environ.get("DB_NAME", "defaultdb")
        port = int(os.environ.get("DB_PORT", 28711))

    # Detect if running in production on Render (or if explicit REQUIRE_CENTRAL_DB / RENDER environment variable is set)
    is_render = (
        os.environ.get("RENDER") is not None
        or os.environ.get("RENDER_SERVICE_ID") is not None
        or os.environ.get("FLASK_ENV") == "production"
        or os.environ.get("ENV") == "production"
        or os.environ.get("REQUIRE_CENTRAL_DB", "false").lower() in ("true", "1")
    )

    if is_render:
        logger.info(f"[PRODUCTION DB CONNECT] Render production environment detected. Connecting to Central Online MySQL Database -> Host: '{host}', Port: {port}, Database Name: '{dbname}', User: '{user}'")

        if not host or host in ("localhost", "127.0.0.1"):
            err_msg = (
                "[DB CONFIG ERROR] Production Render environment detected, but DB_HOST is missing or set to localhost/127.0.0.1. "
                "Render cannot connect to local MySQL. Please configure DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, and DB_PORT "
                "in your Render Dashboard Environment Variables to point to your Central Online MySQL Database. "
                "Fallback to SQLite is strictly DISABLED in production."
            )
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        if not mysql_module:
            err_msg = "[DB DRIVER ERROR] mysql.connector module is missing in production environment."
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        connect_kwargs = {
            "host": host,
            "user": user,
            "password": password,
            "database": dbname,
            "port": port,
            "connect_timeout": 10
        }
        if os.environ.get("DB_SSL_DISABLED", "").lower() in ("true", "1"):
            connect_kwargs["ssl_disabled"] = True
        else:
            db_ssl_ca = os.environ.get("DB_SSL_CA", "")
            if db_ssl_ca:
                if os.path.exists(db_ssl_ca):
                    connect_kwargs["ssl_ca"] = db_ssl_ca
                elif "-----BEGIN CERTIFICATE-----" in db_ssl_ca:
                    ca_path = os.path.join(USER_DATA_DIR, "aiven_ca.pem")
                    try:
                        with open(ca_path, "w", encoding="utf-8") as f:
                            f.write(db_ssl_ca)
                        connect_kwargs["ssl_ca"] = ca_path
                    except Exception as ca_err:
                        logger.warning(f"[SSL CA NOTICE] Could not write CA PEM: {ca_err}")
                        connect_kwargs["ssl_verify_identity"] = False
            else:
                # Aiven MySQL requires SSL; verify_identity=False ensures compatibility with Aiven cloud SSL
                connect_kwargs["ssl_verify_identity"] = False

        try:
            pool = get_mysql_pool(connect_kwargs)
            if pool:
                conn = pool.get_connection()
            else:
                conn = mysql_module.connect(**connect_kwargs)

            DB_TYPE = "mysql"
            logger.info(f"[DB CONNECT SUCCESS] Connected to Central Online MySQL Database -> Host: '{host}', Database Name: '{dbname}'")
            return conn
        except Exception as e:
            err_str = str(e)
            # Automatic fallback retry with 'defaultdb' if user avnadmin does not have access to 'smart_village'
            if ("1045" in err_str or "1049" in err_str or "Access denied" in err_str or "Unknown database" in err_str) and dbname != "defaultdb":
                logger.warning(f"[DB CONNECT FALLBACK] Could not connect to database '{dbname}' ({err_str}). Retrying connection with 'defaultdb'...")
                connect_kwargs["database"] = "defaultdb"
                try:
                    conn = mysql_module.connect(**connect_kwargs)
                    DB_TYPE = "mysql"
                    logger.info(f"[DB CONNECT SUCCESS] Connected to Central Online MySQL Database -> Host: '{host}', Database Name: 'defaultdb'")
                    return conn
                except Exception as ex:
                    logger.error(f"[DB CONNECT FAILURE] Fallback retry to 'defaultdb' failed: {ex}")

            err_msg = f"[DB CONNECT FAILURE] Failed to connect to Central Online MySQL Database (Host: '{host}', Port: {port}, DB: '{dbname}'): {e}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    # Local Development Handling
    if not host:
        host = "localhost"
    if not user:
        user = "root"

    logger.info(f"[LOCAL DB CONNECT] Local development mode -> Host: '{host}', Port: {port}, Database: '{dbname}'")

    if PREFER_MYSQL and mysql_module:
        try:
            connect_kwargs = {
                "host": host,
                "user": user,
                "password": password,
                "database": dbname,
                "port": port,
                "connect_timeout": 5
            }
            pool = get_mysql_pool(connect_kwargs)
            if pool:
                conn = pool.get_connection()
            else:
                conn = mysql_module.connect(**connect_kwargs)

            DB_TYPE = "mysql"
            logger.info(f"[LOCAL DB CONNECT SUCCESS] Connected to local MySQL Database -> Host: '{host}', DB: '{dbname}'")
            return conn
        except Exception as e:
            logger.warning(f"[LOCAL DB CONNECT NOTICE] Local MySQL unavailable ({e}). Falling back to local SQLite for local development.")

    shared_sqlite_path = os.environ.get("SQLITE_DB_PATH", os.path.join(USER_DATA_DIR, "smart_village.db"))
    logger.info(f"[LOCAL DB FALLBACK] Using local SQLite database: '{shared_sqlite_path}'")
    conn = sqlite3.connect(shared_sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    DB_TYPE = "sqlite"
    return SQLiteConnectionAdapter(conn)


def init_db():
    try:
        db = get_db()
        if DB_TYPE == "sqlite":
            conn = db.conn
            cur = conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    password TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );

                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    location TEXT,
                    photo TEXT,
                    status TEXT DEFAULT 'Submitted',
                    assigned_to INTEGER NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
                );

                INSERT OR IGNORE INTO categories (name) VALUES
                ('Water Problem'), ('Road Issue'), ('Street Light'),
                ('Drainage Issue'), ('Electricity'), ('Garbage'), ('Other');
            """)
            sqlite_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_user_id ON complaints(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_category_id ON complaints(category_id)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status)",
                "CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON complaints(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_complaint_id ON feedback(complaint_id)"
            ]
            for idx_sql in sqlite_indexes:
                try:
                    cur.execute(idx_sql)
                except Exception:
                    pass

            admin_plain_pwd = os.environ.get("ADMIN_PASSWORD", "Manish@9934")
            hashed_admin_pwd = generate_password_hash(admin_plain_pwd)
            admin_emails = ["manishmaurya9934@gmail.com", "admin-manish@smartvillage.com"]
            for a_email in admin_emails:
                cur.execute("SELECT id FROM admins WHERE email = ?", (a_email,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO admins (name, email, password) VALUES (?, ?, ?)",
                        ('Village Admin', a_email, hashed_admin_pwd)
                    )
                else:
                    cur.execute(
                        "UPDATE admins SET password = ? WHERE email = ?",
                        (hashed_admin_pwd, a_email)
                    )
            conn.commit()
            cur.close()
            db.close()
        else:
            cur = db.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    phone VARCHAR(15),
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    complaint_id INT NOT NULL,
                    rating INT NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
                )
            """)
            mysql_indexes = [
                "CREATE INDEX idx_users_phone ON users(phone)",
                "CREATE INDEX idx_complaints_user_id ON complaints(user_id)",
                "CREATE INDEX idx_complaints_category_id ON complaints(category_id)",
                "CREATE INDEX idx_complaints_status ON complaints(status)",
                "CREATE INDEX idx_complaints_created_at ON complaints(created_at)",
                "CREATE INDEX idx_feedback_complaint_id ON feedback(complaint_id)"
            ]
            for idx_sql in mysql_indexes:
                try:
                    cur.execute(idx_sql)
                except Exception:
                    pass

            for cat in ['Water Problem', 'Road Issue', 'Street Light', 'Drainage Issue', 'Electricity', 'Garbage', 'Other']:
                try:
                    cur.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", (cat,))
                except Exception:
                    pass
            try:
                admin_plain_pwd = os.environ.get("ADMIN_PASSWORD", "Manish@9934")
                hashed_admin_pwd = generate_password_hash(admin_plain_pwd)
                admin_emails = ["manishmaurya9934@gmail.com", "admin-manish@smartvillage.com"]
                for a_email in admin_emails:
                    cur.execute("SELECT id FROM admins WHERE email = %s", (a_email,))
                    existing_admin = cur.fetchone()
                    if not existing_admin:
                        cur.execute(
                            "INSERT INTO admins (name, email, password) VALUES (%s, %s, %s)",
                            ('Village Admin', a_email, hashed_admin_pwd)
                        )
                    else:
                        cur.execute(
                            "UPDATE admins SET password = %s WHERE email = %s",
                            (hashed_admin_pwd, a_email)
                        )
            except Exception as e:
                logger.error(f"[INIT DB ADMIN ERROR] Failed to setup admin account: {e}")
            db.commit()
            cur.close()
            db.close()
    except Exception as e:
        print(f"Database Initialization Notice: {e}")

# Initialize DB tables on startup
init_db()

@app.route('/uploads/<path:filename>', endpoint='uploaded_file')
@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def citizen_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
@app.route("/smartvillage")
def index():
    stats = {
        "total_citizens": 0,
        "total_complaints": 0,
        "under_process": 0,
        "resolved": 0
    }
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT COUNT(*) AS n FROM users")
        row = cur.fetchone()
        if row:
            stats["total_citizens"] = row["n"]

        cur.execute("""
            SELECT 
                COUNT(*) AS total_complaints,
                SUM(CASE WHEN status IN ('Submitted', 'Under Review', 'In Progress') THEN 1 ELSE 0 END) AS under_process,
                SUM(CASE WHEN status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved
            FROM complaints
        """)
        c_row = cur.fetchone()
        if c_row:
            stats["total_complaints"] = c_row["total_complaints"] or 0
            stats["under_process"] = c_row["under_process"] or 0
            stats["resolved"] = c_row["resolved"] or 0

        cur.close()
        db.close()
    except Exception as e:
        logger.error(f"Stats calculation notice: {e}")

    return render_template("index.html", stats=stats)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form["password"]

        if not name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
                (name, email, phone, generate_password_hash(password))
            )
            db.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.rollback()
            flash("Email already registered or registration error.", "danger")
        finally:
            cur.close()
            db.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
@app.route("/citizen-login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html")

        try:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            cur.close()
            db.close()

            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")
        except Exception as e:
            logger.error(f"[CITIZEN LOGIN FAILURE] Database exception during citizen login: {e}")
            flash("Server is temporarily unavailable. Please try again.", "danger")
    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if not email or not new_password or not confirm_password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("forgot_password"))

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("forgot_password"))

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if not user:
            cur.close()
            db.close()
            flash("No citizen account found with this email address.", "danger")
            return redirect(url_for("forgot_password"))

        hashed = generate_password_hash(new_password)
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))
        db.commit()
        cur.close()
        db.close()

        flash("Password reset successfully! Please login with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@citizen_required
def dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, cat.name AS category_name
        FROM complaints c
        JOIN categories cat ON c.category_id = cat.id
        WHERE c.user_id=%s
        ORDER BY c.created_at DESC
    """, (session["user_id"],))
    complaints = cur.fetchall()
    cur.close()
    db.close()
    return render_template("dashboard.html", complaints=complaints)

@app.route("/submit-complaint", methods=["GET", "POST"])
@citizen_required
def submit_complaint():
    categories = get_categories_cached()

    if request.method == "POST":
        category_id = request.form["category_id"]
        description = request.form["description"].strip()
        location = request.form.get("location", "").strip()
        photo = request.files.get("photo")

        if not description:
            flash("Complaint description is required.", "danger")
            return redirect(url_for("submit_complaint"))

        filename = None
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG, PNG and WEBP files are allowed.", "danger")
                return redirect(url_for("submit_complaint"))
            filename = save_optimized_photo(photo)

        complaint_id = "CID" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]

        db = get_db()
        cur = db.cursor()
        try:
            logger.info(f"[COMPLAINT INSERT] Inserting complaint '{complaint_id}' for user_id '{session['user_id']}' into database...")
            cur.execute("""
                INSERT INTO complaints
                (complaint_id,user_id,category_id,description,location,photo)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (complaint_id, session["user_id"], category_id,
                  description, location, filename))
            db.commit()
            logger.info(f"[COMPLAINT INSERT SUCCESS] Complaint '{complaint_id}' successfully COMMITTED to central database.")
            flash(f"Complaint submitted successfully. ID: {complaint_id}", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            db.rollback()
            logger.error(f"[COMPLAINT INSERT FAILURE] Failed to insert complaint '{complaint_id}': {e}")
            flash("Database transaction error while submitting complaint.", "danger")
            return redirect(url_for("submit_complaint"))
        finally:
            cur.close()
            db.close()

    return render_template("submit_complaint.html", categories=categories)

@app.route("/complaint/<int:complaint_db_id>")
@citizen_required
def complaint_detail(complaint_db_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, cat.name AS category_name, u.name AS user_name
        FROM complaints c
        JOIN categories cat ON c.category_id=cat.id
        JOIN users u ON c.user_id=u.id
        WHERE c.id=%s AND c.user_id=%s
    """, (complaint_db_id, session["user_id"]))
    complaint = cur.fetchone()
    cur.close(); db.close()
    if not complaint:
        flash("Complaint not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("complaint_detail.html", complaint=complaint)

@app.route("/edit-complaint/<int:complaint_db_id>", methods=["GET", "POST"])
@citizen_required
def edit_complaint(complaint_db_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM complaints WHERE id=%s AND user_id=%s
    """, (complaint_db_id, session["user_id"]))
    complaint = cur.fetchone()

    if not complaint:
        cur.close(); db.close()
        flash("Complaint not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT * FROM categories ORDER BY name")
    categories = cur.fetchall()

    if request.method == "POST":
        category_id = request.form["category_id"]
        description = request.form["description"].strip()
        location = request.form.get("location", "").strip()
        photo = request.files.get("photo")

        if not description:
            flash("Complaint description is required.", "danger")
            cur.close(); db.close()
            return redirect(url_for("edit_complaint", complaint_db_id=complaint_db_id))

        filename = complaint["photo"]
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG, PNG and WEBP files are allowed.", "danger")
                cur.close(); db.close()
                return redirect(url_for("edit_complaint", complaint_db_id=complaint_db_id))

            if complaint["photo"]:
                old_photo_path = os.path.join(app.config["UPLOAD_FOLDER"], complaint["photo"])
                if os.path.exists(old_photo_path):
                    try:
                        os.remove(old_photo_path)
                    except OSError:
                        pass

            safe_name = secure_filename(photo.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cur2 = db.cursor()
        cur2.execute("""
            UPDATE complaints
            SET category_id=%s, description=%s, location=%s, photo=%s
            WHERE id=%s AND user_id=%s
        """, (category_id, description, location, filename, complaint_db_id, session["user_id"]))
        db.commit()
        cur2.close()
        cur.close(); db.close()

        flash("Complaint updated successfully.", "success")
        return redirect(url_for("complaint_detail", complaint_db_id=complaint_db_id))

    cur.close(); db.close()
    return render_template("edit_complaint.html", complaint=complaint, categories=categories)

@app.route("/delete-complaint/<int:complaint_db_id>", methods=["POST"])
@citizen_required
def delete_complaint(complaint_db_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT photo FROM complaints WHERE id=%s AND user_id=%s",
                (complaint_db_id, session["user_id"]))
    complaint = cur.fetchone()

    if not complaint:
        cur.close(); db.close()
        flash("Complaint not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))

    if complaint["photo"]:
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], complaint["photo"])
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                pass

    cur2 = db.cursor()
    cur2.execute("DELETE FROM complaints WHERE id=%s AND user_id=%s",
                (complaint_db_id, session["user_id"]))
    db.commit()
    cur2.close()
    cur.close(); db.close()

    flash("Complaint deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/feedback/<int:complaint_db_id>", methods=["POST"])
@citizen_required
def feedback(complaint_db_id):
    rating = int(request.form["rating"])
    comment = request.form.get("comment", "").strip()

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("complaint_detail", complaint_db_id=complaint_db_id))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id FROM complaints WHERE id=%s AND user_id=%s",
                (complaint_db_id, session["user_id"]))
    if not cur.fetchone():
        cur.close(); db.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT id FROM feedback WHERE complaint_id=%s", (complaint_db_id,))
    existing = cur.fetchone()
    cur2 = db.cursor()
    if existing:
        cur2.execute("UPDATE feedback SET rating=%s, comment=%s WHERE id=%s",
                    (rating, comment, existing["id"]))
    else:
        cur2.execute("INSERT INTO feedback (complaint_id,rating,comment) VALUES (%s,%s,%s)",
                    (complaint_db_id, rating, comment))
    db.commit()
    cur2.close()
    cur.close(); db.close()
    flash("Feedback saved.", "success")
    return redirect(url_for("complaint_detail", complaint_db_id=complaint_db_id))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
            admin = cur.fetchone()
            cur.close(); db.close()

            if admin and (password == admin["password"] or check_password_hash(admin["password"], password)):
                session.clear()
                session["admin_id"] = admin["id"]
                session["admin_name"] = admin["name"]
                return redirect(url_for("admin_dashboard"))

            flash("Invalid admin credentials.", "danger")
        except Exception as e:
            logger.error(f"[ADMIN LOGIN ERROR] Database error during admin login: {e}")
            flash(f"Database Error: {e}", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) AS st_submitted,
                SUM(CASE WHEN status = 'Under Review' THEN 1 ELSE 0 END) AS st_review,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS st_progress,
                SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS st_resolved,
                SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) AS st_closed
            FROM complaints
        """)
        agg_row = cur.fetchone() or {}
        total = agg_row.get("total") or 0
        stats = {
            "Submitted": agg_row.get("st_submitted") or 0,
            "Under Review": agg_row.get("st_review") or 0,
            "In Progress": agg_row.get("st_progress") or 0,
            "Resolved": agg_row.get("st_resolved") or 0,
            "Closed": agg_row.get("st_closed") or 0
        }

        cur.execute("""
            SELECT c.id, c.complaint_id, c.description, c.location, c.photo, c.status, c.created_at,
                   u.name AS user_name, cat.name AS category_name
            FROM complaints c
            JOIN users u ON c.user_id=u.id
            JOIN categories cat ON c.category_id=cat.id
            ORDER BY c.created_at DESC
        """)
        complaints = cur.fetchall()

        logger.info(f"[ADMIN QUERY RESULT] Admin Dashboard fetched complaints from central database. Total record count: {len(complaints)}")

        cur.close(); db.close()
        return render_template("admin_dashboard.html",
                               total=total, stats=stats, complaints=complaints)
    except Exception as e:
        logger.error(f"[ADMIN DASHBOARD ERROR] Database error loading dashboard: {e}")
        flash(f"Database Error: {e}", "danger")
        return render_template("admin_dashboard.html", total=0, stats={}, complaints=[])

@app.route("/admin/update-status/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):
    status = request.form["status"]
    allowed = {"Submitted", "Under Review", "In Progress", "Resolved", "Closed"}
    if status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE complaints SET status=%s WHERE id=%s",
                (status, complaint_id))
    db.commit()
    cur.close(); db.close()
    flash("Complaint status updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete-complaint/<int:complaint_id>", methods=["POST"])
@admin_required
def admin_delete_complaint(complaint_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT photo FROM complaints WHERE id=%s", (complaint_id,))
        complaint = cur.fetchone()

        if not complaint:
            flash("Complaint not found.", "danger")
            return redirect(url_for("admin_dashboard"))

        if complaint.get("photo"):
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], complaint["photo"])
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass

        cur.execute("DELETE FROM feedback WHERE complaint_id=%s", (complaint_id,))
        cur.execute("DELETE FROM complaints WHERE id=%s", (complaint_id,))
        db.commit()
        flash("Complaint deleted successfully.", "success")
    except Exception as e:
        db.rollback()
        flash("Failed to delete complaint.", "danger")
    finally:
        cur.close()
        db.close()

    return redirect(url_for("admin_dashboard"))


# ==========================================
# REST API ENDPOINTS FOR ANDROID MOBILE APP
# ==========================================

from flask import jsonify

@app.route("/__smartvillage_debug_2026")
def smartvillage_debug():
    return {
        "application": "Smart Village Complaint Management System",
        "deployment": "production",
        "status": "correct_flask_app"
    }

@app.route("/api/health", methods=["GET"])
def api_health():
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        db.close()
        return jsonify({
            "status": "ok",
            "database": "connected"
        }), 200
    except Exception as e:
        logger.error(f"[HEALTH CHECK DB ERROR] Health check database ping failed: {e}")
        return jsonify({
            "status": "error",
            "database": "disconnected"
        }), 503

@app.route("/api/debug/routes", methods=["GET"])
def debug_routes():
    return jsonify({
        "routes": sorted([
            str(rule)
            for rule in app.url_map.iter_rules()
        ])
    }), 200




@app.route("/api/stats", methods=["GET"])
def api_stats():
    stats = {
        "citizens": 0,
        "complaints": 0,
        "in_progress": 0,
        "resolved": 0,
        "total_citizens": 0,
        "total_complaints": 0,
        "under_process": 0
    }
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS n FROM users")
        r = cur.fetchone()
        stats["citizens"] = stats["total_citizens"] = r["n"] if r else 0

        cur.execute("""
            SELECT 
                COUNT(*) AS total_complaints,
                SUM(CASE WHEN status IN ('Submitted', 'Under Review', 'In Progress') THEN 1 ELSE 0 END) AS under_process,
                SUM(CASE WHEN status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved
            FROM complaints
        """)
        c_row = cur.fetchone()
        if c_row:
            stats["complaints"] = stats["total_complaints"] = c_row["total_complaints"] or 0
            stats["in_progress"] = stats["under_process"] = c_row["under_process"] or 0
            stats["resolved"] = c_row["resolved"] or 0

        cur.close(); db.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({
        "status": "success",
        "success": True,
        "stats": stats,
        "citizens": stats["citizens"],
        "complaints": stats["complaints"],
        "in_progress": stats["in_progress"],
        "resolved": stats["resolved"]
    })

@app.route("/api/categories", methods=["GET"])
def api_categories():
    try:
        cats = get_categories_cached()
        return jsonify({"success": True, "categories": cats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Name, email and password are required."}), 400

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
            (name, email, phone, generate_password_hash(password))
        )
        db.commit()
        return jsonify({"success": True, "message": "Registration successful. Please login."})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": "Email already registered or database error."}), 400
    finally:
        cur.close(); db.close()

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required."}), 400

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close(); db.close()

    if user and check_password_hash(user["password"], password):
        return jsonify({
            "success": True,
            "message": "Login successful.",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "phone": user.get("phone", "")
            }
        })
    return jsonify({"success": False, "message": "Invalid email or password."}), 401

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
    admin = cur.fetchone()
    cur.close(); db.close()

    if admin and (password == admin["password"] or check_password_hash(admin["password"], password)):
        return jsonify({
            "success": True,
            "message": "Admin login successful.",
            "admin": {
                "id": admin["id"],
                "name": admin["name"],
                "email": admin["email"]
            }
        })
    return jsonify({"success": False, "message": "Invalid admin credentials."}), 401

@app.route("/api/dashboard/<int:user_id>", methods=["GET"])
def api_dashboard(user_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, cat.name AS category_name
        FROM complaints c
        JOIN categories cat ON c.category_id = cat.id
        WHERE c.user_id=%s
        ORDER BY c.created_at DESC
    """, (user_id,))
    complaints = cur.fetchall()
    cur.close(); db.close()
    return jsonify({"success": True, "complaints": complaints})

@app.route("/api/submit-complaint", methods=["POST"])
def api_submit_complaint():
    json_data = request.get_json(silent=True) or {}
    user_id = request.form.get("user_id") or json_data.get("user_id")
    category_id = request.form.get("category_id") or json_data.get("category_id")
    description = (request.form.get("description") or json_data.get("description", "")).strip()
    location = (request.form.get("location") or json_data.get("location", "")).strip()
    photo = request.files.get("photo")

    if not user_id or not category_id or not description:
        return jsonify({"success": False, "message": "User ID, Category and Description are required."}), 400

    filename = None
    if photo and photo.filename:
        if not allowed_file(photo.filename):
            return jsonify({"success": False, "message": "Invalid file type. Allowed: JPG, PNG, WEBP."}), 400
        filename = save_optimized_photo(photo)

    complaint_id = "CID" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]

    db = get_db()
    cur = db.cursor()
    try:
        logger.info(f"[API COMPLAINT INSERT] Inserting complaint '{complaint_id}' for user_id '{user_id}' into central database...")
        cur.execute("""
            INSERT INTO complaints
            (complaint_id,user_id,category_id,description,location,photo)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (complaint_id, user_id, category_id, description, location, filename))
        db.commit()
        logger.info(f"[API COMPLAINT INSERT SUCCESS] Complaint '{complaint_id}' successfully COMMITTED to central database.")
        return jsonify({"success": True, "message": "Complaint submitted successfully.", "complaint_id": complaint_id})
    except Exception as e:
        db.rollback()
        logger.error(f"[API COMPLAINT INSERT FAILURE] Failed to insert complaint '{complaint_id}': {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close(); db.close()

@app.route("/api/admin/complaints", methods=["GET"])
def api_admin_complaints():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT c.*, u.name AS citizen_name, u.email AS citizen_email, u.phone AS citizen_phone, cat.name AS category_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        JOIN categories cat ON c.category_id = cat.id
        ORDER BY c.created_at DESC
    """)
    complaints = cur.fetchall()
    cur.close(); db.close()

    logger.info(f"[API ADMIN QUERY RESULT] Admin API queried central database. Total complaints returned: {len(complaints)}")
    return jsonify({"success": True, "complaints": complaints})

@app.route("/api/admin/update-status/<int:complaint_id>", methods=["POST"])
def api_admin_update_status(complaint_id):
    data = request.get_json(silent=True) or request.form
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "message": "Status is required."}), 400

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("UPDATE complaints SET status=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (new_status, complaint_id))
        db.commit()
        return jsonify({"success": True, "message": "Status updated successfully."})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close(); db.close()

@app.route("/api/admin/delete-complaint/<int:complaint_id>", methods=["POST", "DELETE"])
def api_admin_delete_complaint(complaint_id):
    db = get_db()
    cur = db.cursor()
    try:
        logger.info(f"[ADMIN DELETE] Admin requesting deletion of complaint ID: {complaint_id}")
        cur.execute("DELETE FROM feedback WHERE complaint_id=%s", (complaint_id,))
        cur.execute("DELETE FROM complaints WHERE id=%s", (complaint_id,))
        db.commit()
        logger.info(f"[ADMIN DELETE SUCCESS] Complaint ID {complaint_id} and associated feedback deleted.")
        return jsonify({"success": True, "message": "Complaint deleted successfully."})
    except Exception as e:
        db.rollback()
        logger.error(f"[ADMIN DELETE FAILURE] Failed to delete complaint ID {complaint_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close(); db.close()

@app.route("/api/delete-complaint/<int:complaint_id>", methods=["POST", "DELETE"])
def api_delete_complaint(complaint_id):
    data = request.get_json(silent=True) or request.form
    user_id = data.get("user_id")

    db = get_db()
    cur = db.cursor()
    try:
        if user_id:
            cur.execute("DELETE FROM complaints WHERE id=%s AND user_id=%s", (complaint_id, user_id))
        else:
            cur.execute("DELETE FROM complaints WHERE id=%s", (complaint_id,))
        db.commit()
        return jsonify({"success": True, "message": "Complaint deleted successfully."})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close(); db.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



