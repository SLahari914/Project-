"""
init_db.py – Run once to create all tables and seed initial accounts.
Usage:  python init_db.py
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "internship.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Admin ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id  TEXT UNIQUE,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            role      TEXT DEFAULT 'administrator',
            is_active INTEGER DEFAULT 1
        )
    """)

    # ── Faculty ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id   TEXT UNIQUE,
            faculty_id TEXT UNIQUE NOT NULL,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            department TEXT DEFAULT 'Computer Applications',
            phone      TEXT DEFAULT '',
            password   TEXT NOT NULL,
            role       TEXT DEFAULT 'faculty',
            is_active  INTEGER DEFAULT 1
        )
    """)

    # ── Students ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id  TEXT UNIQUE,
            usn       TEXT UNIQUE NOT NULL,
            name      TEXT NOT NULL,
            email     TEXT NOT NULL,
            course    TEXT DEFAULT 'BCA',
            semester  TEXT DEFAULT '1st',
            phone     TEXT DEFAULT '',
            company   TEXT DEFAULT '',
            status    TEXT DEFAULT 'Not Started',
            password  TEXT NOT NULL,
            role      TEXT DEFAULT 'student',
            is_active INTEGER DEFAULT 1
        )
    """)

    # ── Internships ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS internships (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn TEXT NOT NULL,
            company     TEXT NOT NULL,
            title       TEXT NOT NULL,
            faculty_id  TEXT NOT NULL,
            start_date  TEXT DEFAULT '',
            end_date    TEXT DEFAULT '',
            status      TEXT DEFAULT 'Not Started'
        )
    """)

    # ── Attendance ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn TEXT NOT NULL,
            faculty_id  TEXT NOT NULL,
            date        TEXT NOT NULL,
            status      TEXT DEFAULT 'Present',
            remarks     TEXT DEFAULT ''
        )
    """)

    # ── Tasks ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn     TEXT NOT NULL,
            title           TEXT NOT NULL,
            description     TEXT NOT NULL,
            submitted_on    TEXT DEFAULT '',
            faculty_remarks TEXT DEFAULT '',
            status          TEXT DEFAULT 'Pending'
        )
    """)

    # ── Evaluations ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn      TEXT NOT NULL,
            faculty_id       TEXT NOT NULL,
            technical_skills INTEGER DEFAULT 0,
            communication    INTEGER DEFAULT 0,
            punctuality      INTEGER DEFAULT 0,
            problem_solving  INTEGER DEFAULT 0,
            overall_score    INTEGER DEFAULT 0,
            remarks          TEXT DEFAULT '',
            evaluated_on     TEXT DEFAULT '',
            status           TEXT DEFAULT 'Approved'
        )
    """)

    # ── Daily / Weekly Updates ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn   TEXT NOT NULL,
            date          TEXT NOT NULL,
            description   TEXT NOT NULL,
            work_done     TEXT DEFAULT '',
            challenges    TEXT DEFAULT '',
            submitted_on  TEXT DEFAULT '',
            document_path TEXT DEFAULT '',
            document_name TEXT DEFAULT '',
            status        TEXT DEFAULT 'Pending',
            staff_remarks TEXT DEFAULT '',
            approved_by   TEXT DEFAULT '',
            approved_at   TEXT DEFAULT ''
        )
    """)

    # ── Progress Sheets ────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS progress_sheets (
            student_usn  TEXT PRIMARY KEY,
            sheet_data   TEXT NOT NULL,
            updated_at   TEXT DEFAULT ''
        )
    """)

    # ── Videos ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn   TEXT NOT NULL,
            title         TEXT NOT NULL,
            description   TEXT DEFAULT '',
            video_url     TEXT NOT NULL,
            submitted_on  TEXT DEFAULT CURRENT_TIMESTAMP,
            status        TEXT DEFAULT 'Under Review',
            ai_score      REAL DEFAULT 0.0,
            ai_feedback   TEXT DEFAULT '',
            uploader_role TEXT DEFAULT 'student',
            video_type    TEXT DEFAULT 'Submission'
        )
    """)

    # ── Quizzes & Attempts ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL,
            topic          TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_by     TEXT DEFAULT 'System',
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            faculty_id     TEXT DEFAULT '',
            assigned_to    TEXT DEFAULT 'ALL',
            due_date       TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id            INTEGER NOT NULL,
            student_usn        TEXT NOT NULL,
            score              INTEGER DEFAULT 0,
            total              INTEGER DEFAULT 0,
            answers_json       TEXT DEFAULT '',
            ai_relevance_score REAL DEFAULT 0.0,
            ai_feedback        TEXT DEFAULT '',
            completed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    """)

    # ── Audit Logs ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            action     TEXT NOT NULL,
            ip_address TEXT DEFAULT '',
            timestamp  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Assessment Schemes & Marks Management ─────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS assessment_schemes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            academic_year   TEXT DEFAULT '2026',
            total_max_marks INTEGER DEFAULT 100,
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS assessment_components (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id         INTEGER NOT NULL,
            component_name    TEXT NOT NULL,
            max_marks         INTEGER NOT NULL,
            weight_percentage REAL DEFAULT 0.0,
            description       TEXT DEFAULT '',
            FOREIGN KEY (scheme_id) REFERENCES assessment_schemes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS student_marks (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn    TEXT NOT NULL,
            internship_id  INTEGER NOT NULL,
            faculty_id     TEXT NOT NULL,
            component_id   INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            max_marks      REAL NOT NULL,
            percentage     REAL NOT NULL,
            grade          TEXT DEFAULT '',
            remarks        TEXT DEFAULT '',
            status         TEXT DEFAULT 'Published',
            evaluated_on   TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by     TEXT DEFAULT '',
            updated_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (component_id) REFERENCES assessment_components(id),
            UNIQUE (student_usn, internship_id, component_id)
        )
    """)

    conn.commit()

    # ── Seed Admin ─────────────────────────────────────────────────────
    existing = c.execute(
        "SELECT id, login_id FROM admin WHERE username = ?", ("admin",)
    ).fetchone()

    if not existing:
        c.execute(
            "INSERT INTO admin (username, password, login_id, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("Admin@123"), "ADM26A1042", "administrator", 1)
        )
        conn.commit()
        print("[OK] Admin account created -> username: admin | login_id: ADM26A1042 | password: Admin@123")
    else:
        print("[INFO] Admin account already exists - skipping seed.")

    # ── Seed default Assessment Scheme ─────────────────────────────────
    existing_scheme = c.execute("SELECT id FROM assessment_schemes LIMIT 1").fetchone()
    if not existing_scheme:
        c.execute("""
            INSERT INTO assessment_schemes (name, academic_year, total_max_marks, is_active)
            VALUES (?, ?, ?, ?)
        """, ("Internship Assessment Scheme 2026", "2026", 100, 1))
        scheme_id = c.lastrowid

        default_components = [
            ("Internal Assessment", 20, 20.0, "Periodic technical milestone review"),
            ("Assignment",          10, 10.0, "Deliverables, documentation & codebase submission"),
            ("Attendance",          10, 10.0, "Verified internship attendance and punctuality"),
            ("Project Work",        20, 20.0, "Implementation, code quality, and technical problem-solving"),
            ("Final Evaluation",    40, 40.0, "Final project viva, presentation, and supervisor appraisal")
        ]
        for comp_name, max_m, weight, desc in default_components:
            c.execute("""
                INSERT INTO assessment_components (scheme_id, component_name, max_marks, weight_percentage, description)
                VALUES (?, ?, ?, ?, ?)
            """, (scheme_id, comp_name, max_m, weight, desc))
        conn.commit()
        print("[OK] Seeded default Assessment Scheme (Total: 100 marks) with 5 components.")

    conn.close()
    print("[OK] Database initialised successfully at:", DB_PATH)


if __name__ == "__main__":
    init_db()
