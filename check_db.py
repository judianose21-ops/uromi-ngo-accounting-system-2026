import sqlite3

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(transactions)")
columns = cur.fetchall()

for col in columns:
    print(col)

conn.close()