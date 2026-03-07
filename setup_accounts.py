import sqlite3

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")

accounts = [
    ("Cash",),
    ("Bank",),
    ("Donations",),
    ("Expenses",)
]

cur.executemany("INSERT INTO accounts (name) VALUES (?)", accounts)

conn.commit()
conn.close()

print("Accounts created successfully")