-- schema_mysql.sql
-- MySQL Schema for Upgrade Existing Internship Management System
-- Common Role-Based Login with ADM25, STF25, STU25 prefixes

CREATE DATABASE IF NOT EXISTS internship_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE internship_system;

-- 1. Admin Table
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login_id VARCHAR(30) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'administrator',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Faculty / Guide Table
CREATE TABLE IF NOT EXISTS faculty (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login_id VARCHAR(30) UNIQUE NOT NULL,
    faculty_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    department VARCHAR(100) DEFAULT 'Computer Applications',
    phone VARCHAR(25) DEFAULT '',
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'faculty',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. Students Table
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login_id VARCHAR(30) UNIQUE NOT NULL,
    usn VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    course VARCHAR(50) DEFAULT 'BCA',
    semester VARCHAR(20) DEFAULT '1st',
    phone VARCHAR(25) DEFAULT '',
    company VARCHAR(100) DEFAULT '',
    status VARCHAR(50) DEFAULT 'Not Started',
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'student',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 4. Internships Table
CREATE TABLE IF NOT EXISTS internships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    company VARCHAR(100) NOT NULL,
    title VARCHAR(150) NOT NULL,
    faculty_id VARCHAR(50) NOT NULL,
    start_date VARCHAR(20) DEFAULT '',
    end_date VARCHAR(20) DEFAULT '',
    status VARCHAR(50) DEFAULT 'Not Started',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_student (student_usn),
    INDEX idx_faculty (faculty_id)
) ENGINE=InnoDB;

-- 5. Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    faculty_id VARCHAR(50) NOT NULL,
    date VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    remarks TEXT,
    UNIQUE KEY uk_student_date (student_usn, date)
) ENGINE=InnoDB;

-- 6. Tasks Table
CREATE TABLE IF NOT EXISTS tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    submitted_on VARCHAR(30) DEFAULT '',
    faculty_remarks TEXT,
    status VARCHAR(50) DEFAULT 'Pending'
) ENGINE=InnoDB;

-- 7. Evaluations Table
CREATE TABLE IF NOT EXISTS evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    faculty_id VARCHAR(50) NOT NULL,
    technical_skills INT DEFAULT 0,
    communication INT DEFAULT 0,
    punctuality INT DEFAULT 0,
    problem_solving INT DEFAULT 0,
    overall_score INT DEFAULT 0,
    remarks TEXT,
    evaluated_on VARCHAR(30) DEFAULT ''
) ENGINE=InnoDB;

-- 8. Daily Updates Table
CREATE TABLE IF NOT EXISTS updates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    date VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    work_done TEXT,
    challenges TEXT,
    submitted_on VARCHAR(30) DEFAULT ''
) ENGINE=InnoDB;

-- 9. Internship Video Submissions & Reference Videos Table
CREATE TABLE IF NOT EXISTS videos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    video_url VARCHAR(255) NOT NULL,
    submitted_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'Under Review',
    ai_score FLOAT DEFAULT 0.0,
    ai_feedback TEXT,
    uploader_role VARCHAR(30) DEFAULT 'student',
    video_type VARCHAR(50) DEFAULT 'Submission',
    INDEX idx_video_stu (student_usn)
) ENGINE=InnoDB;

-- 10. Quizzes Table (OpenRouter AI Quiz Generation & Faculty Question Assignment)
CREATE TABLE IF NOT EXISTS quizzes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    topic VARCHAR(150) NOT NULL,
    questions_json LONGTEXT NOT NULL,
    created_by VARCHAR(50) DEFAULT 'Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    faculty_id VARCHAR(50) DEFAULT '',
    assigned_to VARCHAR(50) DEFAULT 'ALL',
    due_date VARCHAR(50) DEFAULT ''
) ENGINE=InnoDB;

-- 11. Quiz Attempts Table
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quiz_id INT NOT NULL,
    student_usn VARCHAR(50) NOT NULL,
    score INT DEFAULT 0,
    total INT DEFAULT 0,
    answers_json LONGTEXT,
    ai_relevance_score FLOAT DEFAULT 0.0,
    ai_feedback TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 12. Security Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    action VARCHAR(150) NOT NULL,
    ip_address VARCHAR(50) DEFAULT '',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 13. Assessment Schemes Table (Configurable Scheme & Maximum Marks)
CREATE TABLE IF NOT EXISTS assessment_schemes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    academic_year VARCHAR(20) DEFAULT '2026',
    total_max_marks INT DEFAULT 100,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 14. Assessment Components Table
CREATE TABLE IF NOT EXISTS assessment_components (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scheme_id INT NOT NULL,
    component_name VARCHAR(150) NOT NULL,
    max_marks INT NOT NULL,
    weight_percentage FLOAT DEFAULT 0.0,
    description TEXT,
    FOREIGN KEY (scheme_id) REFERENCES assessment_schemes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 15. Student Marks Table
CREATE TABLE IF NOT EXISTS student_marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_usn VARCHAR(50) NOT NULL,
    internship_id INT NOT NULL,
    faculty_id VARCHAR(50) NOT NULL,
    component_id INT NOT NULL,
    marks_obtained FLOAT NOT NULL,
    max_marks FLOAT NOT NULL,
    percentage FLOAT NOT NULL,
    grade VARCHAR(10) DEFAULT '',
    remarks TEXT,
    status VARCHAR(50) DEFAULT 'Published',
    evaluated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(50) DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (component_id) REFERENCES assessment_components(id) ON DELETE CASCADE,
    UNIQUE KEY uq_student_assessment (student_usn, internship_id, component_id),
    INDEX idx_marks_stu (student_usn),
    INDEX idx_marks_fac (faculty_id)
) ENGINE=InnoDB;
