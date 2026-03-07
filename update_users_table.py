import sqlite3

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

cur.execute("""
""")
cur.execute(
"SELECT password,role FROM users WHERE username=?",
(data.username,)
)

user = cur.fetchone()

if user and bcrypt.verify(data.password,user[0]):

    return {"status":"success","role":user[1]}
conn.commit()
conn.close()

print("Role column added")