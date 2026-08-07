import os

DB_PATH = os.environ.get("DB_PATH", "roster.db")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ACCOUNTS_FILE = os.environ.get("ACCOUNTS_FILE", "accounts.json")
