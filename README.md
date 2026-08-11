# Smart Village Complaint Management System

## Technology
- Frontend: HTML, CSS, Bootstrap, JavaScript
- Backend: Python Flask
- Database: MySQL

## Setup in VS Code

1. Install Python and MySQL.
2. Create the database:
   - Open MySQL Workbench.
   - Run `database/smart_village.sql`.
3. Open `app.py`.
4. Change:
   `DB_CONFIG["password"] = "YOUR_MYSQL_PASSWORD"`
   to your MySQL root password.
5. Open terminal in this project folder:
   `python -m venv venv`
   `venv\Scripts\activate` (Windows)
6. Install packages:
   `pip install -r requirements.txt`
7. Run:
   `python app.py`
8. Open:
   `http://127.0.0.1:5000`

## Admin Demo Login
Email: admin@smartvillage.com
Password: admin123

## Citizen
First register from the Register page, then login and submit complaints.

## Main workflow
Citizen Registration -> Login -> Submit Complaint -> My Complaints -> Admin Review -> Status Update -> Citizen sees updated status -> Feedback after Resolved/Closed.

## Important
This is a college project/demo. Before real deployment, use environment variables for secrets, CSRF protection, stricter file validation, rate limiting, HTTPS and a proper admin password hash.
