import sqlite3

conn = sqlite3.connect("ngo.db")
c = conn.cursor()

# Add new accounting columns safely
try:
    c.execute("ALTER TABLE transactions ADD COLUMN pv_number TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN account TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN account_code TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN sub_account TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN sub_account_code TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN project TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE transactions ADD COLUMN month TEXT")
except:
    pass

conn.commit()
conn.close()

print("Database upgraded successfully")
