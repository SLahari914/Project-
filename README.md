# 🎓 AI-Powered Internship Management System

An enterprise-grade, full-stack **Flask & SQLite/MySQL** web application designed to monitor student internship progress, administer continuous assessment benchmarks, host AI-evaluated project presentation videos, and manage faculty-assigned technical assessments.

---

## 🌟 Key Highlights & Features

### 1. 🛡️ Institutional Prefix-Based Authentication
* **Role Identification by Prefix:**
  * **Administrator:** `ADM26` (e.g., `ADM26A1042`)
  * **Faculty / Guide:** `STF26` (e.g., `STF26T1001`)
  * **Student:** `STU26` (e.g., `STU26S2045`)
* **Security & Session Hardening:**
  * Werkzeug `scrypt` password hashing with fallback recovery defaults.
  * Cookie protection (`HttpOnly`, `SameSite=Lax`, permanent session lifetime).
  * In-memory brute-force rate limiter (`HTTP 429 Too Many Requests` after 5 failed login attempts).
  * Real-time security audit logging (`audit_logs` table) recording user ID, IP address, timestamp, and actions.

---

### 2. 📊 5-Component Continuous Assessment Benchmark (100 Marks Total)
Implements an institutional quality benchmark scheme with strict boundary checks, automatic percentage and letter-grade computation (`A+`, `A`, `B+`, `B`, `C`, `P`, `F`), and real-time status management:

| Component Name | Max Marks | Weightage | Description |
| :--- | :---: | :---: | :--- |
| **1. Internal Assessment** | **20** | 20% | Periodic technical milestone and architecture reviews |
| **2. Assignment** | **10** | 10% | Deliverables, documentation, and repository submission |
| **3. Attendance** | **10** | 10% | Verified punctuality and internship attendance records |
| **4. Project Work** | **20** | 20% | Core software engineering, code quality, and implementation |
| **5. Final Evaluation** | **40** | 40% | Final viva presentation, defense, and supervisor appraisal |
| **TOTAL BENCHMARK** | **100** | **100%** | Comprehensive cumulative academic assessment |

* **Faculty & Admin Marks Manager (`manage-marks.html`):**
  * Interactive live-score calculator (updates total, percentage, and grade in real time as numbers are typed).
  * Boundary validation (rejects any entry exceeding the component's maximum).
  * Save as `Draft` or `Published`.
  * **1-Click CSV Export** (`/api/marks/export-csv`) to generate official grading sheets.
* **Student Benchmark Report Card (`student-marks.html`):**
  * Visual progress bars for each of the 5 benchmark components.
  * Evaluator feedback, status badges, and print-ready summary format.

---

### 3. 📹 Video Presentation & Benchmark Reference Management
* **Admin Reference & Demo Management:**
  * Administrators can upload institutional benchmark demo videos (`.mp4`, `.webm`) or link external presentation URLs.
  * Preview/play videos directly in the browser and manage all submissions.
* **Student Video Demo Submissions:**
  * Students submit internship demo videos or presentation URLs.
  * Automatically evaluated by **OpenRouter AI** (`nvidia/llama-nemotron-rerank-vl-1b-v2:free`) to assess technical relevance and generate feedback.
  * Institutional benchmark reference videos are visible to all students for guidance.

---

### 4. 📝 Guide/Faculty Question Allocation & OpenRouter AI Evaluation
* **Faculty Question Authoring:**
  * Guides can create custom question sets with multiple-choice options (`A`, `B`, `C`, `D`) and explanations.
  * Allocate question sets directly to **All Assigned Students** or to a **Specific Student by USN**.
* **Student Interactive Quizzes & AI Evaluation:**
  * Students select from question sets allocated specifically by their guide.
  * Answers are evaluated with automated AI feedback, percentage scores, and recorded in `quiz_attempts`.
  * Faculty dashboard displays real-time student attempt logs and score distributions.

---

### 5. 💼 Internship Lifecycle Management
* **Internship CRUD:** Track company allocations, faculty supervisors, and dates.
* **Attendance System:** Daily status logging (`Present`, `Absent`, `Late`) with percentage calculation.
* **Task Submissions:** Milestone tasks with student description, code deliverables, and faculty remarks.
* **Daily Updates:** Daily work logs, challenges faced, and supervisor comments.

---

## 🏗️ Technology Stack

* **Backend:** Python 3.10+, Flask 3.0+
* **Database:** SQLite 3 (WAL mode enabled for high-concurrency read/write transactions; MySQL schema compatible via `schema_mysql.sql`)
* **AI Evaluation Engine:** OpenRouter API (`nvidia/llama-nemotron-rerank-vl-1b-v2:free` with deterministic heuristic fallbacks)
* **Frontend:** Vanilla HTML5, CSS3, JavaScript (ES6+), Bootstrap 5

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10 or higher installed
* Git

### 2. Installation
```bash
# Clone or navigate to the project directory
cd "AI PROJECT"

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Review `config.py` to configure your settings or set environment variables:
```python
SECRET_KEY = "your-secure-secret-key"
OPENROUTER_API_KEY = "your-openrouter-api-key"   # Optional: Heuristic fallback is active if omitted
REGISTRATION_YEAR = "26"                        # Current 2-digit academic year
```

### 4. Initialize Database & Seed Accounts
```bash
# Run database initialization (creates tables & seeds default 100-mark assessment scheme)
python init_db.py

# (Optional) Run user generator to create accounts with current academic year prefixes
python create_users.py
```

### 5. Start the Application Server
```bash
python run.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Default Credentials

| Role | Username / USN | Institutional Login ID | Default Password | Dashboard URL |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `ADM26A1042` | `Admin@123` | `/admin/dashboard` |
| **Faculty / Guide** | `AGCMS01` | `STF26T1001` | `Guide@123` | `/faculty/dashboard` |
| **Student** | `U18FU24S0083` | `STU26S2045` | `Student@123` | `/student/dashboard` |

*(Note: Users can also log in using either their Username/USN or their auto-generated Login ID).*

---

## 📡 API Reference Overview

### 🔐 Authentication & Session
* `POST /api/login` - Authenticate using username or Login ID with role detection
* `GET /api/me` - Get current session details
* `GET /api/logout` - Clear user session
* `POST /api/change-password` - Update account password
* `GET /api/admin/audit-logs` - Retrieve security audit records (Admin only)

### 📊 Benchmark Marks Management
* `GET /api/assessment-schemes` - List active continuous assessment schemes and components
* `GET /api/marks` - Retrieve student marks (filtered by role and cohort)
* `POST /api/marks` - Enter or update component marks (Faculty & Admin)
* `GET /api/marks/student/<usn>` - Get complete marks breakdown for a specific student
* `GET /api/marks/export-csv` - Export marks to a downloadable `.csv` file

### 📹 Video Management
* `GET /api/admin/videos` - Retrieve all videos in the system (Admin only)
* `POST /api/admin/videos` - Upload institutional benchmark demo video
* `PUT /api/admin/videos/<id>` - Update video review status, feedback, or score
* `DELETE /api/admin/videos/<id>` - Delete video record and local storage file
* `GET /api/student/videos` - Get student submissions and institutional benchmark references
* `POST /api/student/videos` - Submit demo video for OpenRouter AI evaluation
* `GET /api/faculty/videos` - View videos submitted by assigned students

### 📝 Question Allocation & AI Quizzes
* `GET /api/quizzes` - List available quizzes allotted to the logged-in student
* `GET /api/quizzes/<id>` - Fetch questions for a specific quiz
* `POST /api/quizzes/<id>/submit` - Submit answers and trigger AI grading
* `GET /api/faculty/quizzes` - View quizzes created by the logged-in guide
* `POST /api/faculty/quizzes` - Create and assign a new question set to students
* `DELETE /api/faculty/quizzes/<id>` - Delete an allocated quiz set
* `GET /api/faculty/quiz-attempts` - View student attempts and AI relevance scores

---

## 🧪 Automated Testing

The codebase includes comprehensive integration test suites verifying all security, marks management, video delivery, and quiz evaluation workflows:

```bash
# Run core authentication, prefix routing, and OpenRouter AI test suite (11 tests)
python test_upgrade.py

# Run benchmark marks, video management, and question assignment test suite (18 tests)
python test_new_features.py
```

**Total Test Coverage:** 29 integration tests passing at 100%.

---

## 📁 Project Directory Structure

```text
├── run.py                     # Main Flask application and REST API controllers
├── config.py                  # System configuration, security settings, upload folders
├── openrouter_service.py      # OpenRouter AI video rerank & quiz evaluation engine
├── init_db.py                 # SQLite schema initialization and default seed data
├── migrate_db.py              # Safe migration script for database upgrades
├── schema_mysql.sql           # Production MySQL DDL schema definitions
├── create_users.py            # Academic year prefix user generator script
├── requirements.txt           # Python dependencies
│
├── login.html                 # Unified multi-role login interface
├── admin-dashboard.html       # Administrator portal & video/audit controls
├── faculty-dashboard.html     # Faculty guide portal & question authoring
├── student-dashboard.html     # Student portal, video submission & AI quizzes
├── manage-marks.html          # Faculty & Admin 5-component marks management interface
├── student-marks.html         # Student benchmark report card & performance breakdown
│
├── manage-students.html       # Student roster management
├── manage-faculty.html        # Faculty roster management
├── manage-internships.html    # Internship assignment & company allocation
├── faculty-attendance.html    # Faculty attendance management
├── faculty-evaluations.html   # Faculty periodic evaluations
├── faculty-students.html      # Faculty assigned students list
├── faculty-updates.html       # Daily update review
├── student-attendance.html    # Student attendance view
├── student-evaluations.html   # Student evaluation view
├── student-internship.html    # Student internship details
├── student-reports.html       # Comprehensive internship reports
├── student-tasks.html         # Student task submission portal
├── student-updates.html       # Daily log submission
│
├── uploads/videos/            # Uploaded student and benchmark reference video files
└── README.md                  # Project documentation
```

---

## 📄 License
This project is proprietary and maintained for academic internship monitoring and continuous evaluation benchmarks.
