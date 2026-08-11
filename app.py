import os
from datetime import datetime
from functools import wraps

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "smart-village-development-key"
)

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Manish9934",
    "database": "smart_village"
}
def get_db():
    return mysql.connector.connect(**DB_CONFIG)

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

@app.route("/smartvillage")
def index():
    return render_template("index.html")

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
        except mysql.connector.IntegrityError:
            db.rollback()
            flash("Email already registered.", "danger")
        finally:
            cur.close()
            db.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

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
    return render_template("login.html")

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
    db = get_db()
    cur = db.cursor(dictionary=True)
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
            return redirect(url_for("submit_complaint"))

        filename = None
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG, PNG and WEBP files are allowed.", "danger")
                cur.close(); db.close()
                return redirect(url_for("submit_complaint"))
            safe_name = secure_filename(photo.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        complaint_id = "CID" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]

        cur2 = db.cursor()
        cur2.execute("""
            INSERT INTO complaints
            (complaint_id,user_id,category_id,description,location,photo)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (complaint_id, session["user_id"], category_id,
              description, location, filename))
        db.commit()
        cur2.close()
        cur.close()
        db.close()

        flash(f"Complaint submitted successfully. ID: {complaint_id}", "success")
        return redirect(url_for("dashboard"))

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

@app.route("/feedback/<int:complaint_db_id>", methods=["POST"])
@citizen_required
def feedback(complaint_db_id):
    rating = int(request.form["rating"])
    comment = request.form.get("comment", "").strip()

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("complaint_detail", complaint_db_id=complaint_db_id))

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM complaints WHERE id=%s AND user_id=%s",
                (complaint_db_id, session["user_id"]))
    if not cur.fetchone():
        cur.close(); db.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT id FROM feedback WHERE complaint_id=%s", (complaint_db_id,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE feedback SET rating=%s, comment=%s WHERE id=%s",
                    (rating, comment, existing[0]))
    else:
        cur.execute("INSERT INTO feedback (complaint_id,rating,comment) VALUES (%s,%s,%s)",
                    (complaint_db_id, rating, comment))
    db.commit()
    cur.close(); db.close()
    flash("Feedback saved.", "success")
    return redirect(url_for("complaint_detail", complaint_db_id=complaint_db_id))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

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
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) AS n FROM complaints")
    total = cur.fetchone()["n"]

    stats = {}
    for status in ["Submitted", "Under Review", "In Progress", "Resolved", "Closed"]:
        cur.execute("SELECT COUNT(*) AS n FROM complaints WHERE status=%s", (status,))
        stats[status] = cur.fetchone()["n"]

    cur.execute("""
        SELECT c.*, u.name AS user_name, cat.name AS category_name
        FROM complaints c
        JOIN users u ON c.user_id=u.id
        JOIN categories cat ON c.category_id=cat.id
        ORDER BY c.created_at DESC
    """)
    complaints = cur.fetchall()

    cur.close(); db.close()
    return render_template("admin_dashboard.html",
                           total=total, stats=stats, complaints=complaints)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
