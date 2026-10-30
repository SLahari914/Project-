"""
create_users.py – Secure account generator for Internship Management System
Supports MySQL and SQLite databases with standard role and year prefixes:
  - ADM26A: Administrator (e.g., ADM26A1042)
  - STF26T: Staff / Guide (e.g., STF26T1001)
  - STU26S: Student       (e.g., STU26S2045)
Supports configurable registration year (e.g. '26' for 2026, '27' for 2027).
Preserves all existing data.
"""

import os
import sys
import secrets
import string
import sqlite3
from werkzeug.security import generate_password_hash

# Try importing MySQL driver (PyMySQL or MySQLdb)
MYSQL_AVAILABLE = False
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    import MySQLdb
    MYSQL_AVAILABLE = True
except Exception:
    try:
        import MySQLdb
        MYSQL_AVAILABLE = True
    except Exception:
        MYSQL_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "internship.db")
REG_YEAR = os.environ.get("REGISTRATION_YEAR", "26")


def generate_login_id(role, year=None, cursor=None, is_mysql=False):
    """
    Format Rule:
    Admin:   ADM + YY + A + unique numeric suffix (e.g. ADM26A1042)
    Staff:   STF + YY + T + unique numeric suffix (e.g. STF26T1001)
    Student: STU + YY + S + unique numeric suffix (e.g. STU26S2045)
    """
    y = str(year or REG_YEAR).strip()
    if len(y) == 4:
        y = y[-2:]

    r = role.lower()
    if r in ["admin", "administrator"]:
        prefix = f"ADM{y}A"
        base_start = 1000
        table = "admin"
    elif r in ["staff", "faculty", "guide"]:
        prefix = f"STF{y}T"
        base_start = 1000
        table = "faculty"
    elif r in ["student"]:
        prefix = f"STU{y}S"
        base_start = 2000
        table = "students"
    else:
        prefix = f"USR{y}U"
        base_start = 1000
        table = "students"

    if cursor is not None:
        ph = "%s" if is_mysql else "?"
        # Check all tables to ensure global uniqueness
        existing_ids = set()
        for t in ["admin", "faculty", "students"]:
            try:
                cursor.execute(f"SELECT login_id FROM {t} WHERE login_id LIKE {ph}", (f"{prefix}%",))
                for row in cursor.fetchall():
                    if row[0]:
                        existing_ids.add(row[0])
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
    else:
        # Fallback random 4-digit
        num = secrets.randbelow(9000) + 1000
        return f"{prefix}{num}"


def get_connection():
    """
    Connect to MySQL if configured, otherwise connect to SQLite.
    Returns (conn, is_mysql).
    """
    use_mysql = os.environ.get("USE_MYSQL", "0") == "1"
    mysql_host = os.environ.get("MYSQL_HOST", "localhost")
    mysql_user = os.environ.get("MYSQL_USER", "root")
    mysql_pass = os.environ.get("MYSQL_PASSWORD", "1234")
    mysql_db   = os.environ.get("MYSQL_DB", "internship_system")

    if use_mysql and MYSQL_AVAILABLE:
        try:
            conn = MySQLdb.connect(
                host=mysql_host,
                user=mysql_user,
                passwd=mysql_pass,
                db=mysql_db
            )
            print("[INFO] Connected to MySQL database.")
            return conn, True
        except Exception as e:
            print(f"[WARN] MySQL connection failed ({e}), falling back to SQLite.")

    # Fallback to local SQLite database
    conn = sqlite3.connect(DB_PATH)
    print(f"[INFO] Connected to SQLite database: {DB_PATH}")
    return conn, False


def is_login_id_taken(cursor, table_name, login_id, is_mysql):
    ph = "%s" if is_mysql else "?"
    cursor.execute(f"SELECT id FROM {table_name} WHERE login_id = {ph}", (login_id,))
    return cursor.fetchone() is not None


def is_email_taken(cursor, table_name, email, is_mysql):
    ph = "%s" if is_mysql else "?"
    cursor.execute(f"SELECT id FROM {table_name} WHERE email = {ph}", (email,))
    return cursor.fetchone() is not None


def create_initial_users():
    conn, is_mysql = get_connection()
    cursor = conn.cursor()
    ph = "%s" if is_mysql else "?"

    # 1. Administrator Account
    cursor.execute("SELECT id, login_id FROM admin LIMIT 1")
    existing_admin = cursor.fetchone()
    if not existing_admin:
        admin_login_id = generate_login_id("administrator", REG_YEAR, cursor, is_mysql)
        admin_user = os.environ.get("INITIAL_ADMIN_USER", "admin")
        admin_pass = os.environ.get("INITIAL_ADMIN_PASS", "Admin@123")
        admin_hash = generate_password_hash(admin_pass)

        cursor.execute(
            f"""
            INSERT INTO admin (login_id, username, password, role, is_active)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (admin_login_id, admin_user, admin_hash, "administrator", 1)
        )
        print(f"[SUCCESS] Admin created: username='{admin_user}' | Login ID='{admin_login_id}'")
    else:
        print(f"[INFO] Admin account already exists (ID: {existing_admin[1] or 'existing'}). Preserving record.")

    # 2. Staff / Guide Account
    cursor.execute("SELECT id, login_id FROM faculty LIMIT 1")
    existing_fac = cursor.fetchone()
    if not existing_fac:
        guide_login_id = generate_login_id("faculty", REG_YEAR, cursor, is_mysql)
        guide_fid  = "FAC001"
        guide_name = "Prof. R. Sharma"
        guide_mail = "guide@internship.edu"
        guide_pass = os.environ.get("INITIAL_STAFF_PASS", "Guide@123")
        guide_hash = generate_password_hash(guide_pass)

        cursor.execute(
            f"""
            INSERT INTO faculty (login_id, faculty_id, name, email, department, phone, password, role, is_active)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (guide_login_id, guide_fid, guide_name, guide_mail, "Computer Applications", "9876543210", guide_hash, "faculty", 1)
        )
        print(f"[SUCCESS] Faculty created: Faculty ID='{guide_fid}' | Login ID='{guide_login_id}'")
    else:
        print(f"[INFO] Faculty account already exists (ID: {existing_fac[1] or 'existing'}). Preserving record.")

    # 3. Student Account
    cursor.execute("SELECT id, login_id FROM students LIMIT 1")
    existing_stu = cursor.fetchone()
    if not existing_stu:
        stu_login_id = generate_login_id("student", REG_YEAR, cursor, is_mysql)
        stu_usn  = "U18FU24S0001"
        stu_name = "Demo Student"
        stu_mail = "student@internship.edu"
        stu_pass = os.environ.get("INITIAL_STUDENT_PASS", "Student@123")
        stu_hash = generate_password_hash(stu_pass)

        cursor.execute(
            f"""
            INSERT INTO students (login_id, usn, name, email, course, semester, phone, company, status, password, role, is_active)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (stu_login_id, stu_usn, stu_name, stu_mail, "BCA", "6th", "9876543211", "Tech Corp", "Active", stu_hash, "student", 1)
        )
        print(f"[SUCCESS] Student created: USN='{stu_usn}' | Login ID='{stu_login_id}'")
    else:
        print(f"[INFO] Student account already exists (ID: {existing_stu[1] or 'existing'}). Preserving record.")

    conn.commit()
    cursor.close()
    conn.close()
    print("[OK] Account verification and creation completed securely.")


if __name__ == "__main__":
    create_initial_users()