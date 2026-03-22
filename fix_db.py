import sqlite3
from pathlib import Path

DB_FILE = Path("database.db")
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

# Check existing columns in transactions table
c.execute("PRAGMA table_info(transactions)")
existing_columns = [row[1] for row in c.fetchall()]

# Required columns
required_columns = {
    "date": "TEXT",
    "pv_number": "TEXT",
    "description": "TEXT",
    "type": "TEXT",
    "amount": "REAL",
    "month": "INTEGER",
    "account": "TEXT",
    "account_code": "TEXT",
    "sub_account": "TEXT",
    "sub_account_code": "TEXT"
}

# Add any missing columns
for col, col_type in required_columns.items():
    if col not in existing_columns:
        c.execute(f"ALTER TABLE transactions ADD COLUMN {col} {col_type}")
        print(f"Added missing column: {col}")

# Optional: check chart_of_accounts table
c.execute("PRAGMA table_info(chart_of_accounts)")
coa_columns = [row[1] for row in c.fetchall()]
if not coa_columns:
    c.execute("""CREATE TABLE IF NOT EXISTS chart_of_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT,
                    account_type TEXT,
                    account_code TEXT,
                    description TEXT
                )""")
    print("Created chart_of_accounts table")

# Optional: check users table
c.execute("PRAGMA table_info(users)")
user_columns = [row[1] for row in c.fetchall()]
if not user_columns:
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT
                )""")
    print("Created users table")

conn.commit()
conn.close()
print("Database schema check complete. All required columns exist.")