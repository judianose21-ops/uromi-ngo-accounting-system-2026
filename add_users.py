#!/usr/bin/env python3
"""
Add Finance and Audit users to the system.
Usage: python add_users.py
"""

import sqlite3
from passlib.hash import bcrypt

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

# Create users table if it doesn't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    is_active INTEGER DEFAULT 1
)
""")

# Migrate email column if needed
cur.execute("PRAGMA table_info(users)")
columns = {row[1] for row in cur.fetchall()}
if "email" not in columns:
    try:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
        print("→ Added email column to users table")
    except Exception as e:
        print(f"⚠ Could not add email column: {e}")

conn.commit()

# Define users to add/update
users = [
    {
        "username": "finance",
        "password": "Finance@2024",
        "role": "finance",
        "email": "finance@uromi.org"
    },
    {
        "username": "audit",
        "password": "Audit@2024",
        "role": "audit",
        "email": "audit@uromi.org"
    }
]

print("Adding/Updating users...")
for user in users:
    hashed_pwd = bcrypt.hash(user["password"])
    
    try:
        # Check if user exists
        cur.execute("SELECT id FROM users WHERE username = ?", (user["username"],))
        existing = cur.fetchone()
        
        if existing:
            # Update existing user
            cur.execute("""
            UPDATE users SET password = ?, role = ?, email = ?, is_active = 1
            WHERE username = ?
            """, (hashed_pwd, user["role"], user["email"], user["username"]))
            print(f"✓ {user['role'].upper()}: {user['username']} / {user['password']} (updated)")
        else:
            # Insert new user
            cur.execute("""
            INSERT INTO users (username, password, role, email, is_active)
            VALUES (?, ?, ?, ?, 1)
            """, (user["username"], hashed_pwd, user["role"], user["email"]))
            print(f"✓ {user['role'].upper()}: {user['username']} / {user['password']} (created)")
    except Exception as e:
        print(f"✗ {user['role'].upper()}: Error - {e}")

conn.commit()

# Display all users
print("\n" + "="*60)
print("All users in database:")
print("="*60)
try:
    cur.execute("SELECT id, username, role, email, is_active FROM users ORDER BY role")
    for row in cur.fetchall():
        status = "✓ ACTIVE" if row[4] == 1 else "✗ INACTIVE"
        email_display = row[3] if row[3] else "—"
        print(f"ID {row[0]}: {row[1]:12} | Role: {row[2]:10} | Email: {email_display:25} | {status}")
except Exception as e:
    print(f"Could not display all users: {e}")

conn.close()
print("="*60)
print("✓ Users setup complete!")

