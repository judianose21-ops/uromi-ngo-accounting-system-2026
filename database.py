import sqlite3
from contextlib import contextmanager

DB_PATH = "ngo.db"

# Context manager to automatically close connection
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access
    try:
        yield conn
    finally:
        conn.close()

# Optional: function to initialize tables if they don't exist
def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        # donors table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
        """)
        # accounts table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
        """)
        # transactions table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            account_name TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT
        )
        """)
        # projects table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            budget REAL DEFAULT 0
        )
        """)
        conn.commit()