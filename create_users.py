import sqlite3
from passlib.hash import bcrypt

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE,
password TEXT
)
""")

password = bcrypt.hash("admin123")

cur.execute("""
INSERT OR REPLACE INTO users (id, username, password)
VALUES (
    (SELECT id FROM users WHERE username='admin'),
    'admin',
    ?
)
""", (password,))

conn.commit()
conn.close()

print("Admin user ready")