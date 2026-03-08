import sqlite3

DB_NAME = "ngo.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


# ---------------------------
# USERS
# ---------------------------

def create_user(username, password, role):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password, role)
    )

    conn.commit()
    conn.close()


def get_user(username):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    )

    user = cur.fetchone()
    conn.close()

    return user


# ---------------------------
# TRANSACTIONS
# ---------------------------

def add_transaction(date, description, amount, type, program):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO transactions(date, description, amount, type, program)
        VALUES (?, ?, ?, ?, ?)
        """,
        (date, description, amount, type, program)
    )

    conn.commit()
    conn.close()


def get_transactions():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions ORDER BY date DESC")

    rows = cur.fetchall()
    conn.close()

    return rows


# ---------------------------
# DASHBOARD DATA
# ---------------------------

def total_donations():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM transactions WHERE type='donation'")
    total = cur.fetchone()[0] or 0

    conn.close()
    return total


def total_expenses():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM transactions WHERE type='expense'")
    total = cur.fetchone()[0] or 0

    conn.close()
    return total