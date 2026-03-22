import sqlite3
from contextlib import contextmanager

DB_PATH = "ngo.db"

# ==============================
# DATABASE CONNECTION
# ==============================

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ==============================
# INITIALIZE DATABASE
# ==============================

def init_db():
    with get_db() as conn:
        cur = conn.cursor()

        # Donors
        cur.execute("""
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
        """)

        # Accounts
        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
        """)

        # Projects
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            budget REAL DEFAULT 0
        )
        """)

        # Transactions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            pv_number TEXT,
            description TEXT,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            account TEXT,
            sub_account TEXT
        )
        """)

        conn.commit()


# ==============================
# ADD TRANSACTION
# ==============================

def add_transaction(date, pv_number, description, type, amount, account, sub_account):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO transactions
        (date, pv_number, description, type, amount, account, sub_account)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            date,
            pv_number,
            description,
            type,
            amount,
            account,
            sub_account
        ))

        conn.commit()


# ==============================
# GET ALL TRANSACTIONS
# ==============================

def get_transactions():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT
            id,
            date,
            pv_number,
            description,
            type,
            amount,
            account,
            sub_account
        FROM transactions
        ORDER BY date DESC
        """)

        rows = cursor.fetchall()

        transactions = []

        for row in rows:
            transactions.append({
                "id": row["id"],
                "date": row["date"],
                "pv_number": row["pv_number"],
                "description": row["description"],
                "type": row["type"],
                "amount": row["amount"],
                "account": row["account"],
                "sub_account": row["sub_account"]
            })

        return transactions


# ==============================
# GET SINGLE TRANSACTION
# ==============================

def get_transaction(transaction_id):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT
            id,
            date,
            pv_number,
            description,
            type,
            amount,
            account,
            sub_account
        FROM transactions
        WHERE id = ?
        """, (transaction_id,))

        row = cursor.fetchone()

        if row:
            return {
                "id": row["id"],
                "date": row["date"],
                "pv_number": row["pv_number"],
                "description": row["description"],
                "type": row["type"],
                "amount": row["amount"],
                "account": row["account"],
                "sub_account": row["sub_account"]
            }

        return None


# ==============================
# DELETE TRANSACTION
# ==============================

def delete_transaction(transaction_id):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM transactions WHERE id = ?",
            (transaction_id,)
        )

        conn.commit()


# ==============================
# UPDATE TRANSACTION
# ==============================

def update_transaction(id, date, pv_number, description, type, amount, account, sub_account):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE transactions
        SET
            date = ?,
            pv_number = ?,
            description = ?,
            type = ?,
            amount = ?,
            account = ?,
            sub_account = ?
        WHERE id = ?
        """, (
            date,
            pv_number,
            description,
            type,
            amount,
            account,
            sub_account,
            id
        ))

        conn.commit()
# ==============================
# GET BUDGET ITEMS
# ==============================

def get_budgets():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM budgets ORDER BY id DESC")
        return cursor.fetchall()


# ==============================
# DELETE BUDGET
# ==============================

def delete_budget(budget_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM budgets WHERE id=?",
            (budget_id,)
        )
        conn.commit()


# ==============================
# UPDATE BUDGET
# ==============================

def update_budget(id, project, account, amount, description):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE budgets
        SET
            project=?,
            account=?,
            amount=?,
            description=?
        WHERE id=?
        """, (
            project,
            account,
            amount,
            description,
            id
        ))

        conn.commit()