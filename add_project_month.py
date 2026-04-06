import sqlite3

conn = sqlite3.connect('ngo.db')
cursor = conn.cursor()

# Add missing columns if they don't exist
columns_to_add = [
    ('project', 'TEXT'),
    ('month', 'INTEGER')
]

for col_name, col_type in columns_to_add:
    try:
        cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
        print(f"✓ Added column: {col_name}")
    except sqlite3.OperationalError as e:
        print(f"✗ {col_name}: {e}")

conn.commit()
conn.close()
print("\nDone!")
