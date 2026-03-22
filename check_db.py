import sqlite3

conn = sqlite3.connect("ngo.db")
c = conn.cursor()

# show tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", c.fetchall())

# show transactions structure
c.execute("PRAGMA table_info(transactions)")
print("Transactions Columns:")
for col in c.fetchall():
    print(col)

conn.close()
