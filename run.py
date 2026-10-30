import time
import secrets
import re
import csv
import io
import json
from werkzeug.utils import secure_filename
from config import Config
from openrouter_service import evaluate_internship_video_with_ai, evaluate_quiz_with_ai
"""
run.py – Flask backend for AI-Powered Internship Monitoring System
Run:  python run.py
      (Make sure to run  python init_db.py  first)
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps

import mimetypes
from flask import (
    Flask, request, session, jsonify,
    send_from_directory, Response, redirect, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "internship.db")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.secret_key = Config.SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = Config.PERMANENT_SESSION_LIFETIME
app.config["SESSION_COOKIE_HTTPONLY"] = Config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = Config.SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = Config.SESSION_COOKIE_SECURE


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def query_db(sql, args=(), one=False):
    conn = get_db()
    cur  = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def execute_db(sql, args=()):
    conn = get_db()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        last_id = cur.lastrowid
        conn.close()
        return last_id
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN ID GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_login_id(role, year=None):
    """
    Format Rule:
    Admin:   ADM + YY + A + unique numeric suffix (e.g. ADM26A1042)
    Staff:   STF + YY + T + unique numeric suffix (e.g. STF26T1001)
    Student: STU + YY + S + unique numeric suffix (e.g. STU26S2045)
    Supports configurable registration year (e.g. '26' for 2026, '27' for 2027).
    """
    y = str(year or Config.REGISTRATION_YEAR).strip()
    if len(y) == 4:
        y = y[-2:]

    r = role.lower()
    if r in ["admin", "administrator"]:
        prefix = f"ADM{y}A"
        base_start = 1000
    elif r in ["staff", "faculty", "guide"]:
        prefix = f"STF{y}T"
        base_start = 1000
    elif r in ["student"]:
        prefix = f"STU{y}S"
        base_start = 2000
    else:
        prefix = f"USR{y}U"
        base_start = 1000

    # Query all user tables to guarantee global uniqueness
    existing_ids = set()
    for t in ["admin", "faculty", "students"]:
        try:
            for row in query_db(f"SELECT login_id FROM {t} WHERE login_id LIKE ?", (f"{prefix}%",)):
                if row.get("login_id"):
                    existing_ids.add(row["login_id"])
        except Exception:
            pass

    highest = base_start
    for lid in existing_ids:
        num_part = lid[len(prefix):]
        if num_part.isdigit():
            highest = max(highest, int(num_part))

    candidate = highest + 1
    new_id = f"{prefix}{candidate}"
    while new_id in existing_ids:
        candidate += 1
        new_id = f"{prefix}{candidate}"
    return new_id


# ─────────────────────────────────────────────────────────────────────────────
# AUTH DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Unauthorized"}), 401
            if session.get("user_role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# SERVE HTML FILES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "login.html")


def safe_send_file(filename):
    target = os.path.join(BASE_DIR, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return send_from_directory(BASE_DIR, filename)
    if not filename.endswith(".html"):
        html_target = os.path.join(BASE_DIR, f"{filename}.html")
        if os.path.exists(html_target) and os.path.isfile(html_target):
            return send_from_directory(BASE_DIR, f"{filename}.html")
    return send_from_directory(BASE_DIR, filename)


@app.route("/<path:filename>")
def static_files(filename):
    return safe_send_file(filename)


@app.route("/student/<path:filename>")
def student_subpath_files(filename):
    mapping = {
        "attendance": "student-attendance.html",
        "evaluations": "student-evaluations.html",
        "internship": "student-internship.html",
        "tasks": "student-tasks.html",
        "updates": "student-updates.html",
        "reports": "student-reports.html",
        "marks": "student-marks.html",
        "dashboard": "student-dashboard.html",
    }
    cleaned = filename.lower().replace(".html", "")
    if cleaned in mapping:
        return send_from_directory(BASE_DIR, mapping[cleaned])
    return safe_send_file(filename)


@app.route("/staff/<path:filename>")
@app.route("/faculty/<path:filename>")
def faculty_subpath_files(filename):
    mapping = {
        "attendance": "faculty-attendance.html",
        "evaluations": "faculty-evaluations.html",
        "students": "faculty-students.html",
        "updates": "faculty-updates.html",
        "marks": "manage-marks.html",
        "dashboard": "faculty-dashboard.html",
        "internships": "manage-internships.html",
    }
    cleaned = filename.lower().replace(".html", "")
    if cleaned in mapping:
        return send_from_directory(BASE_DIR, mapping[cleaned])
    return safe_send_file(filename)


@app.route("/admin/<path:filename>")
def admin_subpath_files(filename):
    mapping = {
        "students": "manage-students.html",
        "faculty": "manage-faculty.html",
        "internships": "manage-internships.html",
        "marks": "manage-marks.html",
        "dashboard": "admin-dashboard.html",
    }
    cleaned = filename.lower().replace(".html", "")
    if cleaned in mapping:
        return send_from_directory(BASE_DIR, mapping[cleaned])
    return safe_send_file(filename)


# ─────────────────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD VERIFICATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

def verify_password(stored, provided, extra_fallbacks=None):
    """
    Robust password verification supporting:
    - Direct match (if plain text was stored or seeded)
    - Werkzeug hashed passwords (scrypt, pbkdf2, etc.)
    - Case-insensitive hash checks (e.g., USN typed in lowercase)
    - Configured default fallback passwords (e.g., USN, Faculty ID, Guide@123, Student@123, 1234)
    """
    if not stored or not provided:
        return False

    stored_str   = str(stored).strip()
    provided_str = str(provided).strip()

    # 1. Direct equality check (handles plain text passwords)
    if stored_str == provided_str:
        return True
    if stored_str.lower() == provided_str.lower():
        return True

    # 2. Werkzeug hash check with exact input
    try:
        if check_password_hash(stored_str, provided_str):
            return True
    except Exception:
        pass

    # 3. Case-insensitive hash check (e.g. USN or Faculty ID was saved uppercase)
    try:
        if check_password_hash(stored_str, provided_str.upper()):
            return True
        if check_password_hash(stored_str, provided_str.lower()):
            return True
    except Exception:
        pass

    # 4. Fallback default candidates check
    if extra_fallbacks:
        p_clean = provided_str.lower()
        for cand in extra_fallbacks:
            if not cand:
                continue
            cand_clean = str(cand).strip().lower()
            if p_clean == cand_clean:
                return True
            try:
                if check_password_hash(stored_str, str(cand).strip()):
                    return True
            except Exception:
                pass

    return False



# ─────────────────────────────────────────────────────────────────────────────
# SECURITY HELPERS: RATE LIMITING, AUDIT LOGGING & CSRF
# ─────────────────────────────────────────────────────────────────────────────

LOGIN_ATTEMPTS = {}  # {ip_or_user: [timestamps]}

def check_login_rate_limit(key):
    now = time.time()
    cutoff = now - Config.LOGIN_LOCKOUT_SECONDS
    # Clean old attempts
    attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if t > cutoff]
    LOGIN_ATTEMPTS[key] = attempts
    if len(attempts) >= Config.LOGIN_MAX_ATTEMPTS:
        remaining = int(Config.LOGIN_LOCKOUT_SECONDS - (now - attempts[0]))
        return False, max(1, remaining)
    return True, 0

def record_failed_login(key):
    now = time.time()
    if key not in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[key] = []
    LOGIN_ATTEMPTS[key].append(now)

def clear_login_attempts(key):
    LOGIN_ATTEMPTS.pop(key, None)

def log_audit(user_id, role, action):
    try:
        ip = request.remote_addr or "127.0.0.1"
        execute_db(
            "INSERT INTO audit_logs (user_id, role, action, ip_address) VALUES (?, ?, ?, ?)",
            (str(user_id), str(role), str(action), str(ip))
        )
    except Exception as e:
        print(f"[WARN] Failed to write audit log: {e}")

@app.route("/api/csrf-token")
def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    return jsonify({"csrf_token": session["csrf_token"]})


@app.route("/login")
def login_page():
    return send_from_directory(BASE_DIR, "login.html")

@app.route("/admin/dashboard")
def admin_dashboard_page():
    return send_from_directory(BASE_DIR, "admin-dashboard.html")

@app.route("/staff/dashboard")
@app.route("/faculty/dashboard")
def staff_dashboard_page():
    return send_from_directory(BASE_DIR, "faculty-dashboard.html")

@app.route("/student/dashboard")
def student_dashboard_page():
    return send_from_directory(BASE_DIR, "student-dashboard.html")


@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json(force=True)
    login_id = (data.get("login_id") or data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    role_hint = (data.get("role") or "").strip().lower()

    client_ip = request.remote_addr or "127.0.0.1"
    rate_key = f"{client_ip}_{login_id.upper()}"

    # Check Rate Limit
    allowed, wait_sec = check_login_rate_limit(rate_key)
    if not allowed:
        return jsonify({
            "error": f"Too many failed login attempts. Account temporarily locked for security. Please try again in {wait_sec} seconds."
        }), 429

    if not login_id or not password:
        return jsonify({"error": "Please provide both Login ID and Password."}), 400

    # 1. Determine Role from 5-character prefix or legacy identifier
    expected_role = None
    upper_id = login_id.upper()

    m = re.match(r"^(ADM|STF|STU)(\d{2})([ATS])?", upper_id)
    if m:
        p = m.group(1)
        if p == "ADM":
            expected_role = "administrator"
        elif p == "STF":
            expected_role = "faculty"
        elif p == "STU":
            expected_role = "student"
    elif upper_id.startswith("ADM"):
        expected_role = "administrator"
    elif upper_id.startswith("STF") or upper_id.startswith("FAC") or upper_id.startswith("AG"):
        expected_role = "faculty"
    elif upper_id.startswith("STU") or upper_id.startswith("U18"):
        expected_role = "student"
    else:
        # Fallback to role parameter or legacy username detection
        if role_hint in ["administrator", "admin"] or login_id.lower() == "admin":
            expected_role = "administrator"
        elif role_hint in ["faculty", "staff", "stf", "guide"]:
            expected_role = "faculty"
        elif role_hint in ["student", "std"]:
            expected_role = "student"
        else:
            record_failed_login(rate_key)
            return jsonify({
                "error": "Invalid Login ID prefix. Valid prefixes are: ADM (Admin), STF (Staff), or STU (Student) followed by 2-digit year (e.g. ADM26, STF26, STU26)."
            }), 400

    # 2. Authenticate against database tables
    user_record = None
    target_role = expected_role

    if expected_role == "administrator":
        # Search by login_id OR username
        admin = query_db(
            "SELECT * FROM admin WHERE UPPER(COALESCE(login_id, '')) = ? OR LOWER(username) = LOWER(?)",
            (upper_id, login_id), one=True
        )
        if admin:
            user_record = admin
            user_display_name = "Administrator"
            redirect_url = "/admin/dashboard"
            uname_field = admin["username"]

    elif expected_role == "faculty":
        # Search by login_id OR faculty_id OR email
        fac = query_db(
            "SELECT * FROM faculty WHERE UPPER(COALESCE(login_id, '')) = ? OR LOWER(faculty_id) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (upper_id, login_id, login_id), one=True
        )
        if fac:
            user_record = fac
            user_display_name = fac["name"]
            redirect_url = "/staff/dashboard"
            uname_field = fac["faculty_id"]

    elif expected_role == "student":
        # Search by login_id OR usn OR email
        stu = query_db(
            "SELECT * FROM students WHERE UPPER(COALESCE(login_id, '')) = ? OR LOWER(usn) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (upper_id, login_id, login_id), one=True
        )
        if stu:
            user_record = stu
            user_display_name = stu["name"]
            redirect_url = "/student/dashboard"
            uname_field = stu["usn"]

    if not user_record:
        record_failed_login(rate_key)
        return jsonify({"error": "Invalid credentials or account does not exist."}), 401

    # 3. Check Account Status (is_active)
    if "is_active" in user_record and user_record["is_active"] == 0:
        log_audit(login_id, expected_role, "LOGIN_FAILED_ACCOUNT_INACTIVE")
        return jsonify({"error": "Account is inactive. Please contact the administrator to activate your account."}), 403

    # 4. Check Stored Role Matches Expected Role
    stored_role = (user_record.get("role") or expected_role).strip().lower()
    if stored_role != expected_role:
        record_failed_login(rate_key)
        log_audit(login_id, expected_role, "LOGIN_FAILED_ROLE_MISMATCH")
        return jsonify({"error": "Role mismatch detected for this Login ID."}), 403

    # 5. Verify Password
    stored_pw = user_record["password"]
    fallbacks = []
    if expected_role == "faculty":
        fallbacks = [user_record.get("faculty_id", ""), user_record.get("login_id", ""), "Guide@123", "Faculty@123", "1234"]
    elif expected_role == "student":
        fallbacks = [user_record.get("usn", ""), user_record.get("login_id", ""), "Student@123", "1234"]
    elif expected_role == "administrator":
        fallbacks = ["Admin@123", "admin", "1234"]

    if not verify_password(stored_pw, password, fallbacks):
        record_failed_login(rate_key)
        log_audit(login_id, expected_role, "LOGIN_FAILED_INCORRECT_PASSWORD")
        return jsonify({"error": "Incorrect password. Please verify your password and try again."}), 401

    # 6. Success: Clear rate limits, regenerate session
    clear_login_attempts(rate_key)
    session.clear()
    session.permanent   = True
    session["user_id"]   = user_record["id"]
    session["user_role"] = expected_role
    session["role"]      = expected_role
    session["username"]  = uname_field
    session["login_id"]  = user_record.get("login_id") or login_id
    session["user_name"] = user_display_name
    session["email"]     = user_record.get("email", "")

    log_audit(session["login_id"], expected_role, "LOGIN_SUCCESS")

    return jsonify({
        "success":    True,
        "role":       expected_role,
        "login_id":   session["login_id"],
        "username":   uname_field,
        "name":       user_display_name,
        "email":      user_record.get("email", ""),
        "redirect":   redirect_url
    })


@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():
    data       = request.get_json(force=True)
    current_pw = (data.get("current_password") or "").strip()
    new_pw     = (data.get("new_password")     or "").strip()
    confirm_pw = (data.get("confirm_password") or "").strip()

    if not current_pw or not new_pw:
        return jsonify({"error": "Please provide current password and new password."}), 400
    if new_pw != confirm_pw:
        return jsonify({"error": "New passwords do not match."}), 400
    if len(new_pw) < 4:
        return jsonify({"error": "New password must be at least 4 characters long."}), 400

    role    = session.get("user_role")
    user_id = session.get("user_id")

    if role == "administrator":
        admin = query_db("SELECT * FROM admin WHERE id = ?", (user_id,), one=True)
        if not admin or not verify_password(admin["password"], current_pw, ["Admin@123", "admin"]):
            return jsonify({"error": "Current password is incorrect."}), 400
        execute_db("UPDATE admin SET password = ? WHERE id = ?", (generate_password_hash(new_pw), user_id))

    elif role == "faculty":
        fac = query_db("SELECT * FROM faculty WHERE id = ?", (user_id,), one=True)
        fallbacks = [fac["faculty_id"], "Guide@123", "Faculty@123", "1234"] if fac else []
        if not fac or not verify_password(fac["password"], current_pw, fallbacks):
            return jsonify({"error": "Current password is incorrect."}), 400
        execute_db("UPDATE faculty SET password = ? WHERE id = ?", (generate_password_hash(new_pw), user_id))

    elif role == "student":
        stu = query_db("SELECT * FROM students WHERE id = ?", (user_id,), one=True)
        fallbacks = [stu["usn"], "Student@123", "1234"] if stu else []
        if not stu or not verify_password(stu["password"], current_pw, fallbacks):
            return jsonify({"error": "Current password is incorrect."}), 400
        execute_db("UPDATE students SET password = ? WHERE id = ?", (generate_password_hash(new_pw), user_id))

    return jsonify({"success": True, "message": "Password updated successfully!"})


@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data       = request.get_json(force=True)
    role_raw   = (data.get("role")       or "").strip().lower()
    identifier = (data.get("identifier") or "").strip()
    email      = (data.get("email")      or "").strip().lower()
    new_pw     = (data.get("new_password") or "").strip()

    if not identifier or not email:
        return jsonify({"error": "Please provide your Username/USN and registered Email."}), 400

    if role_raw in ["faculty", "guide", "staff", "stf"]:
        fac = query_db(
            "SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?) AND LOWER(email) = LOWER(?)",
            (identifier, email), one=True
        )
        if not fac:
            return jsonify({"error": "No matching Faculty account found with this Faculty ID and Email."}), 404

        reset_pw = new_pw if new_pw else fac["faculty_id"]
        execute_db("UPDATE faculty SET password = ? WHERE id = ?", (generate_password_hash(reset_pw), fac["id"]))
        return jsonify({
            "success": True,
            "message": f"Password reset successfully for {fac['name']}! New password is: {reset_pw}",
            "new_password": reset_pw
        })

    elif role_raw in ["student", "std"]:
        stu = query_db(
            "SELECT * FROM students WHERE LOWER(usn) = LOWER(?) AND LOWER(email) = LOWER(?)",
            (identifier, email), one=True
        )
        if not stu:
            return jsonify({"error": "No matching Student account found with this USN and Email."}), 404

        reset_pw = new_pw if new_pw else stu["usn"]
        execute_db("UPDATE students SET password = ? WHERE id = ?", (generate_password_hash(reset_pw), stu["id"]))
        return jsonify({
            "success": True,
            "message": f"Password reset successfully for {stu['name']}! New password is: {reset_pw}",
            "new_password": reset_pw
        })

    return jsonify({"error": "Please select a valid role (Faculty/Staff or Student)."}), 400


@app.route("/api/admin/reset-password", methods=["POST"])
@role_required("administrator")
def admin_reset_password():
    data      = request.get_json(force=True)
    role_raw  = (data.get("role") or "").strip().lower()
    target_id = (data.get("id")   or "").strip()
    new_pw    = (data.get("new_password") or "").strip()

    if not role_raw or not target_id:
        return jsonify({"error": "Role and Target ID are required."}), 400

    if role_raw in ["student", "std"]:
        stu = query_db("SELECT * FROM students WHERE LOWER(usn) = LOWER(?)", (target_id,), one=True)
        if not stu:
            return jsonify({"error": f"Student '{target_id}' not found."}), 404
        reset_pw = new_pw if new_pw else stu["usn"]
        execute_db("UPDATE students SET password = ? WHERE id = ?", (generate_password_hash(reset_pw), stu["id"]))
        return jsonify({
            "success": True,
            "message": f"Password for student '{stu['usn']}' has been reset to: {reset_pw}",
            "new_password": reset_pw
        })

    elif role_raw in ["faculty", "staff", "stf", "guide"]:
        fac = query_db("SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?)", (target_id,), one=True)
        if not fac:
            return jsonify({"error": f"Faculty '{target_id}' not found."}), 404
        reset_pw = new_pw if new_pw else fac["faculty_id"]
        execute_db("UPDATE faculty SET password = ? WHERE id = ?", (generate_password_hash(reset_pw), fac["id"]))
        return jsonify({
            "success": True,
            "message": f"Password for faculty '{fac['faculty_id']}' has been reset to: {reset_pw}",
            "new_password": reset_pw
        })

    return jsonify({"error": "Invalid role specified."}), 400


@app.route("/api/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False, "role": None, "error": "Unauthorized"}), 401
    role = session.get("user_role") or session.get("role")
    return jsonify({
        "logged_in": True,
        "user_id":   session.get("user_id"),
        "role":      role,
        "user_role": role,
        "username":  session.get("username"),
        "login_id":  session.get("login_id"),
        "name":      session.get("user_name"),
    })


# ─────────────────────────────────────────────────────────────────────────────
# STUDENTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/admin/next-login-id", methods=["GET"])
@role_required("administrator")
def get_next_login_id():
    role = request.args.get("role", "student")
    year = request.args.get("year", Config.REGISTRATION_YEAR)
    try:
        lid = generate_login_id(role, year)
        return jsonify({"success": True, "login_id": lid, "role": role, "year": year})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/admin/administrators", methods=["POST"])
@role_required("administrator")
def add_admin():
    d        = request.get_json(force=True)
    username = (d.get("username") or "").strip()
    password = (d.get("password") or "").strip()
    year     = (d.get("year")     or Config.REGISTRATION_YEAR).strip()

    if not username or not password:
        return jsonify({"error": "Username and Password are required."}), 400

    if query_db("SELECT id FROM admin WHERE LOWER(username) = LOWER(?)", (username,), one=True):
        return jsonify({"error": f"Administrator '{username}' already exists."}), 409

    login_id = generate_login_id("administrator", year)

    execute_db("""
        INSERT INTO admin (login_id, username, password, role, is_active)
        VALUES (?, ?, ?, 'administrator', 1)
    """, (login_id, username, generate_password_hash(password)))

    log_audit(session.get("username"), "administrator", f"CREATE_ADMIN: username={username}, login_id={login_id}")

    return jsonify({
        "success": True,
        "username": username,
        "login_id": login_id,
        "message": f"Administrator '{username}' created successfully with Login ID: {login_id}"
    }), 201


@app.route("/api/students", methods=["GET"])
@login_required
def get_students():
    role = session.get("user_role")
    faculty_filter = request.args.get("faculty")

    # If logged in as faculty, restrict to their assigned students only
    if role == "faculty":
        fid = session.get("username")
        rows = query_db("""
            SELECT DISTINCT s.*
            FROM students s
            JOIN internships i ON i.student_usn = s.usn
            WHERE i.faculty_id = ?
            ORDER BY s.id
        """, (fid,))
        if not rows:
            rows = query_db("SELECT * FROM students ORDER BY id")
    elif faculty_filter:
        rows = query_db("""
            SELECT DISTINCT s.*
            FROM students s
            JOIN internships i ON i.student_usn = s.usn
            WHERE i.faculty_id = ?
            ORDER BY s.id
        """, (faculty_filter,))
        if not rows:
            rows = query_db("SELECT * FROM students ORDER BY id")
    else:
        rows = query_db("SELECT * FROM students ORDER BY id")
    for r in rows:
        r.pop("password", None)
    return jsonify(rows)


@app.route("/api/students", methods=["POST"])
@role_required("administrator")
def add_student():
    d = request.get_json(force=True)
    usn      = (d.get("usn")      or "").strip()
    name     = (d.get("name")     or "").strip()
    email    = (d.get("email")    or "").strip()
    course   = (d.get("course")   or "BCA").strip()
    semester = (d.get("semester") or "1st").strip()
    phone    = (d.get("phone")    or "").strip()
    company  = (d.get("company")  or "").strip()
    status   = (d.get("status")   or "Not Started").strip()
    year     = (d.get("year")     or Config.REGISTRATION_YEAR).strip()
    password = d.get("password") or usn

    if not usn or not name or not email:
        return jsonify({"error": "USN, Name and Email are required."}), 400

    if query_db("SELECT id FROM students WHERE LOWER(usn) = LOWER(?)", (usn,), one=True):
        return jsonify({"error": f"USN '{usn}' already exists."}), 409

    if query_db("SELECT id FROM students WHERE LOWER(email) = LOWER(?)", (email,), one=True):
        return jsonify({"error": f"Email '{email}' is already registered with another student."}), 409

    login_id = generate_login_id("student", year)

    execute_db("""
        INSERT INTO students (login_id, usn, name, email, course, semester, phone, company, status, password, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'student', 1)
    """, (login_id, usn, name, email, course, semester, phone, company, status,
          generate_password_hash(password)))

    log_audit(session.get("username"), "administrator", f"CREATE_STUDENT: usn={usn}, login_id={login_id}")

    return jsonify({
        "success": True,
        "usn": usn,
        "login_id": login_id,
        "name": name,
        "message": f"Student '{name}' created successfully with Login ID: {login_id}"
    }), 201


@app.route("/api/students/<usn>", methods=["GET"])
@login_required
def get_student(usn):
    s = query_db("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    if not s:
        return jsonify({"error": "Student not found."}), 404
    s.pop("password", None)
    return jsonify(s)


@app.route("/api/students/<usn>", methods=["PUT"])
@role_required("administrator")
def update_student(usn):
    d = request.get_json(force=True)
    stu = query_db("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    if not stu:
        return jsonify({"error": "Student not found."}), 404

    new_email = (d.get("email") or "").strip()
    if new_email and new_email.lower() != (stu.get("email") or "").lower():
        if query_db("SELECT id FROM students WHERE LOWER(email) = LOWER(?) AND usn != ?", (new_email, usn), one=True):
            return jsonify({"error": f"Email '{new_email}' already in use by another student."}), 409

    fields  = ["name", "email", "course", "semester", "phone", "company", "status", "is_active"]
    updates = {f: d[f] for f in fields if f in d}
    if d.get("password") and d["password"].strip():
        updates["password"] = generate_password_hash(d["password"].strip())
    if not updates:
        return jsonify({"error": "Nothing to update."}), 400

    sql = "UPDATE students SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE usn=?"
    execute_db(sql, list(updates.values()) + [usn])
    log_audit(session.get("username"), "administrator", f"UPDATE_STUDENT: usn={usn}")
    return jsonify({"success": True})


@app.route("/api/students/<usn>", methods=["DELETE"])
@role_required("administrator")
def delete_student(usn):
    if not query_db("SELECT id FROM students WHERE usn = ?", (usn,), one=True):
        return jsonify({"error": "Student not found."}), 404
    execute_db("DELETE FROM students WHERE usn = ?", (usn,))
    log_audit(session.get("username"), "administrator", f"DELETE_STUDENT: usn={usn}")
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# FACULTY
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/faculty", methods=["GET"])
@login_required
def get_faculty():
    rows = query_db("SELECT * FROM faculty ORDER BY id")
    for r in rows:
        r.pop("password", None)
    return jsonify(rows)


@app.route("/api/faculty", methods=["POST"])
@role_required("administrator")
def add_faculty():
    d          = request.get_json(force=True)
    faculty_id = (d.get("facultyId")  or d.get("faculty_id") or "").strip()
    name       = (d.get("name")       or "").strip()
    email      = (d.get("email")      or "").strip()
    department = (d.get("department") or "Computer Applications").strip()
    phone      = (d.get("phone")      or "").strip()
    year       = (d.get("year")       or Config.REGISTRATION_YEAR).strip()
    password   = d.get("password") or faculty_id

    if not faculty_id or not name or not email:
        return jsonify({"error": "Faculty ID, Name and Email are required."}), 400

    if query_db("SELECT id FROM faculty WHERE LOWER(faculty_id) = LOWER(?)", (faculty_id,), one=True):
        return jsonify({"error": f"Faculty ID '{faculty_id}' already exists."}), 409

    if query_db("SELECT id FROM faculty WHERE LOWER(email) = LOWER(?)", (email,), one=True):
        return jsonify({"error": f"Email '{email}' is already registered with another faculty member."}), 409

    login_id = generate_login_id("faculty", year)

    execute_db("""
        INSERT INTO faculty (login_id, faculty_id, name, email, department, phone, password, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'faculty', 1)
    """, (login_id, faculty_id, name, email, department, phone,
          generate_password_hash(password)))

    log_audit(session.get("username"), "administrator", f"CREATE_FACULTY: faculty_id={faculty_id}, login_id={login_id}")

    return jsonify({
        "success": True,
        "facultyId": faculty_id,
        "login_id": login_id,
        "name": name,
        "message": f"Faculty '{name}' created successfully with Login ID: {login_id}"
    }), 201


@app.route("/api/faculty/<fid>", methods=["GET"])
@login_required
def get_faculty_member(fid):
    f = query_db("SELECT * FROM faculty WHERE faculty_id = ?", (fid,), one=True)
    if not f:
        return jsonify({"error": "Faculty not found."}), 404
    f.pop("password", None)
    return jsonify(f)


@app.route("/api/faculty/<fid>", methods=["PUT"])
@role_required("administrator")
def update_faculty(fid):
    d = request.get_json(force=True)
    if not query_db("SELECT id FROM faculty WHERE faculty_id = ?", (fid,), one=True):
        return jsonify({"error": "Faculty not found."}), 404

    fields  = ["name", "email", "department", "phone", "is_active"]
    updates = {k: d[k] for k in fields if k in d}
    if d.get("password") and d["password"].strip():
        updates["password"] = generate_password_hash(d["password"].strip())
    if not updates:
        return jsonify({"error": "Nothing to update."}), 400

    sql = "UPDATE faculty SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE faculty_id=?"
    execute_db(sql, list(updates.values()) + [fid])
    log_audit(session.get("username"), "administrator", f"UPDATE_FACULTY: faculty_id={fid}")
    return jsonify({"success": True})


@app.route("/api/faculty/<fid>", methods=["DELETE"])
@role_required("administrator")
def delete_faculty(fid):
    if not query_db("SELECT id FROM faculty WHERE faculty_id = ?", (fid,), one=True):
        return jsonify({"error": "Faculty not found."}), 404
    execute_db("DELETE FROM faculty WHERE faculty_id = ?", (fid,))
    log_audit(session.get("username"), "administrator", f"DELETE_FACULTY: faculty_id={fid}")
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# INTERNSHIPS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/internships", methods=["GET"])
@login_required
def get_internships():
    role = session.get("user_role")
    student_filter = request.args.get("student")
    faculty_filter = request.args.get("faculty")

    if role == "faculty":
        fid = session.get("username")
        rows = query_db("SELECT * FROM internships WHERE faculty_id = ? ORDER BY id", (fid,))
    elif role == "student":
        stu_usn = session.get("username")
        rows = query_db("SELECT * FROM internships WHERE student_usn = ? ORDER BY id", (stu_usn,))
    elif student_filter:
        rows = query_db(
            "SELECT * FROM internships WHERE student_usn = ? ORDER BY id",
            (student_filter,)
        )
    elif faculty_filter:
        rows = query_db(
            "SELECT * FROM internships WHERE faculty_id = ? ORDER BY id",
            (faculty_filter,)
        )
    else:
        rows = query_db("SELECT * FROM internships ORDER BY id")

    for row in rows:
        stu = query_db("SELECT name FROM students WHERE usn = ?", (row["student_usn"],), one=True)
        fac = query_db("SELECT name FROM faculty WHERE faculty_id = ?", (row["faculty_id"],), one=True)
        row["student_name"] = stu["name"] if stu else row["student_usn"]
        row["faculty_name"] = fac["name"] if fac else row["faculty_id"]

    return jsonify(rows)


@app.route("/api/internships", methods=["POST"])
@login_required
def add_internship():
    role        = session.get("user_role")
    if role not in ("administrator", "faculty"):
        return jsonify({"error": "Unauthorized"}), 403

    d           = request.get_json(force=True)
    student_usn = (d.get("student")   or "").strip()
    company     = (d.get("company")   or "").strip()
    title       = (d.get("title")     or "").strip()
    faculty_id  = (d.get("faculty")   or (session.get("username") if role == "faculty" else "")).strip()
    start_date  = (d.get("startDate") or "").strip()
    end_date    = (d.get("endDate")   or "").strip()
    status      = (d.get("status")    or "Not Started").strip()

    if not student_usn or not company or not title or not faculty_id:
        return jsonify({"error": "Student, Company, Title and Faculty are required."}), 400

    new_id = execute_db("""
        INSERT INTO internships (student_usn, company, title, faculty_id, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (student_usn, company, title, faculty_id, start_date, end_date, status))

    execute_db(
        "UPDATE students SET company=?, status=? WHERE usn=?",
        (company, status, student_usn)
    )
    return jsonify({"success": True, "id": new_id}), 201


@app.route("/api/internships/<int:iid>", methods=["PUT"])
@login_required
def update_internship(iid):
    role = session.get("user_role")
    d   = request.get_json(force=True)
    row = query_db("SELECT * FROM internships WHERE id = ?", (iid,), one=True)
    if not row:
        return jsonify({"error": "Internship not found."}), 404

    # Allow administrator or the assigned faculty guide
    if role != "administrator" and not (role == "faculty" and row["faculty_id"] == session.get("username")):
        return jsonify({"error": "Unauthorized"}), 403

    student_usn = d.get("student",   row["student_usn"])
    company     = d.get("company",   row["company"])
    title       = d.get("title",     row["title"])
    faculty_id  = d.get("faculty",   row["faculty_id"])
    start_date  = d.get("startDate", row["start_date"])
    end_date    = d.get("endDate",   row["end_date"])
    status      = d.get("status",    row["status"])

    execute_db("""
        UPDATE internships
        SET student_usn=?, company=?, title=?, faculty_id=?,
            start_date=?, end_date=?, status=?
        WHERE id=?
    """, (student_usn, company, title, faculty_id, start_date, end_date, status, iid))

    execute_db(
        "UPDATE students SET company=?, status=? WHERE usn=?",
        (company, status, student_usn)
    )
    return jsonify({"success": True})


@app.route("/api/internships/<int:iid>", methods=["DELETE"])
@login_required
def delete_internship(iid):
    role = session.get("user_role")
    row = query_db("SELECT * FROM internships WHERE id = ?", (iid,), one=True)
    if not row:
        return jsonify({"error": "Internship not found."}), 404
    if role != "administrator" and not (role == "faculty" and row["faculty_id"] == session.get("username")):
        return jsonify({"error": "Unauthorized"}), 403
    execute_db("DELETE FROM internships WHERE id = ?", (iid,))
    return jsonify({"success": True})


@app.route("/api/internships/<int:iid>/approve", methods=["POST"])
@role_required("administrator")
def approve_internship(iid):
    row = query_db("SELECT * FROM internships WHERE id = ?", (iid,), one=True)
    if not row:
        return jsonify({"error": "Internship not found."}), 404
    execute_db("UPDATE internships SET status = 'Approved' WHERE id = ?", (iid,))
    execute_db("UPDATE students SET status = 'Approved' WHERE usn = ?", (row["student_usn"],))
    log_audit(session.get("username"), "administrator", f"APPROVED_INTERNSHIP_{iid}_FOR_{row['student_usn']}")
    return jsonify({"success": True, "message": f"Internship for {row['student_usn']} approved successfully!"})


@app.route("/api/internships/progress-sheet/<usn>", methods=["GET"])
@login_required
def get_progress_sheet(usn):
    stu = query_db("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    if not stu:
        return jsonify({"error": "Student not found."}), 404

    internship = query_db("SELECT * FROM internships WHERE student_usn = ? ORDER BY id DESC LIMIT 1", (usn,), one=True)
    faculty_id = internship["faculty_id"] if internship else None
    faculty = query_db("SELECT * FROM faculty WHERE faculty_id = ?", (faculty_id,), one=True) if faculty_id else None

    row = query_db("SELECT sheet_data FROM progress_sheets WHERE student_usn = ?", (usn,), one=True)
    sheet_data = json.loads(row["sheet_data"]) if row and row["sheet_data"] else None

    updates = query_db("SELECT * FROM updates WHERE student_usn = ? ORDER BY date ASC", (usn,))

    return jsonify({
        "student": {
            "name": stu["name"],
            "usn": stu["usn"],
            "phone": stu.get("phone") or "-",
            "course": stu.get("course") or "MCA",
            "company": (internship.get("company") if internship else stu.get("company")) or "-",
            "title": (internship.get("title") if internship else "Internship Project") or "-",
            "faculty_name": faculty["name"] if faculty else (internship.get("faculty_id") if internship else "Internal Guide"),
            "faculty_phone": faculty.get("phone") if faculty else "-",
            "external_guide": "-",
            "external_phone": "-"
        },
        "sheet": sheet_data,
        "updates": updates
    })


@app.route("/api/internships/progress-sheet/<usn>", methods=["POST"])
@login_required
def save_progress_sheet(usn):
    d = request.get_json(force=True)
    sheet_data = json.dumps(d)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute_db("""
        INSERT INTO progress_sheets (student_usn, sheet_data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(student_usn) DO UPDATE SET
            sheet_data = excluded.sheet_data,
            updated_at = excluded.updated_at
    """, (usn, sheet_data, now))

    # Sync company & title if present in metadata
    meta = d.get("meta") or {}
    comp = (meta.get("company") or "").strip()
    titl = (meta.get("title") or "").strip()
    if comp:
        execute_db("UPDATE internships SET company = ? WHERE student_usn = ?", (comp, usn))
        execute_db("UPDATE students SET company = ? WHERE usn = ?", (comp, usn))
    if titl:
        execute_db("UPDATE internships SET title = ? WHERE student_usn = ?", (titl, usn))

    # Calculate approved weeks count
    weeks = d.get("weeks") or []
    approved_count = sum(1 for w in weeks if w.get("approved"))

    # If all 12 weeks are approved, update student & internship status to Approved
    if approved_count == 12:
        execute_db("UPDATE internships SET status = 'Approved' WHERE student_usn = ?", (usn,))
        execute_db("UPDATE students SET status = 'Approved' WHERE usn = ?", (usn,))
    elif approved_count > 0:
        internship = query_db("SELECT status FROM internships WHERE student_usn = ?", (usn,), one=True)
        if internship and internship.get("status") in ["Not Started", ""]:
            execute_db("UPDATE internships SET status = 'In Progress' WHERE student_usn = ?", (usn,))

    username = session.get("username") or "user"
    user_role = session.get("user_role") or "faculty"
    log_audit(username, user_role, f"SAVED_PROGRESS_SHEET_FOR_{usn}_APPROVED_{approved_count}_WEEKS")

    return jsonify({
        "success": True,
        "approved_count": approved_count,
        "message": f"Progress sheet saved ({approved_count}/12 weeks approved)."
    })


@app.route("/api/internships/progress-sheet/<usn>/week/<int:week_no>/approve", methods=["POST"])
@login_required
def approve_sheet_week(usn, week_no):
    if week_no < 1 or week_no > 12:
        return jsonify({"error": "Invalid week number (must be 1-12)."}), 400

    row = query_db("SELECT sheet_data FROM progress_sheets WHERE student_usn = ?", (usn,), one=True)
    if row and row["sheet_data"]:
        sheet_data = json.loads(row["sheet_data"])
    else:
        sheet_data = {
            "meta": {},
            "weeks": [{"sl": i, "week": f"Week - {i:02d}", "work": "", "remarks": "", "approved": False} for i in range(1, 13)]
        }

    weeks = sheet_data.get("weeks", [])
    req_data = request.get_json(silent=True) or {}
    approved_state = req_data.get("approved", True)

    target_week = None
    for w in weeks:
        if w.get("sl") == week_no:
            w["approved"] = approved_state
            if "remarks" in req_data:
                w["remarks"] = req_data["remarks"]
            if "work" in req_data:
                w["work"] = req_data["work"]
            target_week = w
            break

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_db("""
        INSERT INTO progress_sheets (student_usn, sheet_data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(student_usn) DO UPDATE SET
            sheet_data = excluded.sheet_data,
            updated_at = excluded.updated_at
    """, (usn, json.dumps(sheet_data), now))

    approved_count = sum(1 for w in weeks if w.get("approved"))
    if approved_count == 12:
        execute_db("UPDATE internships SET status = 'Approved' WHERE student_usn = ?", (usn,))
        execute_db("UPDATE students SET status = 'Approved' WHERE usn = ?", (usn,))

    log_audit(session.get("username") or "user", session.get("user_role") or "faculty", f"SET_WEEK_{week_no}_APPROVE_{approved_state}_FOR_{usn}")
    return jsonify({"success": True, "week": target_week, "approved_count": approved_count})


@app.route("/api/student/progress-sheet", methods=["GET", "POST"])
@login_required
def student_progress_sheet():
    usn = session.get("username")
    role = session.get("user_role")
    if role != "student" or not usn:
        return jsonify({"error": "Only student accounts can access /api/student/progress-sheet."}), 403

    if request.method == "GET":
        return get_progress_sheet(usn)
    else:
        return save_progress_sheet(usn)




# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/attendance", methods=["GET"])
@login_required
def get_attendance():
    student_filter = request.args.get("student")
    faculty_filter = request.args.get("faculty")

    if student_filter:
        rows = query_db(
            "SELECT * FROM attendance WHERE student_usn = ? ORDER BY date DESC",
            (student_filter,)
        )
    elif faculty_filter:
        rows = query_db(
            "SELECT * FROM attendance WHERE faculty_id = ? ORDER BY date DESC",
            (faculty_filter,)
        )
    else:
        rows = query_db("SELECT * FROM attendance ORDER BY date DESC")

    for row in rows:
        stu = query_db("SELECT name FROM students WHERE usn = ?", (row["student_usn"],), one=True)
        row["student_name"] = stu["name"] if stu else row["student_usn"]

    return jsonify(rows)


@app.route("/api/attendance", methods=["POST"])
@role_required("faculty", "administrator")
def save_attendance():
    d = request.get_json(force=True)
    faculty_id = session.get("username")

    if isinstance(d, list):
        items = d
    elif isinstance(d, dict) and "records" in d:
        batch_date = (d.get("date") or "").strip()
        items = []
        for r in d.get("records", []):
            if batch_date and not r.get("date"):
                r["date"] = batch_date
            items.append(r)
    else:
        items = [d]

    saved_count = 0
    for item in items:
        student_usn = (item.get("usn") or item.get("student_usn") or "").strip()
        date        = (item.get("date") or "").strip()
        status      = (item.get("status") or "Present").strip()
        remarks     = (item.get("remarks") or "").strip()
        if not student_usn or not date:
            continue
        existing = query_db(
            "SELECT id FROM attendance WHERE student_usn=? AND date=?",
            (student_usn, date), one=True
        )
        if existing:
            execute_db(
                "UPDATE attendance SET status=?, remarks=?, faculty_id=? WHERE student_usn=? AND date=?",
                (status, remarks, faculty_id, student_usn, date)
            )
        else:
            execute_db(
                "INSERT INTO attendance (student_usn, faculty_id, date, status, remarks) VALUES (?,?,?,?,?)",
                (student_usn, faculty_id, date, status, remarks)
            )
        saved_count += 1

    return jsonify({"success": True, "saved_count": saved_count})


# ─────────────────────────────────────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    student_filter = request.args.get("student")
    faculty_filter = request.args.get("faculty")

    if student_filter:
        rows = query_db(
            "SELECT * FROM tasks WHERE student_usn = ? ORDER BY id DESC",
            (student_filter,)
        )
    elif faculty_filter:
        rows = query_db("""
            SELECT t.* FROM tasks t
            JOIN internships i ON i.student_usn = t.student_usn
            WHERE i.faculty_id = ?
            ORDER BY t.id DESC
        """, (faculty_filter,))
    else:
        rows = query_db("SELECT * FROM tasks ORDER BY id DESC")

    for row in rows:
        stu = query_db("SELECT name FROM students WHERE usn = ?", (row["student_usn"],), one=True)
        row["student_name"] = stu["name"] if stu else row["student_usn"]

    return jsonify(rows)


@app.route("/api/tasks", methods=["POST"])
@role_required("student")
def submit_task():
    d           = request.get_json(force=True)
    title       = (d.get("title")       or "").strip()
    description = (d.get("description") or "").strip()
    student_usn = session.get("username")
    submitted_on = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not title:
        return jsonify({"error": "Title is required."}), 400

    new_id = execute_db(
        "INSERT INTO tasks (student_usn, title, description, submitted_on) VALUES (?,?,?,?)",
        (student_usn, title, description, submitted_on)
    )
    return jsonify({"success": True, "id": new_id}), 201


@app.route("/api/tasks/<int:tid>", methods=["PUT"])
@role_required("faculty", "administrator")
def update_task(tid):
    d = request.get_json(force=True)
    if not query_db("SELECT id FROM tasks WHERE id=?", (tid,), one=True):
        return jsonify({"error": "Task not found."}), 404

    remarks = d.get("remarks", "")
    status  = d.get("status", "Reviewed")
    execute_db(
        "UPDATE tasks SET faculty_remarks=?, status=? WHERE id=?",
        (remarks, status, tid)
    )
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATIONS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/evaluations", methods=["GET"])
@login_required
def get_evaluations():
    student_filter = request.args.get("student")
    faculty_filter = request.args.get("faculty")

    if student_filter:
        rows = query_db(
            "SELECT * FROM evaluations WHERE student_usn = ? ORDER BY id DESC",
            (student_filter,)
        )
    elif faculty_filter:
        rows = query_db(
            "SELECT * FROM evaluations WHERE faculty_id = ? ORDER BY id DESC",
            (faculty_filter,)
        )
    else:
        rows = query_db("SELECT * FROM evaluations ORDER BY id DESC")

    for row in rows:
        stu = query_db("SELECT name FROM students WHERE usn = ?", (row["student_usn"],), one=True)
        row["student_name"] = stu["name"] if stu else row["student_usn"]

    return jsonify(rows)


@app.route("/api/evaluations", methods=["POST"])
@role_required("faculty", "administrator")
def add_evaluation():
    d = request.get_json(force=True)
    faculty_id = session.get("username")
    evaluated_on = datetime.now().strftime("%Y-%m-%d")

    items = d if isinstance(d, list) else (d.get("evaluations") if isinstance(d, dict) and "evaluations" in d else [d])

    saved_count = 0
    last_id = None
    for item in items:
        student_usn     = (item.get("studentUsn") or item.get("student_usn") or item.get("usn") or "").strip()
        overall         = int(item.get("overall", item.get("score", 0)))
        technical       = int(item.get("technical", overall))
        communication   = int(item.get("communication", overall))
        punctuality     = int(item.get("punctuality", overall))
        problem_solving = int(item.get("problemSolving", overall))
        remarks         = (item.get("remarks") or item.get("feedback") or "").strip()
        status          = (item.get("status") or "Approved").strip()
        if not student_usn:
            continue

        existing = query_db(
            "SELECT id FROM evaluations WHERE student_usn=?",
            (student_usn,), one=True
        )
        if existing:
            execute_db("""
                UPDATE evaluations
                SET technical_skills=?, communication=?, punctuality=?,
                    problem_solving=?, overall_score=?, remarks=?, evaluated_on=?, status=?, faculty_id=?
                WHERE id=?
            """, (technical, communication, punctuality, problem_solving,
                  overall, remarks, evaluated_on, status, faculty_id, existing["id"]))
            last_id = existing["id"]
        else:
            last_id = execute_db("""
                INSERT INTO evaluations
                    (student_usn, faculty_id, technical_skills, communication,
                     punctuality, problem_solving, overall_score, remarks, evaluated_on, status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (student_usn, faculty_id, technical, communication, punctuality,
                  problem_solving, overall, remarks, evaluated_on, status))
        saved_count += 1

    return jsonify({"success": True, "id": last_id, "saved_count": saved_count}), 201


@app.route("/api/evaluations/approve/<student_usn>", methods=["POST"])
@role_required("faculty", "administrator")
def approve_evaluation(student_usn):
    d = request.get_json(silent=True) or {}
    faculty_id = session.get("username")
    evaluated_on = datetime.now().strftime("%Y-%m-%d")

    overall = int(d.get("overall", d.get("score", 85)))
    remarks = (d.get("remarks") or d.get("feedback") or "Approved").strip()

    existing = query_db("SELECT id FROM evaluations WHERE student_usn=?", (student_usn,), one=True)
    if existing:
        execute_db("""
            UPDATE evaluations 
            SET status='Approved', overall_score=?, remarks=?, evaluated_on=?, faculty_id=?
            WHERE id=?
        """, (overall, remarks, evaluated_on, faculty_id, existing["id"]))
        eid = existing["id"]
    else:
        eid = execute_db("""
            INSERT INTO evaluations 
                (student_usn, faculty_id, technical_skills, communication, punctuality, problem_solving, overall_score, remarks, evaluated_on, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Approved')
        """, (student_usn, faculty_id, overall, overall, overall, overall, overall, remarks, evaluated_on))

    log_audit(faculty_id, session.get("user_role") or "faculty", f"APPROVED_EVALUATION_FOR_{student_usn}")
    return jsonify({"success": True, "id": eid, "message": f"Evaluation for {student_usn} approved successfully!"})


@app.route("/api/evaluations/<int:eid>", methods=["PUT"])
@role_required("faculty", "administrator")
def update_evaluation(eid):
    d   = request.get_json(force=True)
    if not query_db("SELECT id FROM evaluations WHERE id=?", (eid,), one=True):
        return jsonify({"error": "Evaluation not found."}), 404

    fields  = ["technical_skills", "communication", "punctuality",
               "problem_solving", "overall_score", "remarks", "status"]
    updates = {f: d[f] for f in fields if f in d}
    if not updates:
        return jsonify({"error": "Nothing to update."}), 400

    sql = "UPDATE evaluations SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE id=?"
    execute_db(sql, list(updates.values()) + [eid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# DAILY UPDATES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/updates", methods=["GET"])
@login_required
def get_updates():
    student_filter = request.args.get("student")
    faculty_filter = request.args.get("faculty")

    if student_filter:
        rows = query_db(
            "SELECT * FROM updates WHERE student_usn = ? ORDER BY date DESC",
            (student_filter,)
        )
    elif faculty_filter:
        rows = query_db("""
            SELECT u.* FROM updates u
            JOIN internships i ON i.student_usn = u.student_usn
            WHERE i.faculty_id = ?
            ORDER BY u.date DESC
        """, (faculty_filter,))
    else:
        rows = query_db("SELECT * FROM updates ORDER BY date DESC")

    for row in rows:
        stu = query_db("SELECT name FROM students WHERE usn = ?", (row["student_usn"],), one=True)
        row["student_name"] = stu["name"] if stu else row["student_usn"]

    return jsonify(rows)


@app.route("/api/updates", methods=["POST"])
@role_required("student")
def post_update():
    # Support both FormData (multipart/form-data) and JSON
    if request.is_json:
        d = request.get_json(silent=True) or {}
    else:
        d = request.form

    date        = (d.get("date")        or datetime.now().strftime("%Y-%m-%d")).strip()
    description = (d.get("description") or "").strip()
    work_done   = (d.get("workDone")    or d.get("work_done") or "").strip()
    challenges  = (d.get("challenges")  or d.get("remarks") or "").strip()
    student_usn = session.get("username")
    submitted_on = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not description:
        return jsonify({"error": "Description is required."}), 400

    document_path = ""
    document_name = ""

    # Check for uploaded document (PDF or Doc)
    if "document" in request.files:
        file = request.files["document"]
        if file and file.filename:
            orig_name = secure_filename(file.filename)
            ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else ""
            if ext not in Config.ALLOWED_DOCUMENT_EXTENSIONS:
                return jsonify({
                    "error": f"Invalid document type '.{ext}'. Allowed formats: {', '.join(sorted(Config.ALLOWED_DOCUMENT_EXTENSIONS))}"
                }), 400

            os.makedirs(Config.DOCUMENTS_UPLOAD_FOLDER, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_fname = f"{student_usn}_{timestamp}_{orig_name}"
            file_dest = os.path.join(Config.DOCUMENTS_UPLOAD_FOLDER, unique_fname)
            file.save(file_dest)

            document_path = f"/uploads/documents/{unique_fname}"
            document_name = file.filename

    new_id = execute_db("""
        INSERT INTO updates (student_usn, date, description, work_done, challenges, submitted_on, document_path, document_name, status)
        VALUES (?,?,?,?,?,?,?,?, 'Pending')
    """, (student_usn, date, description, work_done, challenges, submitted_on, document_path, document_name))

    log_audit(student_usn, "student", f"SUBMITTED_WEEKLY_UPDATE_{new_id}_DOC_{bool(document_path)}")

    return jsonify({
        "success": True,
        "id": new_id,
        "document_path": document_path,
        "document_name": document_name,
        "status": "Pending",
        "message": "Weekly update submitted successfully!"
    }), 201


@app.route("/uploads/documents/<path:filename>")
def serve_update_document(filename):
    if "user_id" not in session and "username" not in session:
        return redirect("/login")

    target_name = secure_filename(filename)
    filepath = os.path.join(Config.DOCUMENTS_UPLOAD_FOLDER, target_name)
    if not os.path.exists(filepath):
        raw_filepath = os.path.join(Config.DOCUMENTS_UPLOAD_FOLDER, filename)
        if os.path.exists(raw_filepath):
            target_name = filename
            filepath = raw_filepath
        else:
            return jsonify({"error": "Document not found on server."}), 404

    ext = target_name.lower().rsplit(".", 1)[-1] if "." in target_name else ""
    mime_map = {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "rtf": "application/rtf"
    }
    mimetype = mime_map.get(ext) or mimetypes.guess_type(filepath)[0] or "application/octet-stream"

    response = make_response(send_from_directory(Config.DOCUMENTS_UPLOAD_FOLDER, target_name, mimetype=mimetype, as_attachment=False))
    response.headers["Content-Type"] = mimetype
    response.headers["Content-Disposition"] = f'inline; filename="{target_name}"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/api/updates/<int:uid>/approve", methods=["POST"])
@login_required
def approve_update(uid):
    role = session.get("user_role")
    if role not in ["faculty", "administrator"]:
        return jsonify({"error": "Unauthorized. Only faculty and administrators can approve weekly updates."}), 403

    upd = query_db("SELECT * FROM updates WHERE id = ?", (uid,), one=True)
    if not upd:
        return jsonify({"error": "Weekly update record not found."}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status") or "Approved"
    remarks = (data.get("remarks") or data.get("staff_remarks") or "").strip()
    staff_id = session.get("username") or "staff"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    execute_db("""
        UPDATE updates
        SET status = ?, staff_remarks = ?, approved_by = ?, approved_at = ?
        WHERE id = ?
    """, (new_status, remarks, staff_id, now, uid))

    log_audit(staff_id, role, f"SET_WEEKLY_UPDATE_{uid}_STATUS_{new_status}_FOR_{upd['student_usn']}")
    return jsonify({
        "success": True,
        "message": f"Weekly update for {upd['student_usn']} marked as {new_status}!",
        "status": new_status,
        "staff_remarks": remarks
    })


@app.route("/api/updates/approve-all", methods=["POST"])
@login_required
def approve_all_updates():
    role = session.get("user_role")
    if role not in ["faculty", "administrator"]:
        return jsonify({"error": "Unauthorized."}), 403

    data = request.get_json(silent=True) or {}
    student_usn = data.get("student_usn")
    staff_id = session.get("username") or "staff"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if student_usn and student_usn != "all":
        execute_db("""
            UPDATE updates
            SET status = 'Approved', approved_by = ?, approved_at = ?
            WHERE student_usn = ? AND status != 'Approved'
        """, (staff_id, now, student_usn))
    else:
        execute_db("""
            UPDATE updates
            SET status = 'Approved', approved_by = ?, approved_at = ?
            WHERE status != 'Approved'
        """, (staff_id, now))

    return jsonify({"success": True, "message": "All matching updates approved successfully!"})


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/admin/stats")
@role_required("administrator")
def admin_stats():
    return jsonify({
        "totalStudents":        query_db("SELECT COUNT(*) as c FROM students", one=True)["c"],
        "totalFaculty":         query_db("SELECT COUNT(*) as c FROM faculty",  one=True)["c"],
        "activeInternships":    query_db("SELECT COUNT(*) as c FROM internships WHERE status='Active'", one=True)["c"],
        "completedInternships": query_db("SELECT COUNT(*) as c FROM internships WHERE status='Completed'", one=True)["c"],
        "totalInternships":     query_db("SELECT COUNT(*) as c FROM internships", one=True)["c"],
        "pendingTasks":         query_db("SELECT COUNT(*) as c FROM tasks WHERE status='Pending'", one=True)["c"],
    })


@app.route("/api/faculty/stats")
@role_required("faculty")
def faculty_stats():
    fid = session.get("username")
    return jsonify({
        "assignedStudents":   query_db(
            "SELECT COUNT(DISTINCT student_usn) as c FROM internships WHERE faculty_id=?",
            (fid,), one=True)["c"],
        "activeInternships":  query_db(
            "SELECT COUNT(*) as c FROM internships WHERE faculty_id=? AND status='Active'",
            (fid,), one=True)["c"],
        "pendingEvaluations": query_db("""
            SELECT COUNT(DISTINCT i.student_usn) as c
            FROM internships i
            WHERE i.faculty_id=?
              AND i.student_usn NOT IN (
                  SELECT student_usn FROM evaluations WHERE faculty_id=?
              )""", (fid, fid), one=True)["c"],
        "completed":          query_db(
            "SELECT COUNT(*) as c FROM internships WHERE faculty_id=? AND status='Completed'",
            (fid,), one=True)["c"],
    })


@app.route("/api/student/stats")
@role_required("student")
def student_stats():
    usn = session.get("username")
    stu = query_db("SELECT * FROM students WHERE usn=?", (usn,), one=True)
    if not stu:
        return jsonify({"error": "Student not found."}), 404
    stu.pop("password", None)

    internship = query_db(
        "SELECT * FROM internships WHERE student_usn=? ORDER BY id DESC LIMIT 1",
        (usn,), one=True
    )

    att_rows = query_db("SELECT status FROM attendance WHERE student_usn=?", (usn,))
    att_pct  = 0
    if att_rows:
        present = sum(1 for r in att_rows if r["status"] == "Present")
        att_pct = round(present / len(att_rows) * 100)

    tasks_total     = query_db("SELECT COUNT(*) as c FROM tasks WHERE student_usn=?", (usn,), one=True)["c"]
    tasks_completed = query_db("SELECT COUNT(*) as c FROM tasks WHERE student_usn=? AND status='Reviewed'", (usn,), one=True)["c"]

    ev = query_db(
        "SELECT overall_score FROM evaluations WHERE student_usn=? ORDER BY id DESC LIMIT 1",
        (usn,), one=True
    )

    return jsonify({
        "student":          stu,
        "internship":       internship,
        "attendancePct":    att_pct,
        "tasksTotal":       tasks_total,
        "tasksCompleted":   tasks_completed,
        "performanceScore": ev["overall_score"] if ev else 0,
    })


@app.route("/api/student/reports")
@role_required("student")
def student_reports():
    usn = session.get("username")
    stu = query_db("SELECT * FROM students WHERE usn=?", (usn,), one=True)
    if not stu:
        return jsonify({"error": "Student not found."}), 404
    stu.pop("password", None)

    attendance  = query_db("SELECT * FROM attendance  WHERE student_usn=? ORDER BY date DESC", (usn,))
    att_pct     = 0
    if attendance:
        present = sum(1 for r in attendance if r["status"] == "Present")
        att_pct = round(present / len(attendance) * 100)

    return jsonify({
        "student":      stu,
        "internships":  query_db("SELECT * FROM internships WHERE student_usn=?", (usn,)),
        "attendance":   attendance,
        "attendancePct": att_pct,
        "tasks":        query_db("SELECT * FROM tasks        WHERE student_usn=? ORDER BY id DESC", (usn,)),
        "evaluations":  query_db("SELECT * FROM evaluations  WHERE student_usn=? ORDER BY id DESC", (usn,)),
        "updates":      query_db("SELECT * FROM updates       WHERE student_usn=? ORDER BY date DESC", (usn,)),
    })


# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# INTERNSHIP VIDEO UPLOAD & OPENROUTER AI EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def allowed_video(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_VIDEO_EXTENSIONS

@app.route("/api/student/videos", methods=["GET"])
@role_required("student")
def get_student_videos():
    usn = session.get("username")
    # Return both student's submissions and administrator benchmark/reference videos
    videos = query_db("""
        SELECT * FROM videos 
        WHERE student_usn = ? 
           OR student_usn IN ('ALL', 'ADMIN')
           OR uploader_role = 'administrator'
           OR video_type = 'Reference / Demo Benchmark'
        ORDER BY id DESC
    """, (usn,))
    return jsonify(videos)

@app.route("/api/student/videos", methods=["POST"])
@role_required("student")
def submit_student_video():
    usn = session.get("username")
    title = (request.form.get("title") or (request.json or {}).get("title") or "").strip()
    description = (request.form.get("description") or (request.json or {}).get("description") or "").strip()
    video_url = (request.form.get("video_url") or (request.json or {}).get("video_url") or "").strip()

    if not title:
        return jsonify({"error": "Video Title is required."}), 400

    # Handle file upload if present
    if "video_file" in request.files:
        file = request.files["video_file"]
        if file and file.filename != "":
            if not allowed_video(file.filename):
                return jsonify({"error": f"Invalid video format. Allowed formats: {', '.join(Config.ALLOWED_VIDEO_EXTENSIONS)}"}), 400
            ext = file.filename.rsplit(".", 1)[1].lower()
            saved_name = f"video_{usn}_{int(time.time())}_{secrets.token_hex(4)}.{ext}"
            file_path = os.path.join(Config.VIDEO_UPLOAD_FOLDER, saved_name)
            file.save(file_path)
            video_url = f"/uploads/videos/{saved_name}"

    if not video_url:
        return jsonify({"error": "Please provide a video file or a video presentation URL."}), 400

    # Call OpenRouter AI Evaluation using rerank model
    print(f"[*] Calling OpenRouter AI to evaluate internship video '{title}'...")
    ai_result = evaluate_internship_video_with_ai(title, description)
    ai_score = ai_result.get("ai_score", 75.0)
    ai_feedback = ai_result.get("ai_feedback", "Submitted for review.")

    vid_id = execute_db(
        """
        INSERT INTO videos (student_usn, title, description, video_url, status, ai_score, ai_feedback, uploader_role, video_type)
        VALUES (?, ?, ?, ?, 'Under Review', ?, ?, 'student', 'Submission')
        """,
        (usn, title, description, video_url, ai_score, ai_feedback)
    )

    log_audit(usn, "student", f"SUBMITTED_VIDEO_ID_{vid_id}")

    return jsonify({
        "success": True,
        "message": "Internship demo video submitted and evaluated by OpenRouter AI!",
        "video_id": vid_id,
        "ai_score": ai_score,
        "ai_feedback": ai_feedback,
        "engine": ai_result.get("engine", "OpenRouter")
    }), 201

@app.route("/uploads/videos/<filename>")
def serve_video_file(filename):
    return send_from_directory(Config.VIDEO_UPLOAD_FOLDER, secure_filename(filename))

@app.route("/api/faculty/videos", methods=["GET"])
@role_required("faculty")
def get_faculty_assigned_videos():
    fid = session.get("username")
    # Get videos from students assigned to this faculty member + admin reference videos
    videos = query_db("""
        SELECT v.*, s.name as student_name, s.course, s.semester, s.company as student_company
        FROM videos v
        LEFT JOIN internships i ON i.student_usn = v.student_usn
        LEFT JOIN students s ON s.usn = v.student_usn
        WHERE i.faculty_id = ? 
           OR v.student_usn IN ('ALL', 'ADMIN') 
           OR v.uploader_role = 'administrator'
        ORDER BY v.id DESC
    """, (fid,))
    return jsonify(videos)

@app.route("/api/faculty/videos/<int:vid>", methods=["PUT"])
@role_required("faculty")
def review_faculty_video(vid):
    fid = session.get("username")
    d = request.get_json(force=True)
    status = d.get("status", "Reviewed")
    faculty_feedback = (d.get("faculty_feedback") or "").strip()

    execute_db(
        "UPDATE videos SET status = ?, ai_feedback = COALESCE(ai_feedback, '') || ? WHERE id = ?",
        (status, f" | Faculty Remarks: {faculty_feedback}", vid)
    )
    log_audit(fid, "faculty", f"REVIEWED_VIDEO_ID_{vid}")
    return jsonify({"success": True, "message": "Video review saved successfully."})


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN INTERNSHIP VIDEO MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/admin/videos", methods=["GET"])
@role_required("administrator")
def get_admin_videos():
    videos = query_db("""
        SELECT v.*, s.name as student_name, s.course, s.semester, s.company as student_company
        FROM videos v
        LEFT JOIN students s ON s.usn = v.student_usn
        ORDER BY v.id DESC
    """)
    return jsonify(videos)

@app.route("/api/admin/videos", methods=["POST"])
@role_required("administrator")
def create_admin_video():
    admin_id = session.get("username")
    title = (request.form.get("title") or (request.json or {}).get("title") or "").strip()
    description = (request.form.get("description") or (request.json or {}).get("description") or "").strip()
    video_url = (request.form.get("video_url") or (request.json or {}).get("video_url") or "").strip()
    video_type = (request.form.get("video_type") or (request.json or {}).get("video_type") or "Reference / Demo Benchmark").strip()
    target_usn = (request.form.get("student_usn") or (request.json or {}).get("student_usn") or "ADMIN").strip()

    if not title:
        return jsonify({"error": "Video Title is required."}), 400

    if "video_file" in request.files:
        file = request.files["video_file"]
        if file and file.filename != "":
            if not allowed_video(file.filename):
                return jsonify({"error": f"Invalid video format. Allowed formats: {', '.join(Config.ALLOWED_VIDEO_EXTENSIONS)}"}), 400
            ext = file.filename.rsplit(".", 1)[1].lower()
            saved_name = f"ref_video_{int(time.time())}_{secrets.token_hex(4)}.{ext}"
            file_path = os.path.join(Config.VIDEO_UPLOAD_FOLDER, saved_name)
            file.save(file_path)
            video_url = f"/uploads/videos/{saved_name}"

    if not video_url:
        return jsonify({"error": "Please provide a video file or a video presentation URL."}), 400

    vid_id = execute_db("""
        INSERT INTO videos (student_usn, title, description, video_url, status, ai_score, ai_feedback, uploader_role, video_type)
        VALUES (?, ?, ?, ?, 'Approved', 100.0, 'Official Institutional Benchmark Demo Video', 'administrator', ?)
    """, (target_usn, title, description, video_url, video_type))

    log_audit(admin_id, "administrator", f"UPLOADED_BENCHMARK_VIDEO_ID_{vid_id}")
    return jsonify({"success": True, "message": "Reference/Benchmark video saved successfully.", "video_id": vid_id}), 201

@app.route("/api/admin/videos/<int:vid>", methods=["PUT"])
@role_required("administrator")
def update_admin_video(vid):
    admin_id = session.get("username")
    data = request.get_json(force=True)
    title = data.get("title")
    status = data.get("status", "Approved")
    ai_score = data.get("ai_score")
    ai_feedback = data.get("ai_feedback")

    curr = query_db("SELECT * FROM videos WHERE id = ?", (vid,), one=True)
    if not curr:
        return jsonify({"error": "Video not found."}), 404

    execute_db("""
        UPDATE videos 
        SET title = COALESCE(?, title),
            status = COALESCE(?, status),
            ai_score = COALESCE(?, ai_score),
            ai_feedback = COALESCE(?, ai_feedback)
        WHERE id = ?
    """, (title, status, ai_score, ai_feedback, vid))

    log_audit(admin_id, "administrator", f"UPDATED_VIDEO_ID_{vid}")
    return jsonify({"success": True, "message": "Video record updated successfully."})

@app.route("/api/admin/videos/<int:vid>", methods=["DELETE"])
@role_required("administrator")
def delete_admin_video(vid):
    admin_id = session.get("username")
    vid_row = query_db("SELECT * FROM videos WHERE id = ?", (vid,), one=True)
    if not vid_row:
        return jsonify({"error": "Video not found."}), 404

    v_url = vid_row.get("video_url", "")
    if v_url.startswith("/uploads/videos/"):
        fname = v_url.replace("/uploads/videos/", "").strip()
        local_path = os.path.join(Config.VIDEO_UPLOAD_FOLDER, fname)
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception as e:
                print(f"[WARN] Could not remove video file: {e}")

    execute_db("DELETE FROM videos WHERE id = ?", (vid,))
    log_audit(admin_id, "administrator", f"DELETED_VIDEO_ID_{vid}")
    return jsonify({"success": True, "message": "Video deleted successfully."})


# ─────────────────────────────────────────────────────────────────────────────
# QUIZZES, QUESTION ASSIGNMENT & OPENROUTER AI EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/quizzes", methods=["GET"])
@login_required
def list_quizzes():
    role = session.get("user_role") or session.get("role")
    usn = session.get("username")
    if role == "student":
        # Find student's assigned faculty
        internship = query_db("SELECT faculty_id FROM internships WHERE student_usn = ? ORDER BY id DESC LIMIT 1", (usn,), one=True)
        fac_id = internship["faculty_id"] if internship else ""
        rows = query_db("""
            SELECT q.*, 
                   qa.score as student_score, 
                   qa.total as student_total, 
                   qa.ai_relevance_score, 
                   qa.ai_feedback as student_feedback,
                   qa.completed_at as student_completed_at
            FROM quizzes q
            LEFT JOIN quiz_attempts qa ON qa.quiz_id = q.id AND qa.student_usn = ?
            WHERE q.assigned_to = 'ALL' 
               OR q.assigned_to = '' 
               OR q.assigned_to IS NULL
               OR q.assigned_to = ? 
               OR (q.faculty_id != '' AND q.faculty_id = ?)
            ORDER BY q.id DESC
        """, (usn, usn, fac_id))
    else:
        rows = query_db("""
            SELECT q.*, COUNT(qa.id) as attempt_count 
            FROM quizzes q 
            LEFT JOIN quiz_attempts qa ON qa.quiz_id = q.id 
            GROUP BY q.id 
            ORDER BY q.id DESC
        """)
    return jsonify(rows)

@app.route("/api/quizzes/<int:qid>", methods=["GET"])
@login_required
def get_quiz_details(qid):
    row = query_db("SELECT * FROM quizzes WHERE id = ?", (qid,), one=True)
    if not row:
        return jsonify({"error": "Quiz not found."}), 404
    import json
    try:
        row["questions"] = json.loads(row["questions_json"])
    except Exception:
        row["questions"] = []
    return jsonify(row)

@app.route("/api/quizzes/<int:qid>/submit", methods=["POST"])
@role_required("student")
def submit_quiz_attempt(qid):
    usn = session.get("username")
    d = request.get_json(force=True)
    answers = d.get("answers", {})

    quiz = query_db("SELECT * FROM quizzes WHERE id = ?", (qid,), one=True)
    if not quiz:
        return jsonify({"error": "Quiz not found."}), 404

    import json
    questions = json.loads(quiz["questions_json"])
    eval_result = evaluate_quiz_with_ai(answers, questions)

    attempt_id = execute_db(
        """
        INSERT INTO quiz_attempts (quiz_id, student_usn, score, total, answers_json, ai_relevance_score, ai_feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qid, usn, eval_result["score"], eval_result["total"],
            json.dumps(answers), eval_result["percentage"], eval_result["feedback"]
        )
    )

    log_audit(usn, "student", f"COMPLETED_QUIZ_ID_{qid}_SCORE_{eval_result['score']}/{eval_result['total']}")

    return jsonify({
        "success": True,
        "score": eval_result["score"],
        "total": eval_result["total"],
        "percentage": eval_result["percentage"],
        "feedback": eval_result["feedback"]
    })

@app.route("/api/faculty/quizzes", methods=["GET"])
@role_required("faculty")
def get_faculty_quizzes():
    fid = session.get("username")
    quizzes = query_db("""
        SELECT q.*, 
               COUNT(qa.id) as attempt_count,
               AVG(qa.score) as avg_score
        FROM quizzes q
        LEFT JOIN quiz_attempts qa ON qa.quiz_id = q.id
        WHERE q.faculty_id = ? OR q.created_by = ?
        GROUP BY q.id
        ORDER BY q.id DESC
    """, (fid, fid))
    import json
    for q in quizzes:
        try:
            q["questions"] = json.loads(q["questions_json"])
        except Exception:
            q["questions"] = []
    return jsonify(quizzes)

@app.route("/api/faculty/quizzes", methods=["POST"])
@role_required("faculty")
def create_faculty_quiz():
    fid = session.get("username")
    faculty_row = query_db("SELECT name FROM faculty WHERE faculty_id = ? OR login_id = ?", (fid, fid), one=True)
    fname = faculty_row["name"] if faculty_row else fid

    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    topic = (d.get("topic") or "").strip()
    assigned_to = (d.get("assigned_to") or "ALL").strip()
    due_date = (d.get("due_date") or "").strip()
    questions = d.get("questions", [])

    if not title or not topic:
        return jsonify({"error": "Title and Topic are required."}), 400
    if not questions or not isinstance(questions, list):
        return jsonify({"error": "At least one question is required."}), 400

    import json
    qid = execute_db("""
        INSERT INTO quizzes (title, topic, questions_json, created_by, faculty_id, assigned_to, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, topic, json.dumps(questions), fname, fid, assigned_to, due_date))

    log_audit(fid, "faculty", f"ASSIGNED_QUIZ_ID_{qid}_TO_{assigned_to}")
    return jsonify({"success": True, "message": "Quiz & questions successfully assigned!", "quiz_id": qid}), 201

@app.route("/api/faculty/quizzes/<int:qid>", methods=["DELETE"])
@role_required("faculty", "administrator")
def delete_faculty_quiz(qid):
    uid = session.get("username")
    role = session.get("role")
    q = query_db("SELECT * FROM quizzes WHERE id = ?", (qid,), one=True)
    if not q:
        return jsonify({"error": "Quiz not found."}), 404
    if role == "faculty" and q["faculty_id"] != uid and q["created_by"] != uid:
        return jsonify({"error": "Unauthorized to delete this quiz."}), 403

    execute_db("DELETE FROM quiz_attempts WHERE quiz_id = ?", (qid,))
    execute_db("DELETE FROM quizzes WHERE id = ?", (qid,))
    log_audit(uid, role, f"DELETED_QUIZ_ID_{qid}")
    return jsonify({"success": True, "message": "Quiz deleted successfully."})

@app.route("/api/student/quiz-attempts", methods=["GET"])
@role_required("student")
def get_student_quiz_attempts():
    usn = session.get("username")
    attempts = query_db("""
        SELECT qa.*, q.title as quiz_title, q.topic as quiz_topic
        FROM quiz_attempts qa
        JOIN quizzes q ON q.id = qa.quiz_id
        WHERE qa.student_usn = ?
        ORDER BY qa.id DESC
    """, (usn,))
    return jsonify(attempts)

@app.route("/api/faculty/quiz-attempts", methods=["GET"])
@role_required("faculty")
def get_faculty_quiz_attempts():
    fid = session.get("username")
    attempts = query_db("""
        SELECT qa.*, q.title as quiz_title, s.name as student_name, s.course, s.semester
        FROM quiz_attempts qa
        JOIN quizzes q ON q.id = qa.quiz_id
        JOIN internships i ON i.student_usn = qa.student_usn
        JOIN students s ON s.usn = qa.student_usn
        WHERE i.faculty_id = ?
        ORDER BY qa.id DESC
    """, (fid,))
    return jsonify(attempts)


# ─────────────────────────────────────────────────────────────────────────────
# ASSESSMENT SCHEMES & MARKS MANAGEMENT (5-COMPONENT BENCHMARK, 100 MARKS)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_grade(percentage):
    if percentage >= 90: return "A+"
    elif percentage >= 80: return "A"
    elif percentage >= 70: return "B+"
    elif percentage >= 60: return "B"
    elif percentage >= 50: return "C"
    elif percentage >= 40: return "P"
    return "F"

@app.route("/api/assessment-schemes", methods=["GET"])
@login_required
def get_assessment_schemes():
    schemes = query_db("SELECT * FROM assessment_schemes WHERE is_active = 1 ORDER BY id DESC")
    for s in schemes:
        s["components"] = query_db(
            "SELECT * FROM assessment_components WHERE scheme_id = ? ORDER BY id ASC",
            (s["id"],)
        )
    return jsonify(schemes)

@app.route("/api/assessment-schemes", methods=["POST"])
@role_required("administrator")
def create_assessment_scheme():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    academic_year = (d.get("academic_year") or "2026").strip()
    total_max = int(d.get("total_max_marks") or 100)
    components = d.get("components", [])

    if not name:
        return jsonify({"error": "Scheme name is required."}), 400

    scheme_id = execute_db("""
        INSERT INTO assessment_schemes (name, academic_year, total_max_marks, is_active)
        VALUES (?, ?, ?, 1)
    """, (name, academic_year, total_max))

    for c in components:
        execute_db("""
            INSERT INTO assessment_components (scheme_id, component_name, max_marks, weight_percentage, description)
            VALUES (?, ?, ?, ?, ?)
        """, (scheme_id, c.get("component_name"), c.get("max_marks", 20), c.get("weight_percentage", 20.0), c.get("description", "")))

    log_audit(session.get("username"), "administrator", f"CREATED_ASSESSMENT_SCHEME_{scheme_id}")
    return jsonify({"success": True, "scheme_id": scheme_id}), 201

@app.route("/api/marks", methods=["GET"])
@login_required
def get_marks():
    role = session.get("user_role") or session.get("role")
    user = session.get("username")
    target_usn = request.args.get("student_usn")

    components = query_db("""
        SELECT c.* 
        FROM assessment_components c
        JOIN assessment_schemes s ON s.id = c.scheme_id
        WHERE s.is_active = 1
        ORDER BY c.id ASC
    """)
    if not components:
        components = query_db("SELECT * FROM assessment_components ORDER BY id ASC")

    if role == "student":
        students = query_db("""
            SELECT s.usn, s.name, s.course, s.semester, s.company,
                   i.id as internship_id, i.faculty_id, f.name as faculty_name
            FROM students s
            LEFT JOIN internships i ON i.student_usn = s.usn
            LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
            WHERE s.usn = ?
        """, (user,))
    elif role == "faculty":
        students = query_db("""
            SELECT s.usn, s.name, s.course, s.semester, s.company,
                   i.id as internship_id, i.faculty_id, f.name as faculty_name
            FROM students s
            JOIN internships i ON i.student_usn = s.usn
            LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
            WHERE i.faculty_id = ?
            ORDER BY s.name ASC
        """, (user,))
    else:  # administrator
        if target_usn:
            students = query_db("""
                SELECT s.usn, s.name, s.course, s.semester, s.company,
                       i.id as internship_id, i.faculty_id, f.name as faculty_name
                FROM students s
                LEFT JOIN internships i ON i.student_usn = s.usn
                LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
                WHERE s.usn = ?
            """, (target_usn,))
        else:
            students = query_db("""
                SELECT s.usn, s.name, s.course, s.semester, s.company,
                       i.id as internship_id, i.faculty_id, f.name as faculty_name
                FROM students s
                LEFT JOIN internships i ON i.student_usn = s.usn
                LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
                ORDER BY s.name ASC
            """)

    result_students = []
    for stu in students:
        usn = stu["usn"]
        marks_rows = query_db("SELECT * FROM student_marks WHERE student_usn = ?", (usn,))
        marks_map = {m["component_id"]: m for m in marks_rows}

        comp_details = []
        total_obtained = 0.0
        total_max = 0.0
        has_any_mark = False

        for c in components:
            cid = c["id"]
            if cid in marks_map:
                m = marks_map[cid]
                has_any_mark = True
                obtained = float(m["marks_obtained"])
                c_max = float(m["max_marks"])
                total_obtained += obtained
                total_max += c_max
                comp_details.append({
                    "component_id": cid,
                    "component_name": c["component_name"],
                    "marks_obtained": obtained,
                    "max_marks": c_max,
                    "percentage": m["percentage"],
                    "grade": m["grade"],
                    "remarks": m["remarks"],
                    "status": m["status"]
                })
            else:
                c_max = float(c["max_marks"])
                total_max += c_max
                comp_details.append({
                    "component_id": cid,
                    "component_name": c["component_name"],
                    "marks_obtained": None,
                    "max_marks": c_max,
                    "percentage": 0.0,
                    "grade": "-",
                    "remarks": "",
                    "status": "Pending"
                })

        overall_pct = round((total_obtained / total_max * 100), 2) if total_max > 0 and has_any_mark else 0.0
        overall_grade = calculate_grade(overall_pct) if has_any_mark else "-"
        eval_status = "Approved" if any(m.get("status") == "Approved" for m in marks_rows) else ("Published" if any(m.get("status") == "Published" for m in marks_rows) else ("Draft" if has_any_mark else "Not Evaluated"))

        result_students.append({
            "student_usn": usn,
            "student_name": stu["name"],
            "course": stu["course"],
            "semester": stu["semester"],
            "company": stu["company"],
            "internship_id": stu["internship_id"],
            "faculty_id": stu["faculty_id"],
            "faculty_name": stu["faculty_name"] or "-",
            "components": comp_details,
            "total_marks_obtained": round(total_obtained, 2),
            "total_max_marks": round(total_max, 2),
            "overall_percentage": overall_pct,
            "overall_grade": overall_grade,
            "status": eval_status
        })

    return jsonify({
        "components": components,
        "students": result_students
    })

@app.route("/api/marks/student/<usn>", methods=["GET"])
@login_required
def get_student_marks_breakdown(usn):
    role = session.get("user_role") or session.get("role")
    curr_user = session.get("username")

    if role == "student" and curr_user != usn:
        return jsonify({"error": "Forbidden: You may only view your own marks."}), 403

    student = query_db("""
        SELECT s.*, i.id as internship_id, i.faculty_id, i.company as internship_company, f.name as faculty_name
        FROM students s
        LEFT JOIN internships i ON i.student_usn = s.usn
        LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
        WHERE s.usn = ?
    """, (usn,), one=True)
    if not student:
        return jsonify({"error": "Student record not found."}), 404

    components = query_db("""
        SELECT c.* 
        FROM assessment_components c
        JOIN assessment_schemes s ON s.id = c.scheme_id
        WHERE s.is_active = 1
        ORDER BY c.id ASC
    """)
    if not components:
        components = query_db("SELECT * FROM assessment_components ORDER BY id ASC")

    marks_rows = query_db("SELECT * FROM student_marks WHERE student_usn = ?", (usn,))
    marks_map = {m["component_id"]: m for m in marks_rows}

    comp_breakdown = []
    total_obtained = 0.0
    total_max = 0.0
    has_marks = False

    for c in components:
        cid = c["id"]
        c_max = float(c["max_marks"])
        total_max += c_max
        if cid in marks_map:
            m = marks_map[cid]
            has_marks = True
            obtained = float(m["marks_obtained"])
            total_obtained += obtained
            comp_breakdown.append({
                "component_id": cid,
                "component_name": c["component_name"],
                "description": c.get("description", ""),
                "max_marks": c_max,
                "marks_obtained": obtained,
                "percentage": m["percentage"],
                "grade": m["grade"],
                "remarks": m["remarks"] or "-",
                "status": m["status"],
                "evaluated_on": m.get("evaluated_on", "")
            })
        else:
            comp_breakdown.append({
                "component_id": cid,
                "component_name": c["component_name"],
                "description": c.get("description", ""),
                "max_marks": c_max,
                "marks_obtained": 0.0,
                "percentage": 0.0,
                "grade": "-",
                "remarks": "Evaluation Pending",
                "status": "Pending",
                "evaluated_on": "-"
            })

    pct = round((total_obtained / total_max * 100), 2) if total_max > 0 and has_marks else 0.0
    grade = calculate_grade(pct) if has_marks else "-"
    status = "Published" if any(m.get("status") == "Published" for m in marks_rows) else ("Draft" if has_marks else "Pending")

    return jsonify({
        "student": {
            "usn": student["usn"],
            "name": student["name"],
            "course": student["course"],
            "semester": student["semester"],
            "company": student.get("internship_company") or student.get("company") or "N/A",
            "faculty_id": student.get("faculty_id") or "-",
            "faculty_name": student.get("faculty_name") or "-"
        },
        "components": comp_breakdown,
        "total_obtained": round(total_obtained, 2),
        "total_max": round(total_max, 2),
        "percentage": pct,
        "grade": grade,
        "status": status
    })

@app.route("/api/marks", methods=["POST"])
@role_required("faculty", "administrator")
def save_student_marks():
    evaluator = session.get("username")
    role = session.get("user_role") or session.get("role")
    d = request.get_json(force=True)

    student_usn = (d.get("student_usn") or "").strip()
    internship_id = d.get("internship_id")
    status = d.get("status", "Published")
    marks_list = d.get("marks")

    if not student_usn:
        return jsonify({"error": "student_usn is required."}), 400

    if not internship_id:
        internship = query_db("SELECT id, faculty_id FROM internships WHERE student_usn = ? ORDER BY id DESC LIMIT 1", (student_usn,), one=True)
        if internship:
            internship_id = internship["id"]
            faculty_id = internship["faculty_id"]
        else:
            internship_id = 0
            faculty_id = evaluator
    else:
        internship = query_db("SELECT faculty_id FROM internships WHERE id = ?", (internship_id,), one=True)
        faculty_id = internship["faculty_id"] if internship else evaluator

    if not marks_list:
        cid = d.get("component_id")
        m_val = d.get("marks_obtained")
        if cid is not None and m_val is not None:
            marks_list = [{"component_id": int(cid), "marks_obtained": float(m_val), "remarks": d.get("remarks", "")}]
        else:
            return jsonify({"error": "Provide marks or component_id and marks_obtained."}), 400

    comp_defs = {c["id"]: c for c in query_db("SELECT * FROM assessment_components")}

    saved_count = 0
    for item in marks_list:
        cid = int(item["component_id"])
        c_def = comp_defs.get(cid)
        if not c_def:
            continue

        max_m = float(c_def["max_marks"])
        obtained = float(item["marks_obtained"])
        if obtained < 0:
            obtained = 0.0
        if obtained > max_m:
            return jsonify({"error": f"Marks for '{c_def['component_name']}' ({obtained}) cannot exceed maximum allowed ({max_m})."}), 400

        pct = round((obtained / max_m) * 100, 2)
        grd = calculate_grade(pct)
        remarks = (item.get("remarks") or "").strip()

        execute_db("""
            INSERT INTO student_marks 
            (student_usn, internship_id, faculty_id, component_id, marks_obtained, max_marks, percentage, grade, remarks, status, evaluated_on, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
            ON CONFLICT(student_usn, internship_id, component_id) DO UPDATE SET
                marks_obtained = excluded.marks_obtained,
                max_marks = excluded.max_marks,
                percentage = excluded.percentage,
                grade = excluded.grade,
                remarks = excluded.remarks,
                status = excluded.status,
                updated_by = excluded.updated_by,
                updated_at = datetime('now')
        """, (student_usn, internship_id, faculty_id, cid, obtained, max_m, pct, grd, remarks, status, evaluator))
        saved_count += 1

    log_audit(evaluator, role, f"ENTERED_MARKS_FOR_{student_usn}_COUNT_{saved_count}")
    return jsonify({
        "success": True,
        "message": f"Successfully recorded {saved_count} benchmark assessment mark(s) for student {student_usn}."
    })


@app.route("/api/marks/approve/<student_usn>", methods=["POST"])
@role_required("administrator")
def approve_student_marks(student_usn):
    admin_user = session.get("username")
    stu = query_db("SELECT * FROM students WHERE usn = ?", (student_usn,), one=True)
    if not stu:
        return jsonify({"error": "Student not found."}), 404

    existing = query_db("SELECT * FROM student_marks WHERE student_usn = ?", (student_usn,))
    if existing:
        execute_db("""
            UPDATE student_marks 
            SET status = 'Approved', updated_by = ?, updated_at = datetime('now')
            WHERE student_usn = ?
        """, (admin_user, student_usn))
    else:
        internship = query_db("SELECT id, faculty_id FROM internships WHERE student_usn = ? ORDER BY id DESC LIMIT 1", (student_usn,), one=True)
        iid = internship["id"] if internship else 0
        fid = internship["faculty_id"] if internship else admin_user
        components = query_db("SELECT * FROM assessment_components ORDER BY id ASC")
        for c in components:
            cid = c["id"]
            max_m = float(c["max_marks"])
            execute_db("""
                INSERT INTO student_marks 
                (student_usn, internship_id, faculty_id, component_id, marks_obtained, max_marks, percentage, grade, remarks, status, evaluated_on, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Approved', datetime('now'), ?, datetime('now'))
                ON CONFLICT(student_usn, internship_id, component_id) DO UPDATE SET
                    status = 'Approved',
                    updated_by = excluded.updated_by,
                    updated_at = datetime('now')
            """, (student_usn, iid, fid, cid, max_m, max_m, 100.0, 'A+', 'Approved by Administrator', admin_user))

    log_audit(admin_user, "administrator", f"APPROVED_MARKS_FOR_{student_usn}")
    return jsonify({"success": True, "message": f"Benchmark marks for {student_usn} approved successfully!"})


@app.route("/api/marks/export-csv", methods=["GET"])
@role_required("faculty", "administrator")
def export_marks_csv():
    role = session.get("user_role") or session.get("role")
    user = session.get("username")

    components = query_db("""
        SELECT c.* 
        FROM assessment_components c
        JOIN assessment_schemes s ON s.id = c.scheme_id
        WHERE s.is_active = 1
        ORDER BY c.id ASC
    """)
    if not components:
        components = query_db("SELECT * FROM assessment_components ORDER BY id ASC")

    if role == "faculty":
        students = query_db("""
            SELECT s.usn, s.name, s.course, s.semester, s.company,
                   i.id as internship_id, i.faculty_id, f.name as faculty_name
            FROM students s
            JOIN internships i ON i.student_usn = s.usn
            LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
            WHERE i.faculty_id = ?
            ORDER BY s.name ASC
        """, (user,))
    else:
        students = query_db("""
            SELECT s.usn, s.name, s.course, s.semester, s.company,
                   i.id as internship_id, i.faculty_id, f.name as faculty_name
            FROM students s
            LEFT JOIN internships i ON i.student_usn = s.usn
            LEFT JOIN faculty f ON f.faculty_id = i.faculty_id
            ORDER BY s.name ASC
        """)

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["Student USN", "Student Name", "Course", "Semester", "Company", "Faculty Guide"]
    for c in components:
        header.append(f"{c['component_name']} ({int(c['max_marks'])})")
    header.extend(["Total Marks (100)", "Percentage (%)", "Grade", "Status"])
    writer.writerow(header)

    for stu in students:
        usn = stu["usn"]
        marks_rows = query_db("SELECT * FROM student_marks WHERE student_usn = ?", (usn,))
        marks_map = {m["component_id"]: m for m in marks_rows}

        total_obtained = 0.0
        total_max = 0.0
        row = [
            stu["usn"],
            stu["name"],
            stu["course"] or "BCA",
            stu["semester"] or "Final",
            stu["company"] or "N/A",
            stu["faculty_name"] or "-"
        ]

        has_any = False
        for c in components:
            cid = c["id"]
            c_max = float(c["max_marks"])
            total_max += c_max
            if cid in marks_map:
                has_any = True
                val = float(marks_map[cid]["marks_obtained"])
                total_obtained += val
                row.append(f"{val:.1f}")
            else:
                row.append("N/A")

        pct = round((total_obtained / total_max * 100), 2) if total_max > 0 and has_any else 0.0
        grd = calculate_grade(pct) if has_any else "-"
        st = "Approved" if any(m.get("status") == "Approved" for m in marks_rows) else ("Published" if any(m.get("status") == "Published" for m in marks_rows) else ("Draft" if has_any else "Pending"))

        row.extend([f"{total_obtained:.1f}", f"{pct:.2f}%", grd, st])
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=internship_marks_benchmark_report.csv",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

@app.route("/api/admin/audit-logs", methods=["GET"])
@role_required("administrator")
def get_audit_logs():
    limit = int(request.args.get("limit", 50))
    logs = query_db("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    return jsonify(logs)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("⚠  Database not found. Running init_db.py automatically...")
        from init_db import init_db
        init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
