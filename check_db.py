import sqlite3

conn = sqlite3.connect('ngo.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)

# Check if there are any audit-related columns in transactions table
cursor.execute('PRAGMA table_info(transactions)')
columns = cursor.fetchall()
print('\nTransactions table columns:')
for col in columns:
    print(f'  {col[1]}: {col[2]}')

conn.close()