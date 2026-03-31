import sqlite3
from contextlib import contextmanager
from passlib.context import CryptContext

DB_PATH = "ngo.db"

# =====================================================
# PASSWORD HASHING
# =====================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)


# =====================================================
# DATABASE CONNECTION
# =====================================================
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# =====================================================
# SAFE COLUMN MIGRATION
# =====================================================
def add_column_if_not_exists(cursor, table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]

    if column not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


# =====================================================
# INITIALIZE DATABASE
# =====================================================
def init_db():
    with get_db() as conn:
        cur = conn.cursor()

        # ---------------- USERS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
        """)

        # ---------------- DONORS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
        """)

        # ---------------- ACCOUNTS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            balance REAL DEFAULT 0
        )
        """)

        # ---------------- PROJECTS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sector TEXT,
            budget REAL DEFAULT 0
        )
        """)

        # ---------------- BUDGETS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            account TEXT,
            amount REAL,
            description TEXT
        )
        """)

        # ---------------- TRANSACTIONS ----------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            pv_number TEXT,
            description TEXT,
            type TEXT,
            amount REAL,
            account TEXT,
            sub_account TEXT
        )
        """)

        # ✅ AUTO MIGRATION (SAFE UPDATES)
        add_column_if_not_exists(cur, "transactions", "gross_amount", "REAL DEFAULT 0")
        add_column_if_not_exists(cur, "transactions", "tax", "REAL DEFAULT 0")
        add_column_if_not_exists(cur, "transactions", "net_amount", "REAL DEFAULT 0")
        add_column_if_not_exists(cur, "transactions", "payment_method", "TEXT")
        add_column_if_not_exists(cur, "transactions", "reference", "TEXT")
        add_column_if_not_exists(cur, "transactions", "created_at",
                                "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")


# =====================================================
# SEED DEFAULT USERS (RUNS SAFELY ONCE)
# =====================================================
def seed_users():
    with get_db() as conn:
        cursor = conn.cursor()

        users = [
            ("admin", hash_password("admin123"), "admin"),
            ("finance", hash_password("finance123"), "finance"),
            ("audit", hash_password("audit123"), "audit"),
        ]

        for user in users:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role)
                VALUES (?, ?, ?)
            """, user)

        conn.commit()

    print("✅ Default users seeded")

# =====================================================
# TRANSACTION FUNCTIONS
# =====================================================
def add_transaction(
    date,
    pv_number,
    description,
    type,
    amount,
    account,
    sub_account,
    gross_amount=0,
    tax=0,
    net_amount=0,
    payment_method=None,
    reference=None
):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO transactions (
            date, pv_number, description, type,
            amount, account, sub_account,
            gross_amount, tax, net_amount,
            payment_method, reference
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, pv_number, description, type,
            amount, account, sub_account,
            gross_amount, tax, net_amount,
            payment_method, reference
        ))

        conn.commit()


def get_transactions():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM transactions
        ORDER BY date DESC
        """)

        return [dict(row) for row in cursor.fetchall()]


def get_transaction(transaction_id):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM transactions WHERE id=?",
            (transaction_id,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None


def update_transaction(
    id,
    date,
    pv_number,
    description,
    type,
    amount,
    account,
    sub_account,
    gross_amount,
    tax,
    net_amount,
    payment_method,
    reference
):
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE transactions SET
            date=?, pv_number=?, description=?, type=?,
            amount=?, account=?, sub_account=?,
            gross_amount=?, tax=?, net_amount=?,
            payment_method=?, reference=?
        WHERE id=?
        """, (
            date, pv_number, description, type,
            amount, account, sub_account,
            gross_amount, tax, net_amount,
            payment_method, reference, id
        ))

        conn.commit()


def delete_transaction(transaction_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM transactions WHERE id=?",
            (transaction_id,)
        )
        conn.commit()


# =====================================================
# BUDGET FUNCTIONS
# =====================================================
def get_budgets():
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM budgets ORDER BY id DESC"
        ).fetchall()


def update_budget(id, project, account, amount, description):
    with get_db() as conn:
        conn.execute("""
        UPDATE budgets
        SET project=?, account=?, amount=?, description=?
        WHERE id=?
        """, (project, account, amount, description, id))
        conn.commit()


def delete_budget(budget_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM budgets WHERE id=?",
            (budget_id,)
        )
        conn.commit()