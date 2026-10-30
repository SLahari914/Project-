"""
config.py – Configuration Settings for Internship Management System
Supports environment variables with secure defaults.
"""

import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    # Security Secrets
    SECRET_KEY = os.environ.get("SECRET_KEY", "internship_sys_secure_secret_2026_x89a!")
    
    # Session Security
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # OpenRouter API Configuration
    OPENROUTER_API_KEY = os.environ.get(
        "OPENROUTER_API_KEY"
    )
    OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"
    OPENROUTER_RERANK_MODEL = "nvidia/llama-nemotron-rerank-vl-1b-v2:free"
    OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
    OPENROUTER_CHAT_MODEL = os.environ.get("OPENROUTER_CHAT_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

    # Uploads Configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    VIDEO_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")
    DOCUMENTS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "documents")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB max file size
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg", "mov", "m4v"}
    ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "txt", "rtf"}

    # Database Configuration
    DB_PATH = os.path.join(BASE_DIR, "internship.db")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")
    MYSQL_DB = os.environ.get("MYSQL_DB", "internship_system")
    USE_MYSQL = os.environ.get("USE_MYSQL", "0") == "1"

    # Rate Limiting Settings
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 300  # 5 minutes

    # Registration Year Configuration
    # Two-digit year prefix (e.g., '26' for 2026, '27' for 2027)
    REGISTRATION_YEAR = os.environ.get("REGISTRATION_YEAR", "26")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
