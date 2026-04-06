import sqlite3

conn = sqlite3.connect('ngo.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== BUDGETS DATA ===")
cursor.execute('SELECT * FROM budgets LIMIT 3')
for row in cursor.fetchall():
    print(dict(row))

print("\n=== TRANSACTIONS DATA (SAMPLE) ===")
cursor.execute('SELECT id, date, project, main_account_code, amount FROM transactions LIMIT 3')
for row in cursor.fetchall():
    print(dict(row))

print("\n=== COUNT VERIFICATION ===")
cursor.execute('SELECT COUNT(*) as count FROM budgets')
print(f"Total budgets: {cursor.fetchone()['count']}")

cursor.execute('SELECT COUNT(*) as count FROM transactions')
print(f"Total transactions: {cursor.fetchone()['count']}")

conn.close()
