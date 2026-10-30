"""
migrate_db.py – Upgrades internship.db schema to add login_id, role, is_active,
video submissions, quiz tracking, and audit log tables.
Preserves all existing data.
"""

import sqlite3
import os
import secrets
import string

DB_PATH = os.path.join(os.path.dirname(__file__), "internship.db")

def generate_suffix(length=5):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("[*] Starting database migration...")

    # 1. Update 'admin' table
    admin_cols = [r[1] for r in c.execute("PRAGMA table_info(admin)").fetchall()]
    if "login_id" not in admin_cols:
        print("[+] Adding login_id to admin...")
        c.execute("ALTER TABLE admin ADD COLUMN login_id TEXT")
    if "role" not in admin_cols:
        print("[+] Adding role to admin...")
        c.execute("ALTER TABLE admin ADD COLUMN role TEXT DEFAULT 'administrator'")
    if "is_active" not in admin_cols:
        print("[+] Adding is_active to admin...")
        c.execute("ALTER TABLE admin ADD COLUMN is_active INTEGER DEFAULT 1")

    # Set default login_id for existing admin if missing
    c.execute("SELECT id, username, login_id FROM admin")
    admins = c.fetchall()
    for row in admins:
        aid, uname, lid = row
        if not lid:
            new_lid = "ADM25A1042"
            c.execute("UPDATE admin SET login_id = ?, role = 'administrator', is_active = 1 WHERE id = ?", (new_lid, aid))
            print(f"[*] Admin '{uname}' assigned Login ID: {new_lid}")

    # 2. Update 'faculty' table
    fac_cols = [r[1] for r in c.execute("PRAGMA table_info(faculty)").fetchall()]
    if "login_id" not in fac_cols:
        print("[+] Adding login_id to faculty...")
        c.execute("ALTER TABLE faculty ADD COLUMN login_id TEXT")
    if "role" not in fac_cols:
        print("[+] Adding role to faculty...")
        c.execute("ALTER TABLE faculty ADD COLUMN role TEXT DEFAULT 'faculty'")
    if "is_active" not in fac_cols:
        print("[+] Adding is_active to faculty...")
        c.execute("ALTER TABLE faculty ADD COLUMN is_active INTEGER DEFAULT 1")

    c.execute("SELECT id, faculty_id, login_id FROM faculty")
    facs = c.fetchall()
    for row in facs:
        fid_num, fac_id, lid = row
        if not lid:
            new_lid = "STF25T1001"
            c.execute("UPDATE faculty SET login_id = ?, role = 'faculty', is_active = 1 WHERE id = ?", (new_lid, fid_num))
            print(f"[*] Faculty '{fac_id}' assigned Login ID: {new_lid}")

    # 3. Update 'students' table
    stu_cols = [r[1] for r in c.execute("PRAGMA table_info(students)").fetchall()]
    if "login_id" not in stu_cols:
        print("[+] Adding login_id to students...")
        c.execute("ALTER TABLE students ADD COLUMN login_id TEXT")
    if "role" not in stu_cols:
        print("[+] Adding role to students...")
        c.execute("ALTER TABLE students ADD COLUMN role TEXT DEFAULT 'student'")
    if "is_active" not in stu_cols:
        print("[+] Adding is_active to students...")
        c.execute("ALTER TABLE students ADD COLUMN is_active INTEGER DEFAULT 1")

    c.execute("SELECT id, usn, login_id FROM students")
    students = c.fetchall()
    for row in students:
        sid, usn, lid = row
        if not lid:
            new_lid = "STU25S2045"
            c.execute("UPDATE students SET login_id = ?, role = 'student', is_active = 1 WHERE id = ?", (new_lid, sid))
            print(f"[*] Student '{usn}' assigned Login ID: {new_lid}")

    # 4. Create 'videos' table for internship video upload
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            video_url TEXT NOT NULL,
            submitted_on TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Under Review',
            ai_score REAL DEFAULT 0.0,
            ai_feedback TEXT DEFAULT '',
            uploader_role TEXT DEFAULT 'student',
            video_type TEXT DEFAULT 'Submission'
        )
    """)
    vid_cols = [x[1] for x in c.execute("PRAGMA table_info(videos)").fetchall()]
    if 'uploader_role' not in vid_cols:
        c.execute("ALTER TABLE videos ADD COLUMN uploader_role TEXT DEFAULT 'student'")
    if 'video_type' not in vid_cols:
        c.execute("ALTER TABLE videos ADD COLUMN video_type TEXT DEFAULT 'Submission'")

    # 5. Create 'quizzes' and 'quiz_attempts' table for OpenRouter quiz tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_by TEXT DEFAULT 'System',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            faculty_id TEXT DEFAULT '',
            assigned_to TEXT DEFAULT 'ALL',
            due_date TEXT DEFAULT ''
        )
    """)
    quiz_cols = [x[1] for x in c.execute("PRAGMA table_info(quizzes)").fetchall()]
    if 'faculty_id' not in quiz_cols:
        c.execute("ALTER TABLE quizzes ADD COLUMN faculty_id TEXT DEFAULT ''")
    if 'assigned_to' not in quiz_cols:
        c.execute("ALTER TABLE quizzes ADD COLUMN assigned_to TEXT DEFAULT 'ALL'")
    if 'due_date' not in quiz_cols:
        c.execute("ALTER TABLE quizzes ADD COLUMN due_date TEXT DEFAULT ''")

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_usn TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            answers_json TEXT DEFAULT '',
            ai_relevance_score REAL DEFAULT 0.0,
            ai_feedback TEXT DEFAULT '',
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    """)

    # 6. Create 'audit_logs' table for security audit logging
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT DEFAULT '',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 7. Create Marks Management & Allocation tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS assessment_schemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            academic_year TEXT DEFAULT '2026',
            total_max_marks INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS assessment_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            max_marks INTEGER NOT NULL,
            weight_percentage REAL DEFAULT 0.0,
            description TEXT DEFAULT '',
            FOREIGN KEY (scheme_id) REFERENCES assessment_schemes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS student_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_usn TEXT NOT NULL,
            internship_id INTEGER NOT NULL,
            faculty_id TEXT NOT NULL,
            component_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            max_marks REAL NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT DEFAULT '',
            remarks TEXT DEFAULT '',
            status TEXT DEFAULT 'Published',
            evaluated_on TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (component_id) REFERENCES assessment_components(id),
            UNIQUE (student_usn, internship_id, component_id)
        )
    """)

    # Seed default assessment scheme if none exists
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
        print("[+] Seeded default Assessment Scheme (Total: 100 marks) with 5 components.")

    # Seed default internship quiz if none exists
    existing_quiz = c.execute("SELECT id FROM quizzes LIMIT 1").fetchone()
    if not existing_quiz:
        import json
        sample_questions = [
            {
                "id": 1,
                "question": "What is the primary role of Flask application routing in a web system?",
                "options": [
                    "A) Mapping URL endpoints to Python view functions",
                    "B) Storing data in persistent disk storage",
                    "C) Compiling CSS styles into JavaScript",
                    "D) Managing local network hardware adapters"
                ],
                "answer": "A",
                "explanation": "Flask routes map specific incoming HTTP request URLs to python controller functions."
            },
            {
                "id": 2,
                "question": "Which HTTP status code signifies successful user authentication in a REST API?",
                "options": ["A) 401 Unauthorized", "B) 403 Forbidden", "C) 200 OK", "D) 302 Found"],
                "answer": "C",
                "explanation": "200 OK is standard for successful JSON response."
            },
            {
                "id": 3,
                "question": "Why must passwords always be hashed with salts (e.g. Werkzeug scrypt/pbkdf2) before storage?",
                "options": [
                    "A) To decrease network bandwidth",
                    "B) To prevent credential recovery even if the database is exposed",
                    "C) To make SQL queries run faster",
                    "D) To satisfy browser cookie size restrictions"
                ],
                "answer": "B",
                "explanation": "Cryptographic one-way hashing with unique salts protects user credentials against rainbow tables and database breaches."
            }
        ]
        c.execute("""
            INSERT INTO quizzes (title, topic, questions_json, created_by)
            VALUES (?, ?, ?, ?)
        """, (
            "Internship Technical Assessment 2026",
            "Web Development, Flask Architecture & System Security",
            json.dumps(sample_questions),
            "Admin"
        ))
        print("[+] Seeded default Internship Technical Quiz.")

    conn.commit()
    conn.close()
    print("[OK] Database migration completed successfully!")

if __name__ == "__main__":
    migrate()
