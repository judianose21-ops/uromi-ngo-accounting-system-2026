import sqlite3


def get_connection():
    return sqlite3.connect("ngo.db")


def initialize():

    conn = get_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT
    )
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO users (id, username, password, role)
    VALUES (1, 'admin', 'admin123', 'admin')
    """)

    # DONORS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT
    )
    """)

    # PROJECTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       project_name TEXT,
       donor TEXT,
       budget REAL
    )
    """)

    # CHART OF ACCOUNTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chart_of_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT,
        account_type TEXT,
        description TEXT
    )
    """)

    # TRANSACTIONS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        debit_account TEXT,
        credit_account TEXT,
        amount REAL,
        project_id TEXT
    )
    """)

    conn.commit()
    conn.close()