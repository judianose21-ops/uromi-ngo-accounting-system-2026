from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
from pathlib import Path
from typing import List, Optional
from passlib.context import CryptContext
import secrets
import sys
import os
import socket
import threading
import logging
import webbrowser

if getattr(sys, 'frozen', False):
    sys.stdout = open(os.devnull, 'w', encoding='utf-8', errors='ignore')
    sys.stderr = open(os.devnull, 'w', encoding='utf-8', errors='ignore')
    sys.stdin = open(os.devnull, 'r', encoding='utf-8', errors='ignore')

import uvicorn
from datetime import datetime, timedelta

app = FastAPI(title="CARE Initiative")

# ─── Password Hashing Setup ────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Password Management Utilities ───────────────────────────────────
def hash_password(password: str) -> str:
    """Hash a password using bcrypt via passlib."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns: (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Password is strong"


def generate_reset_token() -> str:
    """Generate a secure reset token."""
    return secrets.token_urlsafe(32)
def init_database_tables():
    with get_db() as conn:
        # Vendors table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                tin             TEXT,
                phone           TEXT,
                email           TEXT,
                address         TEXT,
                account_number  TEXT,
                bank_name       TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now')),
                is_active       INTEGER DEFAULT 1
            )
        """)
        
        # Optional index for faster name searches
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vendors_name 
            ON vendors(name)
        """)
        
        conn.commit()
    print("Database tables initialized (vendors table ready)")

# Run it once when the app starts
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (runs before the server accepts requests)
    print("Initializing/Verifying database...")
    # your existing database check/init code here
    yield  # This is where the app runs normally
    # Shutdown code (runs after server stops)
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# ─── Configuration ───────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    bundle_dir = Path(sys._MEIPASS)
    base_dir = Path(sys.executable).resolve().parent
else:
    bundle_dir = Path(__file__).resolve().parent
    base_dir = bundle_dir

log_file = base_dir / "UROMI.log"
logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.handlers = [file_handler]
logger.info("Application starting. Frozen=%s base_dir=%s bundle_dir=%s", getattr(sys, 'frozen', False), base_dir, bundle_dir)

UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "logging.Formatter",
            "fmt": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "()": "logging.Formatter",
            "fmt": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "class": "logging.StreamHandler",
            "formatter": "access",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}

static_dir = bundle_dir / "static"
template_dir = bundle_dir / "templates"

# Ensure required directories exist when running from a bundle or source tree.
if not static_dir.exists():
    logger.warning("Static directory missing at %s, creating it.", static_dir)
    static_dir.mkdir(parents=True, exist_ok=True)

if not template_dir.exists():
    logger.warning("Template directory missing at %s, creating it.", template_dir)
    template_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(template_dir))

# ─── Register custom Jinja filter (must be right after templates) ──
def format_currency(value):
    try:
        return f"₦{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["format_currency"] = format_currency

DB_FILE = Path(__file__).resolve().parent / "ngo.db"


def get_db() -> sqlite3.Connection:
    """Get a new database connection with row factory set."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def table_has_column(table_name: str, column_name: str) -> bool:
    """Return True if the given table has the named column."""
    with get_db() as conn:
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(col[1] == column_name for col in cols)


def normalize_employee_row(employee: sqlite3.Row) -> dict:
    """Normalize an employee row for legacy and new schemas."""
    if employee is None:
        return {}

    data = dict(employee)
    full_name = (data.get('full_name') or '').strip()
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()

    if not first_name and full_name:
        parts = full_name.split()
        first_name = parts[0] if parts else ''
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else last_name

    if not last_name and full_name:
        parts = full_name.split()
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else last_name

    data['first_name'] = first_name or data.get('employee_id', '')
    data['last_name'] = last_name or ''
    data['position'] = data.get('position') or data.get('designation') or ''

    basic_salary = data.get('basic_salary')
    if basic_salary is None or basic_salary == '':
        monthly_salary = data.get('monthly_salary')
        try:
            data['basic_salary'] = float(monthly_salary) if monthly_salary is not None else 0.0
        except (TypeError, ValueError):
            data['basic_salary'] = 0.0
    else:
        try:
            data['basic_salary'] = float(basic_salary)
        except (TypeError, ValueError):
            data['basic_salary'] = 0.0

    data['bank_account_number'] = data.get('bank_account_number') or data.get('bank_account') or ''
    data['bank_account_name'] = data.get('bank_account_name') or ''
    data['department'] = data.get('department') or ''

    return data


def init_db() -> None:
    """Initialize database schema if tables don't exist + migrate missing columns."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Initializing/Verifying database at: {DB_FILE.absolute()}")

    with get_db() as conn:
        c = conn.cursor()

        # 1. Create all tables if they don't exist
        # Users
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT,
            email TEXT UNIQUE,
            last_password_change TEXT,
            password_reset_token TEXT,
            reset_token_expiry TEXT,
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Ensure at least one admin user exists for login safety
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        if user_count == 0:
            default_password_hash = hash_password("admin123")
            c.execute(
                "INSERT INTO users (username, password, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
                ("admin", default_password_hash, "admin", 1)
            )

        # Donors
        c.execute("""
        CREATE TABLE IF NOT EXISTS donors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_name TEXT UNIQUE NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT
        )
        """)

        # Projects
        c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT UNIQUE NOT NULL,
            donor TEXT,
            start_date TEXT,
            end_date TEXT
        )
        """)

        # Main Chart of Accounts
        c.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT UNIQUE NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT,
            description TEXT
        )
        """)

        # Sub-accounts
        c.execute("""
        CREATE TABLE IF NOT EXISTS subaccounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_account_code TEXT NOT NULL,
            sub_account_code TEXT UNIQUE NOT NULL,
            sub_account_name TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (parent_account_code) REFERENCES chart_of_accounts(account_code) ON DELETE CASCADE
        )
        """)

        # Vendors
        c.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tin TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            account_number TEXT,
            bank_name TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1
        )
        """)

        c.execute("""
        CREATE INDEX IF NOT EXISTS idx_vendors_name 
            ON vendors(name)
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                pv_number TEXT,
                reference TEXT,
                description TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                month INTEGER,
                project TEXT,
                main_account TEXT,
                main_account_code TEXT,
                sub_account TEXT,
                sub_account_code TEXT,
                wht_applied INTEGER DEFAULT 0,
                wht_rate REAL DEFAULT 0.0,
                wht_amount REAL DEFAULT 0.0,
                net_amount REAL DEFAULT 0.0
            )
        """)

        # Budget lines
        c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            account_code TEXT,
            account_name TEXT,
            subaccount_code TEXT,
            subaccount_name TEXT,
            detail TEXT,
            quantity REAL,
            unit_cost REAL,
            periods INTEGER,
            total REAL
        )
        """)

        # Legacy expenses
        c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            account_code TEXT,
            account_name TEXT,
            detail TEXT,
            amount REAL,
            date TEXT
        )
        """)


        conn.commit()

        # 2. Migrate any missing columns (safe even if table is new)
        c.execute("PRAGMA table_info(transactions)")
        columns = {row[1] for row in c.fetchall()}

        missing_cols = {
            'wht_applied': 'INTEGER DEFAULT 0',
            'wht_rate': 'REAL DEFAULT 0.0',
            'wht_amount': 'REAL DEFAULT 0.0',
            'net_amount': 'REAL DEFAULT 0.0',
            'vendor_tin': 'TEXT',
            'vendor_account_name': 'TEXT',
            'vendor_account_number': 'TEXT'
        }

        for col_name, col_def in missing_cols.items():
            if col_name not in columns:
                c.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_def}")
                print(f"→ Added missing column to transactions: {col_name}")

        conn.commit()

        # 2b. Migrate budgets table - add missing columns
        c.execute("PRAGMA table_info(budgets)")
        budget_columns = {row[1] for row in c.fetchall()}

        budget_missing_cols = {
            'total': 'REAL DEFAULT 0'
        }

        for col_name, col_def in budget_missing_cols.items():
            if col_name not in budget_columns:
                c.execute(f"ALTER TABLE budgets ADD COLUMN {col_name} {col_def}")
                print(f"→ Added missing column to budgets: {col_name}")

        conn.commit()

        # 2c. Migrate chart_of_accounts table - add soft delete & audit columns
        c.execute("PRAGMA table_info(chart_of_accounts)")
        coa_columns = {row[1] for row in c.fetchall()}

        # Add columns without problematic CURRENT_TIMESTAMP default
        coa_migrations = [
            ('is_active', 'INTEGER'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT')
        ]

        for col_name, col_type in coa_migrations:
            if col_name not in coa_columns:
                c.execute(f"ALTER TABLE chart_of_accounts ADD COLUMN {col_name} {col_type}")
                # Set default values for existing rows
                if col_name == 'is_active':
                    c.execute(f"UPDATE chart_of_accounts SET {col_name} = 1 WHERE {col_name} IS NULL")
                else:  # created_at, updated_at
                    c.execute(f"UPDATE chart_of_accounts SET {col_name} = datetime('now') WHERE {col_name} IS NULL")
                print(f"→ Added missing column to chart_of_accounts: {col_name}")

        conn.commit()

        # 2d. Migrate subaccounts table - add soft delete & audit columns
        c.execute("PRAGMA table_info(subaccounts)")
        sub_columns = {row[1] for row in c.fetchall()}

        # Add columns without problematic CURRENT_TIMESTAMP default
        sub_migrations = [
            ('is_active', 'INTEGER'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT')
        ]

        for col_name, col_type in sub_migrations:
            if col_name not in sub_columns:
                c.execute(f"ALTER TABLE subaccounts ADD COLUMN {col_name} {col_type}")
                # Set default values for existing rows
                if col_name == 'is_active':
                    c.execute(f"UPDATE subaccounts SET {col_name} = 1 WHERE {col_name} IS NULL")
                else:  # created_at, updated_at
                    c.execute(f"UPDATE subaccounts SET {col_name} = datetime('now') WHERE {col_name} IS NULL")
                print(f"→ Added missing column to subaccounts: {col_name}")

        conn.commit()

        # 2e. Migrate projects table - standardize columns
        # First, check actual table structure
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        projects_exists = c.fetchone() is not None
        
        if projects_exists:
            c.execute("PRAGMA table_info(projects)")
            proj_cols = {row[1] for row in c.fetchall()}
            print(f"✓ Projects table exists with columns: {proj_cols}")
            
            # Case 1: Table has 'name' instead of 'project_name' - MIGRATE IT
            if 'name' in proj_cols and 'project_name' not in proj_cols:
                print("→ Migrating projects table: 'name' → 'project_name'")
                try:
                    # Backup old data
                    c.execute("SELECT * FROM projects")
                    old_data = c.fetchall()
                    old_cols = [desc[0] for desc in c.description]
                    
                    # Drop old table
                    c.execute("DROP TABLE projects")
                    
                    # Create new table with correct schema
                    c.execute("""
                        CREATE TABLE projects (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_name TEXT UNIQUE NOT NULL,
                            code TEXT,
                            donor TEXT,
                            description TEXT,
                            sector TEXT,
                            budget REAL,
                            start_date TEXT,
                            end_date TEXT,
                            created_at TEXT DEFAULT (datetime('now')),
                            is_active INTEGER DEFAULT 1
                        )
                    """)
                    
                    # Restore data - map 'name' to 'project_name'
                    for row in old_data:
                        row_dict = dict(zip(old_cols, row))
                        c.execute("""
                            INSERT INTO projects 
                            (id, project_name, code, donor, description, sector, budget, start_date, end_date, created_at, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row_dict.get('id'),
                            row_dict.get('name'),  # Map 'name' to 'project_name'
                            row_dict.get('code'),
                            row_dict.get('donor'),
                            row_dict.get('description'),
                            row_dict.get('sector'),
                            row_dict.get('budget'),
                            row_dict.get('start_date'),
                            row_dict.get('end_date'),
                            row_dict.get('created_at', 'now'),
                            1  # is_active = 1
                        ))
                    conn.commit()
                    print("✓ Projects table migrated successfully")
                except Exception as e:
                    print(f"✗ Migration failed: {e}")
                    # Try to recover - recreate table fresh
                    try:
                        c.execute("DROP TABLE IF EXISTS projects")
                        c.execute("""
                            CREATE TABLE projects (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                project_name TEXT UNIQUE NOT NULL,
                                code TEXT,
                                donor TEXT,
                                description TEXT,
                                sector TEXT,
                                budget REAL,
                                start_date TEXT,
                                end_date TEXT,
                                created_at TEXT DEFAULT (datetime('now')),
                                is_active INTEGER DEFAULT 1
                            )
                        """)
                        conn.commit()
                        print("✓ Projects table recreated fresh")
                    except Exception as e2:
                        print(f"✗ Failed to recreate projects table: {e2}")
                        
            # Case 2: Table exists but missing some columns - ADD THEM
            else:
                c.execute("PRAGMA table_info(projects)")
                proj_cols = {row[1] for row in c.fetchall()}
                
                proj_missing_cols = [
                    ('project_name', 'TEXT UNIQUE'),
                    ('donor', 'TEXT'),
                    ('sector', 'TEXT'),
                    ('budget', 'REAL'),
                    ('start_date', 'TEXT'),
                    ('end_date', 'TEXT'),
                    ('is_active', 'INTEGER'),
                    ('code', 'TEXT')
                ]
                
                for col_name, col_type in proj_missing_cols:
                    if col_name not in proj_cols:
                        try:
                            if col_name == 'is_active':
                                c.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type} DEFAULT 1")
                                c.execute(f"UPDATE projects SET {col_name} = 1 WHERE {col_name} IS NULL")
                            else:
                                c.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                            print(f"→ Added column to projects: {col_name}")
                        except Exception as e:
                            print(f"⚠ Could not add column {col_name}: {e}")
                
                conn.commit()
        else:
            print("→ Creating projects table fresh")
            c.execute("""
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT UNIQUE NOT NULL,
                    code TEXT,
                    donor TEXT,
                    description TEXT,
                    sector TEXT,
                    budget REAL,
                    start_date TEXT,
                    end_date TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()
            print("✓ Projects table created")

        # 3. Verification & debug output
        tables = ['chart_of_accounts', 'subaccounts', 'transactions', 'budgets', 'expenses', 'projects']
        for tbl in tables:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
            if c.fetchone():
                print(f"✓ Table '{tbl}' exists")
            else:
                print(f"✗ Table '{tbl}' NOT created!")

        # Verify projects table has correct columns
        c.execute("PRAGMA table_info(projects)")
        proj_cols = [row[1] for row in c.fetchall()]
        print(f"Projects table columns: {proj_cols}")
        
        if 'project_name' in proj_cols:
            print("✓ Projects table has 'project_name' column")
            # Also verify sector and budget exist
            if 'sector' not in proj_cols or 'budget' not in proj_cols:
                print("⚠ Projects table missing sector/budget columns - ADDING...")
                if 'sector' not in proj_cols:
                    c.execute("ALTER TABLE projects ADD COLUMN sector TEXT")
                    print("→ Added sector column")
                if 'budget' not in proj_cols:
                    c.execute("ALTER TABLE projects ADD COLUMN budget REAL")
                    print("→ Added budget column")
                conn.commit()
            print("✓ Projects table READY with all columns")
        else:
            print("✗ Projects table MISSING 'project_name' column - FIXING...")
            # Force fix if it still doesn't have the right column
            try:
                c.execute("DROP TABLE IF EXISTS projects")
                c.execute("""
                    CREATE TABLE projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_name TEXT UNIQUE NOT NULL,
                        code TEXT,
                        donor TEXT,
                        description TEXT,
                        sector TEXT,
                        budget REAL,
                        start_date TEXT,
                        end_date TEXT,
                        created_at TEXT DEFAULT (datetime('now')),
                        is_active INTEGER DEFAULT 1
                    )
                """)
                conn.commit()
                print("✓ Projects table FIXED and recreated with sector & budget")
            except Exception as e:
                print(f"✗ CRITICAL: Could not fix projects table: {e}")

        # Show current columns in transactions
        c.execute("PRAGMA table_info(transactions)")
        print("Columns in transactions:", [row[1] for row in c.fetchall()])

        # 2f. Migrate users table - add password management columns
        c.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in c.fetchall()}

        user_migrations = [
            ('email', 'TEXT UNIQUE'),
            ('last_password_change', 'TEXT'),
            ('password_reset_token', 'TEXT'),
            ('reset_token_expiry', 'TEXT'),
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('locked_until', 'TEXT'),
            ('is_active', 'INTEGER DEFAULT 1'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT')
        ]

        for col_name, col_type in user_migrations:
            if col_name not in user_columns:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    print(f"→ Added column to users: {col_name}")
                except Exception as e:
                    print(f"⚠ Could not add column {col_name} to users: {e}")

        # Ensure existing users have active accounts after schema migration
        c.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        # Ensure existing users have a role assigned for role-based login
        c.execute("UPDATE users SET role = 'admin' WHERE role IS NULL OR trim(role) = ''")
        conn.commit()
        print("✓ Password management columns added to users table and enabled existing users")

        # ─── PAYROLL MANAGEMENT TABLES ──────────────────────────────────────

        # Employees table
        c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            date_of_birth TEXT,
            hire_date TEXT NOT NULL,
            termination_date TEXT,
            department TEXT,
            position TEXT,
            employment_type TEXT CHECK(employment_type IN ('full-time', 'part-time', 'contract', 'intern')) DEFAULT 'full-time',
            basic_salary REAL NOT NULL DEFAULT 0,
            bank_name TEXT,
            bank_account_number TEXT,
            bank_account_name TEXT,
            tax_id TEXT,
            pension_fund TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Migrate legacy employees schema if necessary
        c.execute("PRAGMA table_info(employees)")
        employee_cols = {row[1] for row in c.fetchall()}

        employee_missing_cols = {
            'first_name': 'TEXT',
            'last_name': 'TEXT',
            'email': 'TEXT',
            'phone': 'TEXT',
            'address': 'TEXT',
            'date_of_birth': 'TEXT',
            'termination_date': 'TEXT',
            'department': 'TEXT',
            'position': 'TEXT',
            'employment_type': 'TEXT',
            'basic_salary': 'REAL DEFAULT 0',
            'bank_name': 'TEXT',
            'bank_account_number': 'TEXT',
            'bank_account_name': 'TEXT',
            'tax_id': 'TEXT',
            'pension_fund': 'TEXT',
            'emergency_contact_name': 'TEXT',
            'emergency_contact_phone': 'TEXT',
            'created_at': 'TEXT',
            'updated_at': 'TEXT'
        }

        for col_name, col_def in employee_missing_cols.items():
            if col_name not in employee_cols:
                c.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_def}")
                print(f"→ Added missing column to employees: {col_name}")

        # Populate new employee fields from legacy data
        if 'full_name' in employee_cols:
            rows = c.execute("SELECT id, full_name FROM employees WHERE full_name IS NOT NULL AND (first_name IS NULL OR first_name = '' OR last_name IS NULL OR last_name = '')").fetchall()
            for row in rows:
                fullname = row[1] or ''
                parts = fullname.strip().split()
                first = parts[0] if parts else ''
                last = ' '.join(parts[1:]) if len(parts) > 1 else ''
                c.execute("UPDATE employees SET first_name = ?, last_name = ? WHERE id = ?", (first, last, row[0]))

        if 'designation' in employee_cols and 'position' in employee_missing_cols:
            c.execute("UPDATE employees SET position = designation WHERE (position IS NULL OR position = '') AND designation IS NOT NULL")

        if 'monthly_salary' in employee_cols and 'basic_salary' in employee_missing_cols:
            c.execute("UPDATE employees SET basic_salary = monthly_salary WHERE (basic_salary IS NULL OR basic_salary = 0) AND monthly_salary IS NOT NULL")

        if 'bank_account' in employee_cols and 'bank_account_number' in employee_missing_cols:
            c.execute("UPDATE employees SET bank_account_number = bank_account WHERE (bank_account_number IS NULL OR bank_account_number = '') AND bank_account IS NOT NULL")

        conn.commit()

        # Salary components (allowances and deductions)
        c.execute("""
        CREATE TABLE IF NOT EXISTS salary_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            component_type TEXT CHECK(component_type IN ('allowance', 'deduction')) NOT NULL,
            is_taxable INTEGER DEFAULT 1,
            is_percentage INTEGER DEFAULT 0,
            percentage_value REAL DEFAULT 0,
            fixed_amount REAL DEFAULT 0,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Employee salary structure (links employees to their salary components)
        c.execute("""
        CREATE TABLE IF NOT EXISTS employee_salary_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            effective_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (component_id) REFERENCES salary_components(id) ON DELETE CASCADE
        )
        """)

        # Tax rates table
        c.execute("""
        CREATE TABLE IF NOT EXISTS tax_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_name TEXT NOT NULL,
            tax_type TEXT CHECK(tax_type IN ('income_tax', 'pension', 'nhf', 'nhis', 'paye')) NOT NULL,
            min_income REAL NOT NULL DEFAULT 0,
            max_income REAL,
            tax_rate REAL NOT NULL DEFAULT 0,
            fixed_amount REAL DEFAULT 0,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            effective_date TEXT NOT NULL,
            end_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Payroll runs (monthly payroll processing)
        c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_period TEXT NOT NULL,
            pay_date TEXT NOT NULL,
            status TEXT CHECK(status IN ('draft', 'processed', 'paid')) DEFAULT 'draft',
            total_gross REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            total_net REAL DEFAULT 0,
            total_employees INTEGER DEFAULT 0,
            processed_by INTEGER,
            approved_by INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (processed_by) REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
        """)

        # Detect legacy payroll_runs schema and migrate if required
        c.execute("PRAGMA table_info(payroll_runs)")
        payroll_run_cols = {row[1] for row in c.fetchall()}
        required_run_cols = {
            'id', 'payroll_period', 'pay_date', 'status', 'total_gross',
            'total_deductions', 'total_net', 'total_employees', 'processed_by',
            'approved_by', 'notes', 'created_at', 'updated_at'
        }

        if not required_run_cols.issubset(payroll_run_cols):
            print("→ Legacy payroll_runs schema detected; migrating payroll_runs table")
            c.execute("ALTER TABLE payroll_runs RENAME TO payroll_runs_old")
            c.execute("""
            CREATE TABLE payroll_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payroll_period TEXT NOT NULL,
                pay_date TEXT NOT NULL,
                status TEXT CHECK(status IN ('draft', 'processed', 'paid')) DEFAULT 'draft',
                total_gross REAL DEFAULT 0,
                total_deductions REAL DEFAULT 0,
                total_net REAL DEFAULT 0,
                total_employees INTEGER DEFAULT 0,
                processed_by INTEGER,
                approved_by INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (processed_by) REFERENCES users(id),
                FOREIGN KEY (approved_by) REFERENCES users(id)
            )
            """)

            c.execute("SELECT * FROM payroll_runs_old")
            old_rows = c.fetchall()
            old_cols = [description[0] for description in c.description]

            for old_row in old_rows:
                row = dict(zip(old_cols, old_row))
                payroll_period = row.get('payroll_period')
                if not payroll_period:
                    # Use period_code or month/year when available
                    if row.get('period_code'):
                        payroll_period = row.get('period_code')
                    elif row.get('month') is not None and row.get('year') is not None:
                        payroll_period = f"{int(row.get('month')):02d}/{int(row.get('year'))}"
                    else:
                        payroll_period = 'Unknown Period'

                pay_date = row.get('pay_date')
                if not pay_date:
                    month = row.get('month')
                    year = row.get('year')
                    if month is not None and year is not None:
                        try:
                            pay_date = f"{int(year):04d}-{int(month):02d}-28"
                        except Exception:
                            pay_date = datetime.now().strftime('%Y-%m-%d')
                    else:
                        pay_date = datetime.now().strftime('%Y-%m-%d')

                status = row.get('status') or 'draft'
                if status not in ('draft', 'processed', 'paid'):
                    status = 'draft' if status in ('pending', 'new', '') else 'processed'

                processed_by = None
                approved_by = None
                if isinstance(row.get('created_by'), int):
                    processed_by = row.get('created_by')
                elif isinstance(row.get('created_by'), str) and row.get('created_by').isdigit():
                    processed_by = int(row.get('created_by'))
                if isinstance(row.get('approved_by'), int):
                    approved_by = row.get('approved_by')
                elif isinstance(row.get('approved_by'), str) and row.get('approved_by').isdigit():
                    approved_by = int(row.get('approved_by'))

                c.execute("""
                    INSERT INTO payroll_runs (
                        id, payroll_period, pay_date, status, total_gross,
                        total_deductions, total_net, total_employees,
                        processed_by, approved_by, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('id'),
                    payroll_period,
                    pay_date,
                    status,
                    row.get('total_gross', 0),
                    row.get('total_deductions', 0),
                    row.get('total_net', 0),
                    row.get('employee_count', row.get('total_employees', 0) or 0),
                    processed_by,
                    approved_by,
                    row.get('notes'),
                    row.get('created_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    row.get('updated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

            c.execute("DROP TABLE payroll_runs_old")
            print("✓ payroll_runs table migrated successfully")

        # Payroll details (individual employee payroll entries)
        c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_run_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL DEFAULT '',
            basic_salary REAL NOT NULL DEFAULT 0,
            total_allowances REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            income_tax REAL DEFAULT 0,
            pension REAL DEFAULT 0,
            nhf REAL DEFAULT 0,
            nhis REAL DEFAULT 0,
            paye REAL DEFAULT 0,
            other_deductions REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            net_pay REAL NOT NULL DEFAULT 0,
            payment_status TEXT CHECK(payment_status IN ('pending', 'paid', 'failed')) DEFAULT 'pending',
            payment_date TEXT,
            bank_reference TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
        """)

        # Ensure payroll_details has required columns for older schema versions
        c.execute("PRAGMA table_info(payroll_details)")
        payroll_detail_cols = {row[1] for row in c.fetchall()}
        payroll_detail_missing_cols = {
            'employee_name': "TEXT NOT NULL DEFAULT ''",
            'basic_salary': 'REAL NOT NULL DEFAULT 0',
            'total_allowances': 'REAL DEFAULT 0',
            'total_deductions': 'REAL DEFAULT 0',
            'gross_salary': 'REAL DEFAULT 0',
            'income_tax': 'REAL DEFAULT 0',
            'pension': 'REAL DEFAULT 0',
            'nhf': 'REAL DEFAULT 0',
            'nhis': 'REAL DEFAULT 0',
            'paye': 'REAL DEFAULT 0',
            'other_deductions': 'REAL DEFAULT 0',
            'net_salary': 'REAL DEFAULT 0',
            'net_pay': 'REAL NOT NULL DEFAULT 0',
            'payment_status': "TEXT CHECK(payment_status IN ('pending', 'paid', 'failed')) DEFAULT 'pending'",
            'payment_date': 'TEXT',
            'bank_reference': 'TEXT',
            'status': "TEXT DEFAULT 'pending'",
            'created_at': 'TEXT DEFAULT (datetime(\'now\'))',
            'updated_at': 'TEXT DEFAULT (datetime(\'now\'))'
        }
        for col_name, col_def in payroll_detail_missing_cols.items():
            if col_name not in payroll_detail_cols:
                c.execute(f"ALTER TABLE payroll_details ADD COLUMN {col_name} {col_def}")
                print(f"→ Added missing column to payroll_details: {col_name}")

        # Payslips table
        c.execute("""
        CREATE TABLE IF NOT EXISTS payslips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_detail_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            payslip_number TEXT UNIQUE NOT NULL,
            payslip_data TEXT NOT NULL, -- JSON data for payslip content
            generated_at TEXT DEFAULT (datetime('now')),
            generated_by INTEGER,
            FOREIGN KEY (payroll_detail_id) REFERENCES payroll_details(id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (generated_by) REFERENCES users(id)
        )
        """)

        # Payroll audit log
        c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            action TEXT CHECK(action IN ('INSERT', 'UPDATE', 'DELETE')) NOT NULL,
            old_values TEXT, -- JSON
            new_values TEXT, -- JSON
            changed_by INTEGER,
            changed_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
        """)

        # Insert default salary components
        c.execute("SELECT COUNT(*) FROM salary_components")
        if c.fetchone()[0] == 0:
            default_components = [
                ('Housing Allowance', 'allowance', 1, 0, 0, 0, 'Monthly housing allowance'),
                ('Transport Allowance', 'allowance', 1, 0, 0, 0, 'Monthly transport allowance'),
                ('Medical Allowance', 'allowance', 1, 0, 0, 0, 'Monthly medical allowance'),
                ('Utility Allowance', 'allowance', 1, 0, 0, 0, 'Monthly utility allowance'),
                ('Overtime', 'allowance', 1, 0, 0, 0, 'Overtime pay'),
                ('Bonus', 'allowance', 1, 0, 0, 0, 'Performance bonus'),
                ('Loan Deduction', 'deduction', 0, 0, 0, 0, 'Monthly loan repayment'),
                ('Advance Deduction', 'deduction', 0, 0, 0, 0, 'Salary advance deduction'),
                ('Union Dues', 'deduction', 0, 0, 0, 0, 'Union membership dues'),
                ('Provident Fund', 'deduction', 0, 1, 8.0, 0, '8% employee contribution to provident fund'),
            ]
            for comp in default_components:
                c.execute("""
                INSERT INTO salary_components 
                (component_name, component_type, is_taxable, is_percentage, percentage_value, fixed_amount, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, comp)

        # Insert default tax rates (Nigerian PAYE system)
        c.execute("SELECT COUNT(*) FROM tax_rates")
        if c.fetchone()[0] == 0:
            default_tax_rates = [
                ('PAYE 7%', 'paye', 0, 300000, 7.0, 0, 'PAYE tax rate for income up to ₦300,000', '2024-01-01'),
                ('PAYE 11%', 'paye', 300000, 600000, 11.0, 21000, 'PAYE tax rate for income ₦300,001 - ₦600,000', '2024-01-01'),
                ('PAYE 15%', 'paye', 600000, 1100000, 15.0, 66000, 'PAYE tax rate for income ₦600,001 - ₦1,100,000', '2024-01-01'),
                ('PAYE 19%', 'paye', 1100000, 1600000, 19.0, 165000, 'PAYE tax rate for income ₦1,100,001 - ₦1,600,000', '2024-01-01'),
                ('PAYE 21%', 'paye', 1600000, 3200000, 21.0, 285000, 'PAYE tax rate for income ₦1,600,001 - ₦3,200,000', '2024-01-01'),
                ('PAYE 24%', 'paye', 3200000, None, 24.0, 669000, 'PAYE tax rate for income above ₦3,200,000', '2024-01-01'),
                ('Pension', 'pension', 0, None, 8.0, 0, '8% pension contribution', '2024-01-01'),
                ('NHF', 'nhf', 0, None, 2.5, 0, '2.5% National Housing Fund contribution', '2024-01-01'),
                ('NHIS', 'nhis', 0, None, 5.0, 0, '5% National Health Insurance Scheme contribution', '2024-01-01'),
            ]
            for tax in default_tax_rates:
                c.execute("""
                INSERT INTO tax_rates 
                (tax_name, tax_type, min_income, max_income, tax_rate, fixed_amount, description, effective_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, tax)

        conn.commit()
        print("✓ Payroll management tables created and populated with default data")


init_db()

# ─── Database Helpers ────────────────────────────────────────────────
def get_main_accounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM chart_of_accounts WHERE is_active = 1 ORDER BY account_code").fetchall()


def get_subaccounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM subaccounts WHERE is_active = 1 ORDER BY sub_account_code").fetchall()


def get_projects() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM projects WHERE is_active = 1 ORDER BY project_name").fetchall()


def get_vendors() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM vendors WHERE is_active = 1 ORDER BY name").fetchall()


def get_transactions() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("""
            SELECT 
                t.id,
                t.date,
                t.pv_number,
                t.reference,
                t.description,
                t.type,
                t.amount,
                t.month,
                t.project,
                t.main_account,
                t.main_account_code,
                t.sub_account,
                t.sub_account_code,
                t.wht_applied,
                COALESCE(t.wht_rate, 0) AS wht_rate,
                COALESCE(t.wht_amount, 0) AS wht_amount,
                COALESCE(t.net_amount, 0) AS net_amount,
                COALESCE(coa.account_name, 'Unknown') AS account_name,
                t.vendor_tin,
                t.vendor_account_name,
                t.vendor_account_number
            FROM transactions t
            LEFT JOIN chart_of_accounts coa ON t.main_account_code = coa.account_code
            ORDER BY t.date DESC, t.id DESC
        """).fetchall()


# ─── Routes ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/dashboard", status_code=303)

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse

# ──────────────────────────────────────────────────────────────
# Helper function (put this somewhere in your file, preferably above routes)
# ──────────────────────────────────────────────────────────────
def number_to_words(n: float) -> str:
    if n == 0:
        return "Zero Naira Only"

    units = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def helper(num: int) -> str:
        if num < 20:
            return units[num]
        if num < 100:
            return tens[num // 10] + (" " + units[num % 10] if num % 10 else "")
        if num < 1000:
            return units[num // 100] + " Hundred" + (" " + helper(num % 100) if num % 100 else "")
        return f"{num:,}"  # fallback

    naira = int(n)
    kobo = int(round((n - naira) * 100))

    words = helper(naira) + " Naira"
    if kobo > 0:
        words += f" and {helper(kobo)} Kobo"
    return words + " Only"


# ──────────────────────────────────────────────────────────────
# Dedicated route for modal/content version
# ──────────────────────────────────────────────────────────────


def number_to_words(n: float | int | str) -> str:
    """
    Convert amount (Naira) to words with Kobo.
    Handles up to billions. Works with int, float, or string input.
    Examples:
        98000      "Ninety Eight Thousand Naira Only"
        100000.50  "One Hundred Thousand Naira and Fifty Kobo Only"
        0          "Zero Naira Only"
    """
    if isinstance(n, str):
        n = float(n.replace(",", ""))  # remove commas if string

    n = float(n or 0)
    if n == 0:
        return "Zero Naira Only"

    units = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million", "Billion"]

    def helper(num: int) -> str:
        if num == 0:
            return ""
        if num < 20:
            return units[num]
        if num < 100:
            return tens[num // 10] + (" " + units[num % 10] if num % 10 else "")
        if num < 1000:
            hundred = num // 100
            remainder = num % 100
            return units[hundred] + " Hundred" + (" " + helper(remainder) if remainder else "")

        for i, scale in enumerate(scales[1:], 1):  # start from Thousand
            base = 1000 ** i
            if num < base * 1000:
                quotient = num // base
                remainder = num % base
                part = helper(quotient) + f" {scale}"
                return part + (" " + helper(remainder) if remainder else "")
        return f"{num:,}"  # fallback (very large numbers)

    naira = int(n)
    kobo = int(round((n - naira) * 100))

    words = helper(naira).strip()
    if not words:
        words = "Zero"

    result = f"{words} Naira"
    if kobo > 0:
        kobo_words = helper(kobo).strip()
        result += f" and {kobo_words} Kobo"

    return result + " Only"


@app.get("/payment-voucher-content/{transaction_id}", response_class=HTMLResponse)
async def payment_voucher_content(transaction_id: int, request: Request):
    """
    Returns only the printable voucher content (for modal/iframe).
    Use this in your frontend modal fetch or iframe src.
    """
    with get_db() as conn:
        tx = conn.execute(
            """
            SELECT 
                id, date, pv_number, description, type, amount,
                main_account_code, main_account,
                sub_account_code, sub_account,
                project, vendor_account_name, vendor_tin,
                wht_applied, wht_rate, wht_amount, net_amount
            FROM transactions 
            WHERE id = ?
            """,
            (transaction_id,)
        ).fetchone()

        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")

    # Safe dict conversion
    tx_dict = dict(tx)

    # Decide amount for words (prefer net if WHT applied)
    use_net = bool(tx_dict.get("wht_applied")) and (tx_dict.get("wht_rate", 0) > 0)
    display_amount = float(tx_dict.get("net_amount") if use_net else tx_dict.get("amount") or 0)

    context = {
        "request": request,
        "tx": tx_dict,
        "voucher_title": "PAYMENT VOUCHER" if tx_dict.get("type") == "Expense" else "RECEIPT VOUCHER",
        "pv_number": tx_dict.get("pv_number") or f"PV-{tx_dict['id']:06d}",
        "tx_date": tx_dict.get("date", "—"),
        "description": tx_dict.get("description", "—"),
        "gross_amount_formatted": f"₦{tx_dict.get('amount', 0):,.2f}",
        "wht_applied": bool(tx_dict.get("wht_applied", 0)),
        "wht_rate_percent": round(float(tx_dict.get("wht_rate", 0)) * 100, 2),
        "wht_amount_formatted": f"₦{tx_dict.get('wht_amount', 0):,.2f}",
        "net_amount_formatted": f"₦{tx_dict.get('net_amount', tx_dict.get('amount', 0)):,.2f}",
        "payee": tx_dict.get("vendor_account_name", "—"),
        "payee_tin": tx_dict.get("vendor_tin", "—"),
        "main_account_display": (
            f"{tx_dict.get('main_account_code', '—')} — {tx_dict.get('main_account', '—')}"
        ),
        "sub_account_display": (
            f"{tx_dict.get('sub_account_code', '—')} — {tx_dict.get('sub_account', '—')}"
            if tx_dict.get("sub_account_code")
            else "—"
        ),
        "project": tx_dict.get("project", "—"),
        "amount_in_words": number_to_words(display_amount),
        "prepared_by": "Jude Oko-Oboh",
        "approved_by": "Abba Umar",
    }

    return templates.TemplateResponse("payment-voucher-content.html", context)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_user(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form(...)):
    username = username.strip()
    selected_role = role.strip().lower()

    valid_roles = ['admin', 'finance', 'audit']
    if selected_role not in valid_roles:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Please select a valid role"})

    with get_db() as conn:
        user = conn.execute("SELECT username, password, is_active, role FROM users WHERE username = ?", (username,)).fetchone()

    if not user or (user["is_active"] == 0):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials or inactive account"})

    if user["role"] is None or user["role"].strip().lower() != selected_role:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Role does not match user profile"})

    if not verify_password(password, user["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("username", username, httponly=True, max_age=60*60*24)
    response.set_cookie("user_role", selected_role, httponly=True, max_age=60*60*24)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("username")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    current_username = request.cookies.get("username")
    current_role = request.cookies.get("user_role") or "user"
    if not current_username:
        return RedirectResponse(url="/login", status_code=303)

    with get_db() as conn:
        total_budget = conn.execute("SELECT IFNULL(SUM(total), 0) FROM budgets").fetchone()[0]
        total_income = conn.execute(
            "SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type = 'Income'"
        ).fetchone()[0]
        total_expenses = conn.execute(
            "SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type = 'Expense'"
        ).fetchone()[0]

    balance = total_income - total_expenses
    burn_rate = round((total_expenses / total_budget * 100), 2) if total_budget > 0 else 0.0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_budget": total_budget,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "balance": balance,
            "burn_rate": burn_rate,
            "current_username": current_username,
            "current_role": current_role,
        }
    )


# ─── Chart of Accounts ──────────────────────────────────────────────

@app.get("/chart-of-accounts", response_class=HTMLResponse)
@app.get("/accounts", response_class=HTMLResponse)
async def chart_of_accounts(request: Request):
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": {},
            "error": None
        }
    )

@app.post("/add-account")
async def add_main_account(
    request: Request,
    account_code: str = Form(...),
    account_name: str = Form(...),
    account_type: str = Form(...),
    description: str = Form(default="")
):
    account_code = account_code.strip()
    account_name = account_name.strip()
    description = description.strip()
    form_data = {
        "account_code": account_code,
        "account_name": account_name,
        "account_type": account_type,
        "description": description
    }
    with get_db() as conn:
        try:
            # Check if account already exists (active or inactive)
            existing = conn.execute(
                "SELECT id, is_active FROM chart_of_accounts WHERE account_code = ?",
                (account_code,)
            ).fetchone()
            
            if existing:
                # Account exists - check if it's inactive (soft-deleted)
                if existing['is_active'] == 0:
                    # Reactivate it instead of creating new
                    conn.execute(
                        """
                        UPDATE chart_of_accounts 
                        SET account_name = ?, account_type = ?, description = ?, is_active = 1, updated_at = datetime('now')
                        WHERE account_code = ?
                        """,
                        (account_name, account_type, description, account_code)
                    )
                    conn.commit()
                    return RedirectResponse("/chart-of-accounts?success=Account+reactivated", status_code=303)
                else:
                    # Account is already active - can't create duplicate
                    error = f"Account code '{account_code}' already exists."
            else:
                # New account - create it
                conn.execute(
                    """
                    INSERT INTO chart_of_accounts
                    (account_code, account_name, account_type, description, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (account_code, account_name, account_type, description)
                )
                conn.commit()
                return RedirectResponse("/chart-of-accounts?success=Account+created+successfully", status_code=303)
        except Exception as e:
            error = str(e)
    
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": form_data,
            "error": error
        }
    )

@app.post("/add-subaccount")
async def add_subaccount(
    request: Request,
    parent_account: str = Form(...),
    sub_account_code: str = Form(...),
    sub_account_name: str = Form(...),
    description: str = Form(default="")
):
    sub_account_code = sub_account_code.strip()
    sub_account_name = sub_account_name.strip()
    description = description.strip()
    form_data = {
        "parent_account": parent_account,
        "sub_account_code": sub_account_code,
        "sub_account_name": sub_account_name,
        "description": description
    }
    with get_db() as conn:
        try:
            # Check if sub-account already exists (active or inactive)
            existing = conn.execute(
                "SELECT id, is_active FROM subaccounts WHERE sub_account_code = ?",
                (sub_account_code,)
            ).fetchone()
            
            if existing:
                # Sub-account exists - check if it's inactive (soft-deleted)
                if existing['is_active'] == 0:
                    # Reactivate it instead of creating new
                    conn.execute(
                        """
                        UPDATE subaccounts 
                        SET parent_account_code = ?, sub_account_name = ?, description = ?, is_active = 1, updated_at = datetime('now')
                        WHERE sub_account_code = ?
                        """,
                        (parent_account, sub_account_name, description, sub_account_code)
                    )
                    conn.commit()
                    return RedirectResponse("/chart-of-accounts?success=Sub-account+reactivated", status_code=303)
                else:
                    # Sub-account is already active - can't create duplicate
                    error = f"Sub-account code '{sub_account_code}' already exists."
            else:
                # New sub-account - create it
                # Verify parent account exists
                parent = conn.execute(
                    "SELECT id FROM chart_of_accounts WHERE account_code = ? AND is_active = 1",
                    (parent_account,)
                ).fetchone()
                
                if not parent:
                    error = f"Invalid parent account '{parent_account}'"
                else:
                    conn.execute(
                        """
                        INSERT INTO subaccounts
                        (parent_account_code, sub_account_code, sub_account_name, description, is_active)
                        VALUES (?, ?, ?, ?, 1)
                        """,
                        (parent_account, sub_account_code, sub_account_name, description)
                    )
                    conn.commit()
                    return RedirectResponse("/chart-of-accounts?success=Sub-account+created+successfully", status_code=303)
        except Exception as e:
            error = str(e)
    
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": form_data,
            "error": error
        }
    )

# ─── Edit Main Account (GET - Display Form) ──────────────────────────────

@app.get("/edit-main-account/{account_code}", response_class=HTMLResponse)
async def edit_main_account_form(request: Request, account_code: str):
    with get_db() as conn:
        account = conn.execute(
            "SELECT * FROM chart_of_accounts WHERE account_code = ?",
            (account_code,)
        ).fetchone()
        
        if not account:
            return RedirectResponse("/chart-of-accounts?error=Account+not+found", status_code=303)
        
        account = dict(account)
    
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": {},
            "error": None,
            "edit_account": account,  # Mark that we're editing
            "edit_type": "main"
        }
    )

# ─── Edit Main Account (POST - Save) ──────────────────────────────────

@app.post("/edit-account/{account_code}")
async def edit_main_account(
    account_code: str,
    request: Request,
    account_name: str = Form(...),
    account_type: str = Form(...),
    description: str = Form(default="")
):
    account_name = account_name.strip()
    description = description.strip()
    
    with get_db() as conn:
        try:
            # Update the account (without changing the code to preserve foreign keys)
            conn.execute(
                """
                UPDATE chart_of_accounts 
                SET account_name = ?, account_type = ?, description = ?, updated_at = datetime('now')
                WHERE account_code = ?
                """,
                (account_name, account_type, description, account_code)
            )
            conn.commit()
            return RedirectResponse("/chart-of-accounts?success=Account+updated+successfully", status_code=303)
        except Exception as e:
            conn.rollback()
            return RedirectResponse(
                f"/chart-of-accounts?error=Failed+to+update+account:+{str(e)}",
                status_code=303
            )

# ─── Edit Sub-Account (GET - Display Form) ────────────────────────────────

@app.get("/edit-subaccount/{sub_account_code}", response_class=HTMLResponse)
async def edit_subaccount_form(request: Request, sub_account_code: str):
    with get_db() as conn:
        subaccount = conn.execute(
            "SELECT * FROM subaccounts WHERE sub_account_code = ?",
            (sub_account_code,)
        ).fetchone()
        
        if not subaccount:
            return RedirectResponse("/chart-of-accounts?error=Sub-account+not+found", status_code=303)
        
        subaccount = dict(subaccount)
    
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": {},
            "error": None,
            "edit_subaccount": subaccount,  # Mark that we're editing
            "edit_type": "sub"
        }
    )

# ─── Edit Sub-Account (POST - Save) ───────────────────────────────────

@app.post("/edit-subaccount/{sub_account_code}")
async def edit_subaccount(
    sub_account_code: str,
    request: Request,
    parent_account: str = Form(...),
    sub_account_name: str = Form(...),
    description: str = Form(default="")
):
    sub_account_name = sub_account_name.strip()
    description = description.strip()
    
    with get_db() as conn:
        try:
            # Update the subaccount (without changing the code to preserve foreign keys)
            conn.execute(
                """
                UPDATE subaccounts 
                SET parent_account_code = ?, sub_account_name = ?, description = ?, updated_at = datetime('now')
                WHERE sub_account_code = ?
                """,
                (parent_account, sub_account_name, description, sub_account_code)
            )
            conn.commit()
            return RedirectResponse("/chart-of-accounts?success=Sub-account+updated+successfully", status_code=303)
        except Exception as e:
            conn.rollback()
            return RedirectResponse(
                f"/chart-of-accounts?error=Failed+to+update+sub-account:+{str(e)}",
                status_code=303
            )

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

# ─── Delete Main Account (Soft Delete) ───────────────────────────────────

@app.post("/delete-main-account/{account_code}")
async def delete_main_account(
    account_code: str,
    request: Request
):
    with get_db() as conn:
        try:
            # Soft delete: deactivate the account instead of deleting it
            # This preserves historical transaction data integrity
            cursor = conn.execute(
                "UPDATE chart_of_accounts SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE account_code = ?",
                (account_code,)
            )
            
            if cursor.rowcount == 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Account+not+found",
                    status_code=303
                )

            conn.commit()
            return RedirectResponse(
                "/chart-of-accounts?success=Main+account+deactivated",
                status_code=303
            )

        except Exception as e:
            conn.rollback()
            return RedirectResponse(
                f"/chart-of-accounts?error={str(e)}",
                status_code=303
            )


# ─── Delete Sub-Account (Soft Delete) ─────────────────────────────────

@app.post("/delete-subaccount/{sub_account_code}")
async def delete_subaccount(
    sub_account_code: str,
    request: Request
):
    with get_db() as conn:
        try:
            # Soft delete: deactivate the sub-account instead of deleting it
            # This preserves historical transaction data integrity
            cursor = conn.execute(
                "UPDATE subaccounts SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE sub_account_code = ?",
                (sub_account_code,)
            )

            if cursor.rowcount == 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Sub-account+not+found",
                    status_code=303
                )

            conn.commit()
            return RedirectResponse(
                "/chart-of-accounts?success=Sub-account+deactivated",
                status_code=303
            )

        except Exception as e:
            conn.rollback()
            return RedirectResponse(
                f"/chart-of-accounts?error={str(e)}",
                status_code=303
            )

# ─── Add / Create Transaction ────────────────────────────────────────────────

@app.get("/add-transaction", response_class=HTMLResponse)
async def add_transaction_form(request: Request):
    projects = get_projects()  # returns list of dicts with id, project_name, code, etc.

    return templates.TemplateResponse(
        "add_transaction.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "projects": projects,                    # full project objects (id + name + code)
            "subaccounts": get_subaccounts(),
            "vendors": get_vendors(),
            "form_data": {},
            "error": None,
            "transaction": None,
            "is_edit": False,
        }
    )


@app.post("/add-transaction")
async def create_transaction(
    request: Request,
    date: str = Form(...),
    pv_number: Optional[str] = Form(None),
    description: str = Form(...),
    type: str = Form(...),
    gross_amount: str = Form(...),
    project: Optional[str] = Form(None),
    main_account_code: str = Form(...),
    sub_account_code: Optional[str] = Form(None),
    vendor_tin: Optional[str] = Form(None),
    vendor_account_details: Optional[str] = Form(None),
    wht_applied: str = Form(default="off"),
    wht_rate: str = Form(default="0.0"),
):
    errors = []
    form_data = {
        "date": date,
        "pv_number": pv_number,
        "description": description,
        "type": type,
        "gross_amount": gross_amount,
        "project": project,
        "main_account_code": main_account_code,
        "sub_account_code": sub_account_code,
        "vendor_tin": vendor_tin,
        "vendor_account_details": vendor_account_details,
        "wht_applied": wht_applied,
        "wht_rate": wht_rate,
    }

    # ─── Basic validation ────────────────────────────────────────────────
    try:
        amount = float(gross_amount.strip().replace(",", ""))
        if amount <= 0:
            errors.append("Amount must be greater than zero")
    except (ValueError, TypeError):
        errors.append("Invalid amount format")

    if not main_account_code.strip():
        errors.append("Main account is required")

    # ─── Withholding tax logic ───────────────────────────────────────────
    wht_applied_flag = 1 if wht_applied == "on" else 0
    wht_rate_pct = 0.0
    wht_amount = 0.0
    net_amount = amount

    if wht_applied_flag:
        try:
            wht_rate_pct = float(wht_rate.strip() or "0") / 100.0
            if wht_rate_pct < 0 or wht_rate_pct > 1:
                errors.append("WHT rate must be between 0% and 100%")
            else:
                wht_amount = amount * wht_rate_pct
                net_amount = amount - wht_amount
        except (ValueError, TypeError):
            errors.append("Invalid WHT rate (use numbers only)")

    if errors:
        projects = get_projects()
        return templates.TemplateResponse(
            "add_transaction.html",
            {
                "request": request,
                "main_accounts": get_main_accounts(),
                "projects": projects,
                "subaccounts": get_subaccounts(),
                "vendors": get_vendors(),
                "form_data": form_data,
                "error": "<br>".join(errors),
                "transaction": None,
                "is_edit": False,
            }
        )

    # ─── Database operations ─────────────────────────────────────────────
    with get_db() as conn:
        # Get main account name
        main_row = conn.execute(
            "SELECT account_name FROM chart_of_accounts WHERE account_code = ?",
            (main_account_code.strip(),)
        ).fetchone()

        if not main_row:
            errors.append(f"Main account code '{main_account_code}' not found")
            return templates.TemplateResponse(
                "add_transaction.html",
                {
                    "request": request,
                    "main_accounts": get_main_accounts(),
                    "projects": get_projects(),
                    "subaccounts": get_subaccounts(),
                    "vendors": get_vendors(),
                    "form_data": form_data,
                    "error": "<br>".join(errors),
                    "transaction": None,
                    "is_edit": False,
                }
            )

        main_account_name = main_row["account_name"]

        # Get sub account name (optional)
        sub_account_name = None
        if sub_account_code and sub_account_code.strip():
            sub_row = conn.execute(
                "SELECT sub_account_name FROM subaccounts WHERE sub_account_code = ?",
                (sub_account_code.strip(),)
            ).fetchone()
            if sub_row:
                sub_account_name = sub_row["sub_account_name"]

        # Extract month from date (YYYY-MM-DD → MM)
        month = None
        if date:
            try:
                _, mm, _ = date.split("-")
                month = int(mm)
            except:
                pass

        # ─── INSERT ──────────────────────────────────────────────────────
        conn.execute("""
            INSERT INTO transactions (
                date, pv_number, description, type, amount,
                month, project,
                main_account, main_account_code,
                sub_account, sub_account_code,
                wht_applied, wht_rate, wht_amount, net_amount,
                vendor_tin, vendor_account_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.strip(),
            pv_number.strip() if pv_number else None,
            description.strip(),
            type.strip(),
            amount,
            month,
            project.strip() if project else None,
            main_account_name,
            main_account_code.strip(),
            sub_account_name,
            sub_account_code.strip() if sub_account_code else None,
            wht_applied_flag,
            wht_rate_pct,
            wht_amount,
            net_amount,
            vendor_tin.strip() if vendor_tin else None,
            vendor_account_details.strip() if vendor_account_details else None
        ))

        conn.commit()

    return RedirectResponse("/transactions?success=created", status_code=303)

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

# ─── Edit Transaction Form ────────────────────────────────────────────────

@app.get("/edit-transaction/{transaction_id}", response_class=HTMLResponse)
@app.post("/edit-transaction/{transaction_id}")
async def edit_transaction_form(
    request: Request, 
    transaction_id: int,
    date: Optional[str] = Form(None),
    pv_number: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    gross_amount: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    main_account_code: Optional[str] = Form(None),
    sub_account_code: Optional[str] = Form(None),
    vendor_tin: Optional[str] = Form(None),
    vendor_account_details: Optional[str] = Form(None),
    wht_applied: Optional[str] = Form(None),
    wht_rate: Optional[str] = Form(None),
):
    """Display the edit form pre-filled with existing transaction data (GET) or update transaction (POST)"""
    
    # Handle POST request - this is the update action
    if request.method == "POST":
        errors = []
        form_data = {
            "date": date,
            "pv_number": pv_number,
            "description": description,
            "type": type,
            "gross_amount": gross_amount,
            "project": project,
            "main_account_code": main_account_code,
            "sub_account_code": sub_account_code,
            "vendor_tin": vendor_tin,
            "vendor_account_details": vendor_account_details,
            "wht_applied": wht_applied,
            "wht_rate": wht_rate,
        }

        # ─── Validation ──────────────────────────────────────────────────────
        try:
            amount = float(gross_amount.strip().replace(",", ""))
            if amount <= 0:
                errors.append("Amount must be greater than zero")
        except (ValueError, TypeError):
            errors.append("Invalid amount format")

        if not main_account_code.strip():
            errors.append("Main account is required")

        # Withholding tax calculation
        wht_applied_flag = 1 if wht_applied == "on" else 0
        wht_rate_pct = 0.0
        wht_amount = 0.0
        net_amount = amount

        if wht_applied_flag:
            try:
                wht_rate_pct = float(wht_rate.strip() or "0") / 100.0
                if wht_rate_pct < 0 or wht_rate_pct > 1:
                    errors.append("WHT rate must be between 0% and 100%")
                else:
                    wht_amount = amount * wht_rate_pct
                    net_amount = amount - wht_amount
            except (ValueError, TypeError):
                errors.append("Invalid WHT rate format (use numbers only)")

        if errors:
            with get_db() as conn:
                tx = conn.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (transaction_id,)
                ).fetchone()

            return templates.TemplateResponse(
                "add_transaction.html",
                {
                    "request": request,
                    "main_accounts": get_main_accounts(),
                    "projects": get_projects(),
                    "subaccounts": get_subaccounts(),
                    "vendors": get_vendors(),
                    "form_data": form_data,
                    "error": "<br>".join(errors),
                    "transaction": tx,
                    "is_edit": True,
                    "edit_id": transaction_id,
                }
            )

        # ─── Update logic ────────────────────────────────────────────────────
        with get_db() as conn:
            # Main account name
            main_row = conn.execute(
                "SELECT account_name FROM chart_of_accounts WHERE account_code = ?",
                (main_account_code.strip(),)
            ).fetchone()

            if not main_row:
                return templates.TemplateResponse(
                    "add_transaction.html",
                    {
                        "request": request,
                        "main_accounts": get_main_accounts(),
                        "projects": get_projects(),
                        "subaccounts": get_subaccounts(),
                        "form_data": form_data,
                        "error": f"Main account code '{main_account_code}' not found",
                        "transaction": {"id": transaction_id},
                        "is_edit": True,
                        "edit_id": transaction_id,
                    }
                )

            main_account_name = main_row["account_name"]

            # Sub account name (optional)
            sub_account_name = None
            if sub_account_code and sub_account_code.strip():
                sub_row = conn.execute(
                    "SELECT sub_account_name FROM subaccounts WHERE sub_account_code = ?",
                    (sub_account_code.strip(),)
                ).fetchone()
                if sub_row:
                    sub_account_name = sub_row["sub_account_name"]

            # Month from date
            month = None
            if date:
                try:
                    _, mm, _ = date.split("-", 2)
                    month = int(mm)
                except:
                    pass

            # ─── UPDATE query ────────────────────────────────────────────────
            conn.execute("""
                UPDATE transactions
                SET 
                    date = ?,
                    pv_number = ?,
                    description = ?,
                    type = ?,
                    amount = ?,
                    month = ?,
                    project = ?,
                    main_account = ?,
                    main_account_code = ?,
                    sub_account = ?,
                    sub_account_code = ?,
                    wht_applied = ?,
                    wht_rate = ?,
                    wht_amount = ?,
                    net_amount = ?,
                    vendor_tin = ?,
                    vendor_account_name = ?
                WHERE id = ?
            """, (
                date.strip(),
                pv_number.strip() if pv_number else None,
                description.strip(),
                type.strip(),
                amount,
                month,
                project.strip() if project else None,
                main_account_name,
                main_account_code.strip(),
                sub_account_name,
                sub_account_code.strip() if sub_account_code else None,
                wht_applied_flag,
                wht_rate_pct,
                wht_amount,
                net_amount,
                vendor_tin.strip() if vendor_tin else None,
                vendor_account_details.strip() if vendor_account_details else None,
                transaction_id
            ))

            conn.commit()

        return RedirectResponse("/transactions?success=updated", status_code=303)
    
    # Handle GET request - display the form
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 
                id, date, pv_number, description, type, amount,
                project, main_account_code, sub_account_code,
                wht_applied, wht_rate, wht_amount, net_amount,
                vendor_tin, vendor_account_name
            FROM transactions 
            WHERE id = ?
            """,
            (transaction_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")

        tx = dict(row)

    form_data = {
        "date": tx.get("date", ""),
        "pv_number": tx.get("pv_number", ""),
        "description": tx.get("description", ""),
        "type": tx.get("type", "Expense"),
        "gross_amount": f"{tx.get('amount', 0):.2f}",
        "project": tx.get("project", ""),
        "main_account_code": tx.get("main_account_code", ""),
        "sub_account_code": tx.get("sub_account_code", ""),
        "vendor_tin": tx.get("vendor_tin", ""),
        "vendor_account_details": tx.get("vendor_account_name", ""),
        "wht_applied": "on" if tx.get("wht_applied", False) else "off",
        "wht_rate": f"{(tx.get('wht_rate', 0.0) * 100):.2f}",
        "wht_amount": f"{tx.get('wht_amount', 0.0):.2f}",
        "net_amount": f"{tx.get('net_amount', 0.0):.2f}",
    }

    return templates.TemplateResponse(
        "add_transaction.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "projects": get_projects(),
            "subaccounts": get_subaccounts(),
            "vendors": get_vendors(),
            "form_data": form_data,
            "error": None,
            "transaction": tx,
            "is_edit": True,
            "edit_id": transaction_id,
        }
    )

# ─── Update Transaction ──────────────────────────────────────────────────

@app.post("/update-transaction")
async def update_transaction(
    request: Request,
    id: int = Form(...),
    date: str = Form(...),
    pv_number: Optional[str] = Form(None),
    description: str = Form(...),
    type: str = Form(...),
    gross_amount: str = Form(...),
    project: Optional[str] = Form(None),
    main_account_code: str = Form(...),
    sub_account_code: Optional[str] = Form(None),
    vendor_tin: Optional[str] = Form(None),
    vendor_account_details: Optional[str] = Form(None),
    wht_applied: str = Form(default="off"),
    wht_rate: str = Form(default="0.0"),
):
    errors = []
    form_data = {
        "date": date,
        "pv_number": pv_number,
        "description": description,
        "type": type,
        "gross_amount": gross_amount,
        "project": project,
        "main_account_code": main_account_code,
        "sub_account_code": sub_account_code,
        "vendor_tin": vendor_tin,
        "vendor_account_details": vendor_account_details,
        "wht_applied": wht_applied,
        "wht_rate": wht_rate,
    }

    # ─── Validation ──────────────────────────────────────────────────────
    try:
        amount = float(gross_amount.strip().replace(",", ""))
        if amount <= 0:
            errors.append("Amount must be greater than zero")
    except (ValueError, TypeError):
        errors.append("Invalid amount format")

    if not main_account_code.strip():
        errors.append("Main account is required")

    # Withholding tax calculation
    wht_applied_flag = 1 if wht_applied == "on" else 0
    wht_rate_pct = 0.0
    wht_amount = 0.0
    net_amount = amount

    if wht_applied_flag:
        try:
            wht_rate_pct = float(wht_rate.strip() or "0") / 100.0
            if wht_rate_pct < 0 or wht_rate_pct > 1:
                errors.append("WHT rate must be between 0% and 100%")
            else:
                wht_amount = amount * wht_rate_pct
                net_amount = amount - wht_amount
        except (ValueError, TypeError):
            errors.append("Invalid WHT rate format (use numbers only)")

    if errors:
        with get_db() as conn:
            tx = conn.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (id,)
            ).fetchone()

        return templates.TemplateResponse(
            "add_transaction.html",
            {
                "request": request,
                "main_accounts": get_main_accounts(),
                "projects": get_projects(),
                "subaccounts": get_subaccounts(),
                "vendors": get_vendors(),
                "form_data": form_data,
                "error": "<br>".join(errors),
                "transaction": tx,
                "is_edit": True,
                "edit_id": id,
            }
        )

    # ─── Update logic ────────────────────────────────────────────────────
    with get_db() as conn:
        # Main account name
        main_row = conn.execute(
            "SELECT account_name FROM chart_of_accounts WHERE account_code = ?",
            (main_account_code.strip(),)
        ).fetchone()

        if not main_row:
            return templates.TemplateResponse(
                "add_transaction.html",
                {
                    "request": request,
                    "main_accounts": get_main_accounts(),
                    "projects": get_projects(),
                    "subaccounts": get_subaccounts(),
                    "vendors": get_vendors(),
                    "form_data": form_data,
                    "error": f"Main account code '{main_account_code}' not found",
                    "transaction": {"id": id},
                    "is_edit": True,
                    "edit_id": id,
                }
            )

        main_account_name = main_row["account_name"]

        # Sub account name (optional)
        sub_account_name = None
        if sub_account_code and sub_account_code.strip():
            sub_row = conn.execute(
                "SELECT sub_account_name FROM subaccounts WHERE sub_account_code = ?",
                (sub_account_code.strip(),)
            ).fetchone()
            if sub_row:
                sub_account_name = sub_row["sub_account_name"]

        # Month from date
        month = None
        if date:
            try:
                _, mm, _ = date.split("-", 2)
                month = int(mm)
            except:
                pass

        # ─── UPDATE query ────────────────────────────────────────────────
        conn.execute("""
            UPDATE transactions
            SET 
                date = ?,
                pv_number = ?,
                description = ?,
                type = ?,
                amount = ?,
                month = ?,
                project = ?,
                main_account = ?,
                main_account_code = ?,
                sub_account = ?,
                sub_account_code = ?,
                wht_applied = ?,
                wht_rate = ?,
                wht_amount = ?,
                net_amount = ?,
                vendor_tin = ?,
                vendor_account_name = ?
            WHERE id = ?
        """, (
            date.strip(),
            pv_number.strip() if pv_number else None,
            description.strip(),
            type.strip(),
            amount,
            month,
            project.strip() if project else None,
            main_account_name,
            main_account_code.strip(),
            sub_account_name,
            sub_account_code.strip() if sub_account_code else None,
            wht_applied_flag,
            wht_rate_pct,
            wht_amount,
            net_amount,
            vendor_tin.strip() if vendor_tin else None,
            vendor_account_details.strip() if vendor_account_details else None,
            id
        ))

        conn.commit()

    return RedirectResponse("/transactions?success=updated", status_code=303)

# ─── Transactions List ──────────────────────────────────────────────
@app.get("/transactions-page", response_class=HTMLResponse)
async def transactions_page(request: Request):
    transactions = get_transactions()
    success_msg = request.query_params.get("success")
    return templates.TemplateResponse(
        "transactions.html",
        {
            "request": request,
            "transactions": transactions,
            "vendors": get_vendors(),
            "success_msg": success_msg  # optional: "created" or "updated"
        }
    )


# Delete transaction (already good)
@app.post("/delete-transaction/{id}")
async def delete_transaction(id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (id,))
        conn.commit()
    return RedirectResponse("/transactions-page?success=deleted", status_code=303)


# Optional: currency filter (unchanged)
def format_currency(value):
    try:
        return f"₦{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["format_currency"] = format_currency


from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from typing import Any, Dict

# ── Your helper functions (keep them) ──
def safe_float(value: Any) -> float:
    """Convert value to float safely, return 0.0 on failure"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def number_to_ngn_words(amount: float) -> str:
    """Simple Naira amount to words (supports up to millions, no kobo for simplicity)"""
    if amount == 0:
        return "Zero Naira Only"
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million"]

    def helper(n: int) -> str:
        if n == 0:
            return ""
        if n < 10:
            return units[n]
        if n < 20:
            return teens[n - 10]
        if n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 else "")
        if n < 1000:
            return units[n // 100] + " Hundred" + (" " + helper(n % 100) if n % 100 else "")
        for i, scale in enumerate(scales[1:], 1):
            divider = 1000 ** i
            if n < divider * 1000:
                return helper(n // divider) + " " + scale + (" " + helper(n % divider) if n % divider else "")
        return ""

    whole = int(amount)
    words = helper(whole).strip()
    if not words:
        words = "Zero"

    kobo = int(round((amount - whole) * 100))
    if kobo > 0:
        return f"{words} Naira and {helper(kobo)} Kobo Only"
    
    return f"{words} Naira Only"


# ── ONLY THIS ENDPOINT REMAINS ──
# We renamed it to the main path /voucher/{id}
# It now returns HTML (printable directly from browser)


from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import traceback

@app.get("/voucher/{transaction_id}", response_class=HTMLResponse)
async def view_voucher(transaction_id: int):
    try:
        with get_db() as conn:
            row = conn.execute("""
                SELECT
                    id,
                    date,
                    pv_number,
                    reference,
                    description,
                    type,
                    amount,
                    wht_applied,
                    wht_rate,
                    project,
                    main_account,
                    main_account_code,
                    sub_account,
                    sub_account_code
                FROM transactions
                WHERE id = ?
            """, (transaction_id,)).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Transaction not found")

            tx = dict(row)

        gross_amount = safe_float(tx.get("amount", 0))
        wht_applied  = bool(safe_float(tx.get("wht_applied", 0)))
        wht_rate     = safe_float(tx.get("wht_rate", 0.0))
        wht_amount   = gross_amount * wht_rate if wht_applied else 0.0
        net_amount   = gross_amount - wht_amount

        gross_str = f"₦{gross_amount:,.2f}"
        wht_str   = f"₦{wht_amount:,.2f}" if wht_applied and wht_amount > 0 else "₦0.00"
        net_str   = f"₦{net_amount:,.2f}"

        amount_in_words = number_to_ngn_words(net_amount)

        payee = tx.get("reference") or tx.get("payee") or "Not specified"
        payee_tin = tx.get("payee_tin") or tx.get("vendor_tin") or "—"

        context = {
            "tx": tx,
            "organization": "CARE INTERNATIONAL",
            "voucher_title": "PAYMENT VOUCHER" if tx.get("type") == "Expense" else "RECEIPT VOUCHER",
            "pv_number": tx.get("pv_number") or f"PV-{tx['id']:04d}",
            "date": tx.get("date", "—"),
            "description": tx.get("description", "—"),
            "project": tx.get("project", "—"),
            "payee": payee,
            "payee_tin": payee_tin,
            "main_account_code": tx.get("main_account_code", "—"),
            "main_account": tx.get("main_account", "—"),
            "sub_account_code": tx.get("sub_account_code", "—"),
            "sub_account": tx.get("sub_account", "—"),
            "gross_amount_formatted": gross_str,
            "wht_applied": wht_applied,
            "wht_rate_percent": f"{wht_rate * 100:.1f}" if wht_applied else "0.0",
            "wht_amount_formatted": wht_str,
            "net_amount_formatted": net_str,
            "net_amount_in_words": amount_in_words,
            "prepared_by": "Jude Oko-Oboh",
            "approved_by": "Abba Umar",
        }

        html_content = templates.get_template("payment-voucher-print.html").render(context)

        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Disposition": f"inline; filename=\"voucher-{context['pv_number']}.html\""
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()  # prints full stack trace to console
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load voucher: {str(e)}"
        )

@app.get("/ledger", response_class=HTMLResponse)
async def ledger_page(request: Request):
    with get_db() as conn:
        # Get all transactions with some basic aggregation
        transactions = conn.execute("""
            SELECT 
                id, date, main_account as account_name, description, type, amount,
                project, pv_number
            FROM transactions 
            ORDER BY date DESC, id DESC
        """).fetchall()

        # Optional: simple totals
        totals = conn.execute("""
            SELECT 
                SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) as total_expense
            FROM transactions
        """).fetchone()

    return templates.TemplateResponse(
        "ledger.html",
        {
            "request": request,
            "transactions": transactions,
            "total_income": totals["total_income"] or 0,
            "total_expense": totals["total_expense"] or 0,
            "net_balance": (totals["total_income"] or 0) - (totals["total_expense"] or 0),
        }
    )

@app.get("/trial-balance", response_class=HTMLResponse)
async def trial_balance_page(request: Request):
    with get_db() as conn:
        # Group by account and calculate debit/credit balances
        accounts = conn.execute("""
            SELECT 
                main_account as account_name,
                SUM(CASE WHEN type = 'Income' OR type = 'Credit' THEN amount ELSE 0 END) as credit,
                SUM(CASE WHEN type = 'Expense' OR type = 'Debit' THEN amount ELSE 0 END) as debit
            FROM transactions
            GROUP BY main_account
            ORDER BY main_account
        """).fetchall()

        # Totals
        totals = conn.execute("""
            SELECT 
                SUM(CASE WHEN type = 'Income' OR type = 'Credit' THEN amount ELSE 0 END) as total_credit,
                SUM(CASE WHEN type = 'Expense' OR type = 'Debit' THEN amount ELSE 0 END) as total_debit
            FROM transactions
        """).fetchone()

    return templates.TemplateResponse(
        "trial_balance.html",
        {
            "request": request,
            "accounts": accounts,
            "total_debit": totals["total_debit"] or 0,
            "total_credit": totals["total_credit"] or 0,
            "difference": abs((totals["total_debit"] or 0) - (totals["total_credit"] or 0))
        }
    )

@app.get("/income-expenditure", response_class=HTMLResponse)
async def income_expenditure_report(request: Request):
    with get_db() as conn:
        # Income (by account)
        income = conn.execute("""
            SELECT 
                main_account as account_name,
                SUM(amount) as total_income
            FROM transactions
            WHERE type = 'Income'
            GROUP BY main_account
            ORDER BY total_income DESC
        """).fetchall()

        # Expenditure (expenses)
        expenditure = conn.execute("""
            SELECT 
                main_account as account_name,
                SUM(amount) as total_expenditure
            FROM transactions
            WHERE type = 'Expense'
            GROUP BY main_account
            ORDER BY total_expenditure DESC
        """).fetchall()

        # Totals
        totals = conn.execute("""
            SELECT 
                SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END) as grand_income,
                SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) as grand_expenditure
            FROM transactions
        """).fetchone()

    grand_income = totals["grand_income"] or 0
    grand_expenditure = totals["grand_expenditure"] or 0

    return templates.TemplateResponse(
        "income_expenditure.html",
        {
            "request": request,
            "income_items": income,
            "expenditure_items": expenditure,
            "grand_income": grand_income,
            "grand_expenditure": grand_expenditure,
            "surplus_deficit": grand_income - grand_expenditure,
        }
    )

@app.get("/balance-sheet", response_class=HTMLResponse)
async def balance_sheet_page(request: Request):
    with get_db() as conn:
        # Assets (positive balance accounts, e.g. cash, receivables)
        assets = conn.execute("""
            SELECT 
                main_account as account_name,
                SUM(CASE 
                    WHEN type IN ('Income', 'Credit') THEN amount
                    WHEN type IN ('Expense', 'Debit') THEN -amount
                    ELSE 0 
                END) as balance
            FROM transactions
            GROUP BY main_account
            HAVING balance > 0
            ORDER BY main_account
        """).fetchall()

        # Liabilities & Equity (negative or credit-heavy accounts)
        liabilities_equity = conn.execute("""
            SELECT 
                main_account as account_name,
                SUM(CASE 
                    WHEN type IN ('Income', 'Credit') THEN amount
                    WHEN type IN ('Expense', 'Debit') THEN -amount
                    ELSE 0 
                END) as balance
            FROM transactions
            GROUP BY main_account
            HAVING balance <= 0
            ORDER BY main_account
        """).fetchall()

        # Totals
        asset_total = conn.execute("""
            SELECT SUM(CASE 
                WHEN type IN ('Income', 'Credit') THEN amount
                WHEN type IN ('Expense', 'Debit') THEN -amount
                ELSE 0 END)
            FROM transactions
        """).fetchone()[0] or 0

    total_assets = sum([a["balance"] for a in assets if a["balance"] and a["balance"] > 0])
    total_liab_equity = sum([l["balance"] for l in liabilities_equity if l["balance"] and l["balance"] <= 0])

    return templates.TemplateResponse(
        "balance_sheet.html",
        {
            "request": request,
            "assets": assets,
            "liabilities_equity": liabilities_equity,
            "total_assets": total_assets,
            "total_liab_equity": abs(total_liab_equity),
            "net_difference": total_assets - abs(total_liab_equity),
        }
    )

@app.get("/bank-reconciliation", response_class=HTMLResponse)
async def bank_reconciliation_page(request: Request):
    return templates.TemplateResponse(
        "bank_reconciliation.html",
        {
            "request": request,
        }
    )

# ─── Budget Management ──────────────────────────────────────────────
from fastapi import Request
from fastapi.responses import HTMLResponse

@app.get("/budget", response_class=HTMLResponse)
async def budget_page(request: Request):
    with get_db() as conn:
        budgets = conn.execute("""
            SELECT id, project, account_code, account_name, 
                   subaccount_code, subaccount_name, detail,
                   quantity, unit_cost, periods, total
            FROM budgets
            ORDER BY project, account_code
        """).fetchall()

        grand_total = conn.execute(
            "SELECT SUM(total) FROM budgets"
        ).fetchone()[0] or 0

    # Read query parameter safely
    success_msg = request.query_params.get("success")
    projects = get_projects()

    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": budgets,
            "grand_total": grand_total,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "projects": projects,
            "success_msg": success_msg,   # "added", "updated", etc.
            "form_data": {},              # or load from session/query if needed
            "error": None
        }
    )

from fastapi.responses import RedirectResponse
from fastapi import Form, HTTPException
import json

@app.post("/add-budget")
async def add_budget(
    project: str = Form(...),
    account_code: str = Form(...),
    # ... all other fields you have in the form ...
    quantity: float = Form(...),
    unit_cost: float = Form(...),
    periods: int = Form(...),
):
    try:
        total = quantity * unit_cost * periods
        
        with get_db() as conn:
            # You probably want to fetch account_name & subaccount_name from accounts tables
            # For simplicity assuming they're passed or looked up
            conn.execute("""
                INSERT INTO budgets (
                    project, account_code, account_name, subaccount_code, subaccount_name,
                    detail, quantity, unit_cost, periods, total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project, account_code, "Account Name", None, None,  # ← improve this
                "Some detail", quantity, unit_cost, periods, total
            ))
            conn.commit()

        return RedirectResponse(
            url="/budget?success=added",
            status_code=303
        )

    except Exception as e:
        # Option A: Redirect back with error (simple)
        return RedirectResponse(
            url=f"/budget?error={str(e)}",
            status_code=303
        )

        # Option B: Re-render form with errors & preserved data (better UX)
        # form_data = { "project": project, "quantity": quantity, ... }
        # return templates.TemplateResponse("budget.html", {
        #     "request": request,
        #     "error_msg": str(e),
        #     "form_data": form_data,
        #     # ... other context ...
        # })

@app.get("/edit-budget/{budget_id}", response_class=HTMLResponse)
async def edit_budget_form(request: Request, budget_id: int):
    with get_db() as conn:
        budget = conn.execute("""
            SELECT * FROM budgets WHERE id = ?
        """, (budget_id,)).fetchone()

        if not budget:
            raise HTTPException(status_code=404, detail="Budget line not found")

    projects = get_projects()
    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": conn.execute("SELECT * FROM budgets ORDER BY project, account_code").fetchall(),
            "grand_total": conn.execute("SELECT SUM(total) FROM budgets").fetchone()[0] or 0,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "projects": projects,
            "form_data": dict(budget),  # pre-fill form with existing data
            "error": None,
            "editing_id": budget_id     # to show edit mode in template
        }
    )


@app.post("/update-budget")
async def update_budget(
    request: Request,
    id: int = Form(...),
    project: str = Form(...),
    account_code: str = Form(...),
    account_name: str = Form(...),
    subaccount_code: Optional[str] = Form(None),
    subaccount_name: Optional[str] = Form(None),
    detail: str = Form(...),
    quantity: float = Form(...),
    unit_cost: float = Form(...),
    periods: int = Form(...),
):
    errors = []
    if quantity <= 0:
        errors.append("Quantity must be greater than zero")
    if unit_cost <= 0:
        errors.append("Unit cost must be greater than zero")
    if periods <= 0:
        errors.append("Periods must be greater than zero")

    total = quantity * unit_cost * periods

    if errors:
        with get_db() as conn:
            budget = conn.execute("SELECT * FROM budgets WHERE id = ?", (id,)).fetchone()
            budgets = conn.execute("SELECT * FROM budgets ORDER BY project, account_code").fetchall()
            grand_total = conn.execute("SELECT SUM(total) FROM budgets").fetchone()[0] or 0

        return templates.TemplateResponse(
            "budget.html",
            {
                "request": request,
                "budgets": budgets,
                "grand_total": grand_total,
                "main_accounts": get_main_accounts(),
                "subaccounts": get_subaccounts(),
                "form_data": {
                    "id": id,
                    "project": project,
                    "account_code": account_code,
                    "account_name": account_name,
                    "subaccount_code": subaccount_code,
                    "subaccount_name": subaccount_name,
                    "detail": detail,
                    "quantity": quantity,
                    "unit_cost": unit_cost,
                    "periods": periods,
                },
                "editing_id": id,
                "error": "<br>".join(errors)
            }
        )

    with get_db() as conn:
        try:
            conn.execute("""
                UPDATE budgets
                SET project = ?, account_code = ?, account_name = ?,
                    subaccount_code = ?, subaccount_name = ?, detail = ?,
                    quantity = ?, unit_cost = ?, periods = ?, total = ?
                WHERE id = ?
            """, (
                project.strip(),
                account_code.strip(),
                account_name.strip(),
                subaccount_code.strip() if subaccount_code else None,
                subaccount_name.strip() if subaccount_name else None,
                detail.strip(),
                quantity,
                unit_cost,
                periods,
                total,
                id
            ))
            conn.commit()
            return RedirectResponse("/budget?success=updated", status_code=303)

        except Exception as e:
            budgets = conn.execute("SELECT * FROM budgets ORDER BY project, account_code").fetchall()
            grand_total = conn.execute("SELECT SUM(total) FROM budgets").fetchone()[0] or 0

            return templates.TemplateResponse(
                "budget.html",
                {
                    "request": request,
                    "budgets": budgets,
                    "grand_total": grand_total,
                    "main_accounts": get_main_accounts(),
                    "subaccounts": get_subaccounts(),
                    "form_data": {
                        "id": id,
                        "project": project,
                        "account_code": account_code,
                        "account_name": account_name,
                        "subaccount_code": subaccount_code,
                        "subaccount_name": subaccount_name,
                        "detail": detail,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "periods": periods,
                    },
                    "editing_id": id,
                    "error": f"Error updating budget: {str(e)}"
                }
            )


@app.post("/delete-budget/{budget_id}")
async def delete_budget(budget_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        conn.commit()
    return RedirectResponse("/budget?success=deleted", status_code=303)

# ─────────────────────────────────────────────
# BUDGET REPORT & BVA REPORT
# ─────────────────────────────────────────────

from fastapi.responses import HTMLResponse
import sqlite3


# ---------- PRINT BUDGET REPORT ----------
@app.get("/print-budget", response_class=HTMLResponse)
async def print_budget(request: Request):
    with get_db() as conn:
        budgets = conn.execute("SELECT * FROM budgets ORDER BY project, account_code, subaccount_code").fetchall()
        grand_total = conn.execute("SELECT IFNULL(SUM(total), 0) AS total FROM budgets").fetchone()[0] or 0

    return templates.TemplateResponse(
        "print_budget.html",
        {
            "request": request,
            "budgets": budgets,
            "grand_total": grand_total
        }
    )


# ---------- GENERATE BVA REPORT ----------
@app.get("/generate-bva")
async def generate_bva():
    # No side table necessary: redirect to print-bva, which calculates current BVA
    return RedirectResponse("/print-bva", status_code=303)


# ---------- PRINT BVA REPORT ----------
@app.get("/print-bva", response_class=HTMLResponse)
async def print_bva(request: Request):
    with get_db() as conn:
        bva_rows = conn.execute("""
            SELECT
                b.project AS category_project,
                b.account_code AS category_account_code,
                b.account_name AS category_account_name,
                b.subaccount_code,
                b.subaccount_name,
                b.detail,
                SUM(b.total) AS budget_total,
                IFNULL(SUM(t.amount), 0) AS actual_total,
                SUM(b.total) - IFNULL(SUM(t.amount), 0) AS variance_total,
                CASE
                    WHEN SUM(b.total) = 0 THEN 0
                    ELSE ROUND((SUM(b.total) - IFNULL(SUM(t.amount), 0)) / SUM(b.total) * 100, 2)
                END AS variance_pct
            FROM budgets b
            LEFT JOIN transactions t ON b.project = t.project AND b.account_code = t.main_account_code
            GROUP BY b.project, b.account_code, b.subaccount_code, b.detail
            ORDER BY b.project, b.account_code
        """).fetchall()

    return templates.TemplateResponse(
        "print_bva.html",
        {
            "request": request,
            "bva_rows": bva_rows
        }
    )

# ─── Projects Management ─────────────────────────────────────────────

@app.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    """Show list of all projects"""
    with get_db() as conn:
        projects = conn.execute("""
            SELECT id, project_name, donor, sector, budget, start_date, end_date 
            FROM projects 
            WHERE is_active = 1
            ORDER BY project_name
        """).fetchall()

    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "projects": projects
        }
    )


@app.get("/projects-report", response_class=HTMLResponse)
async def projects_report(request: Request):
    """Show projects report with budget breakdown pie chart"""
    with get_db() as conn:
        projects = conn.execute("""
            SELECT id, project_name, donor, sector, budget, start_date, end_date 
            FROM projects 
            WHERE is_active = 1 AND budget > 0
            ORDER BY budget DESC
        """).fetchall()
        
        # Calculate total budget
        total_budget = conn.execute("""
            SELECT SUM(budget) as total FROM projects WHERE is_active = 1
        """).fetchone()['total'] or 0

    # Convert to dict list and add percentage
    projects_list_with_percent = []
    for p in projects:
        project_dict = dict(p)
        percentage = (project_dict['budget'] / total_budget * 100) if total_budget > 0 else 0
        project_dict['percentage'] = round(percentage, 2)
        projects_list_with_percent.append(project_dict)

    return templates.TemplateResponse(
        "projects_report.html",
        {
            "request": request,
            "projects": projects_list_with_percent,
            "total_budget": total_budget
        }
    )


@app.get("/add-project", response_class=HTMLResponse)
async def add_project_form(request: Request):
    """Show form to add new project"""
    return templates.TemplateResponse(
        "project_form.html",
        {
            "request": request,
            "project": None,  # new project
            "error": None
        }
    )


@app.post("/add-project")
async def create_project(
    project_name: str = Form(...),
    donor: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    sector: Optional[str] = Form(None),
    budget: Optional[str] = Form(None),
):
    errors = []
    if not project_name.strip():
        errors.append("Project name is required")

    # Validate budget if provided
    budget_float = None
    if budget:
        try:
            budget_float = float(budget.strip().replace(",", ""))
            if budget_float < 0:
                errors.append("Budget must be a positive number")
        except (ValueError, TypeError):
            errors.append("Invalid budget amount")

    if errors:
        return templates.TemplateResponse(
            "project_form.html",
            {
                "request": request,
                "project": {
                    "project_name": project_name,
                    "donor": donor,
                    "start_date": start_date,
                    "end_date": end_date,
                    "sector": sector,
                    "budget": budget
                },
                "error": "<br>".join(errors)
            }
        )

    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO projects (project_name, donor, start_date, end_date, sector, budget, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                project_name.strip(),
                donor.strip() if donor else None,
                start_date.strip() if start_date else None,
                end_date.strip() if end_date else None,
                sector.strip() if sector else None,
                budget_float
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            return templates.TemplateResponse(
                "project_form.html",
                {
                    "request": request,
                    "project": {
                        "project_name": project_name,
                        "donor": donor,
                        "start_date": start_date,
                        "end_date": end_date,
                        "sector": sector,
                        "budget": budget
                    },
                    "error": "Project name already exists"
                }
            )
        except Exception as e:
            return templates.TemplateResponse(
                "project_form.html",
                {
                    "request": request,
                    "project": {
                        "project_name": project_name,
                        "donor": donor,
                        "start_date": start_date,
                        "end_date": end_date,
                        "sector": sector,
                        "budget": budget
                    },
                    "error": f"Error creating project: {str(e)}"
                }
            )

    return RedirectResponse("/projects?success=added", status_code=303)


@app.get("/edit-project/{project}", response_class=HTMLResponse)
async def edit_project_form(request: Request, project: int):
    """Show form to edit existing project"""
    with get_db() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project,)
        ).fetchone()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    return templates.TemplateResponse(
        "project_form.html",
        {
            "request": request,
            "project": project,
            "error": None
        }
    )


@app.post("/edit-project/{project}")
async def update_project(
    project: int,
    project_name: str = Form(...),
    donor: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    sector: Optional[str] = Form(None),
    budget: Optional[str] = Form(None),
):
    errors = []
    if not project_name.strip():
        errors.append("Project name is required")

    # Validate budget if provided
    budget_float = None
    if budget:
        try:
            budget_float = float(budget.strip().replace(",", ""))
            if budget_float < 0:
                errors.append("Budget must be a positive number")
        except (ValueError, TypeError):
            errors.append("Invalid budget amount")

    if errors:
        with get_db() as conn:
            project_data = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project,)
            ).fetchone()

        return templates.TemplateResponse(
            "project_form.html",
            {
                "request": request,
                "project": {
                    "id": project,
                    "project_name": project_name,
                    "donor": donor,
                    "start_date": start_date,
                    "end_date": end_date,
                    "sector": sector,
                    "budget": budget
                },
                "error": "<br>".join(errors)
            }
        )

    with get_db() as conn:
        try:
            conn.execute("""
                UPDATE projects
                SET project_name = ?, donor = ?, start_date = ?, end_date = ?, sector = ?, budget = ?
                WHERE id = ?
            """, (
                project_name.strip(),
                donor.strip() if donor else None,
                start_date.strip() if start_date else None,
                end_date.strip() if end_date else None,
                sector.strip() if sector else None,
                budget_float,
                project
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            return templates.TemplateResponse(
                "project_form.html",
                {
                    "request": request,
                    "project": {
                        "id": project,
                        "project_name": project_name,
                        "donor": donor,
                        "start_date": start_date,
                        "end_date": end_date,
                        "sector": sector,
                        "budget": budget
                    },
                    "error": "Project name already exists"
                }
            )
        except Exception as e:
            return templates.TemplateResponse(
                "project_form.html",
                {
                    "request": request,
                    "project": {
                        "id": project,
                        "project_name": project_name,
                        "donor": donor,
                        "start_date": start_date,
                        "end_date": end_date,
                        "sector": sector,
                        "budget": budget
                    },
                    "error": f"Error updating project: {str(e)}"
                }
            )


    return RedirectResponse("/projects?success=updated", status_code=303)


@app.post("/delete-project/{project_id}")
async def delete_project(project_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    return RedirectResponse("/projects?success=deleted", status_code=303)


from fastapi import Request
from fastapi.responses import HTMLResponse

@app.get("/transactions", response_class=HTMLResponse)
@app.get("/transactions-page", response_class=HTMLResponse)  # optional alias
async def list_transactions(request: Request):
    transactions = get_transactions()

    # Optional: get success/error messages from query params (after redirect)
    success_msg = request.query_params.get("success")
    error_msg   = request.query_params.get("error")

    return templates.TemplateResponse(
        "transactions.html",
        {
            "request":      request,
            "transactions": transactions,
            "vendors": get_vendors(),
            "success_msg":  success_msg,
            "error_msg":    error_msg
        }
    )

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

# ─── Vendors List ────────────────────────────────────────────────
@app.get("/vendors", response_class=HTMLResponse)
async def vendors_list(request: Request):
    with get_db() as conn:
        vendors = conn.execute("""
            SELECT id, name, tin, phone, email, address, 
                   account_number, bank_name, is_active
            FROM vendors
            ORDER BY name ASC
        """).fetchall()

    return templates.TemplateResponse(
        "vendors.html",
        {
            "request": request,
            "vendors": vendors,
            "success_msg": request.query_params.get("success"),
            "error_msg": request.query_params.get("error"),
        }
    )

# ─── Add Vendor ──────────────────────────────────────────────────
@app.get("/vendors/add", response_class=HTMLResponse)
async def add_vendor_form(request: Request):
    return templates.TemplateResponse("vendor_form.html", {
        "request": request,
        "is_edit": False,
        "vendor": {},
    })

@app.post("/vendors/add")
async def add_vendor(
    name: str = Form(...),
    tin: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
):
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO vendors (name, tin, phone, email, address, account_number, bank_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name.strip(), tin, phone, email, address, account_number, bank_name))
            conn.commit()

        return RedirectResponse(url="/vendors?success=Vendor+added+successfully", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/vendors?error={str(e)}", status_code=303)

# ─── Edit Vendor ─────────────────────────────────────────────────
@app.get("/vendors/edit/{vendor_id}", response_class=HTMLResponse)
async def edit_vendor_form(request: Request, vendor_id: int):
    with get_db() as conn:
        vendor = conn.execute("""
            SELECT * FROM vendors WHERE id = ?
        """, (vendor_id,)).fetchone()

        if not vendor:
            raise HTTPException(404, "Vendor not found")

    return templates.TemplateResponse("vendor_form.html", {
        "request": request,
        "is_edit": True,
        "vendor": vendor,
    })

@app.post("/vendors/edit/{vendor_id}")
async def update_vendor(
    vendor_id: int,
    name: str = Form(...),
    tin: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
):
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE vendors
                SET name = ?, tin = ?, phone = ?, email = ?, 
                    address = ?, account_number = ?, bank_name = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (name.strip(), tin, phone, email, address, account_number, bank_name, vendor_id))
            conn.commit()

        return RedirectResponse(url="/vendors?success=Vendor+updated+successfully", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/vendors?error={str(e)}", status_code=303)



# â”€â”€â”€ PASSWORD MANAGEMENT ROUTES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Change Password Route
@app.post("/vendors/delete/{vendor_id}")
async def delete_vendor(vendor_id: int):
    try:
        with get_db() as conn:
            vendor = conn.execute("SELECT name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if not vendor:
                raise HTTPException(404, "Vendor not found")
            
            conn.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
            conn.commit()
        
        return RedirectResponse(url=f"/vendors?success=Vendor+deleted+successfully", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/vendors?error=Unable+to+delete+vendor", status_code=303)


@app.get("/vendors/{vendor_id}", response_class=HTMLResponse)
async def view_vendor_details(request: Request, vendor_id: int):
    with get_db() as conn:
        vendor = conn.execute("""
            SELECT * FROM vendors WHERE id = ?
        """, (vendor_id,)).fetchone()
        
        if not vendor:
            raise HTTPException(404, "Vendor not found")
        
        # Convert Row to dict for template
        vendor_dict = dict(vendor)
        
        transactions = conn.execute("""
            SELECT id, date, pv_number, description, amount, type
            FROM transactions
            WHERE vendor_account_name = ? OR vendor_tin = ?
            ORDER BY date DESC
            LIMIT 10
        """, (vendor_dict['name'], vendor_dict.get('tin', ''))).fetchall()
        
        # Convert transactions to dicts
        transactions_list = [dict(tx) for tx in transactions]
        
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(amount) as total_spent
            FROM transactions
            WHERE vendor_account_name = ? OR vendor_tin = ?
        """, (vendor_dict['name'], vendor_dict.get('tin', ''))).fetchone()
        
        stats_dict = dict(stats) if stats else {"total_transactions": 0, "total_spent": 0}

    return templates.TemplateResponse(
        "vendor_detail.html",
        {
            "request": request,
            "vendor": vendor_dict,
            "transactions": transactions_list,
            "stats": stats_dict
        }
    )


@app.get("/vendors/search", response_class=HTMLResponse)
async def search_vendors(request: Request, q: str = ""):
    with get_db() as conn:
        if q.strip():
            vendors = conn.execute("""
                SELECT id, name, tin, phone, email, address, 
                       account_number, bank_name, is_active
                FROM vendors
                WHERE name LIKE ? OR tin LIKE ? OR phone LIKE ? OR email LIKE ?
                ORDER BY name ASC
            """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        else:
            vendors = []

    return templates.TemplateResponse(
        "vendors.html",
        {
            "request": request,
            "vendors": vendors,
            "search_query": q,
            "success_msg": None,
            "error_msg": None,
        }
    )


# Change Password Route
@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    """Display change password form"""
    return templates.TemplateResponse(
        "change_password.html",
        {
            "request": request,
            "error": None,
            "success": None
        }
    )


@app.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Handle password change"""
    errors = []

    if not current_password:
        errors.append("Current password is required")

    if new_password != confirm_password:
        errors.append("New passwords do not match")

    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        errors.append(msg)

    if errors:
        return templates.TemplateResponse(
            "change_password.html",
            {
                "request": request,
                "error": "<br>".join(errors),
                "success": None
            }
        )

    # Get username from request (you'll need to implement proper session management)
    current_username = request.cookies.get("username", "admin")
    
    with get_db() as conn:
        user = conn.execute(
            "SELECT password FROM users WHERE username = ?",
            (current_username,)
        ).fetchone()

        if not user:
            return templates.TemplateResponse(
                "change_password.html",
                {
                    "request": request,
                    "error": "User not found",
                    "success": None
                }
            )

        if not verify_password(current_password, user["password"]):
            return templates.TemplateResponse(
                "change_password.html",
                {
                    "request": request,
                    "error": "Current password is incorrect",
                    "success": None
                }
            )

        try:
            hashed_new_password = hash_password(new_password)
            conn.execute(
                """
                UPDATE users 
                SET password = ?, last_password_change = ?, updated_at = ?
                WHERE username = ?
                """,
                (hashed_new_password, datetime.now().isoformat(), datetime.now().isoformat(), current_username)
            )
            conn.commit()

            return templates.TemplateResponse(
                "change_password.html",
                {
                    "request": request,
                    "error": None,
                    "success": "âœ“ Password changed successfully!"
                }
            )
        except Exception as e:
            return templates.TemplateResponse(
                "change_password.html",
                {
                    "request": request,
                    "error": f"Error updating password: {str(e)}",
                    "success": None
                }
            )


# Forgot Password Route
@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Display forgot password form"""
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "error": None,
            "success": None
        }
    )


@app.post("/forgot-password")
async def forgot_password(
    username: str = Form(...),
):
    """Handle forgot password request"""
    if not username:
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error": "Username is required",
                "success": None
            }
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, email, is_active FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if not user or user.get("is_active") == 0:
            return templates.TemplateResponse(
                "forgot_password.html",
                {
                    "request": request,
                    "error": None,
                    "success": "âœ“ If active account exists, reset instructions sent to email"
                }
            )

        reset_token = generate_reset_token()
        reset_expiry = (datetime.now() + timedelta(hours=24)).isoformat()

        try:
            conn.execute(
                """
                UPDATE users 
                SET password_reset_token = ?, reset_token_expiry = ?
                WHERE username = ?
                """,
                (reset_token, reset_expiry, username)
            )
            conn.commit()

            # Token displayed for testing (in production, send via email)
            return templates.TemplateResponse(
                "forgot_password.html",
                {
                    "request": request,
                    "error": None,
                    "success": f"âœ“ Reset token generated: {reset_token[:20]}... (use with /reset-password?token=...)"
                }
            )
        except Exception as e:
            return templates.TemplateResponse(
                "forgot_password.html",
                {
                    "request": request,
                    "error": f"Error: {str(e)}",
                    "success": None
                }
            )


# Reset Password Route
@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: Optional[str] = None):
    """Display reset password form"""
    if not token:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": "",
                "error": "Invalid reset token",
                "success": None
            }
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT username FROM users WHERE password_reset_token = ? AND reset_token_expiry > ?",
            (token, datetime.now().isoformat())
        ).fetchone()

        if not user:
            return templates.TemplateResponse(
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "error": "Invalid or expired reset token",
                    "success": None
                }
            )

    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "token": token,
            "error": None,
            "success": None
        }
    )


@app.post("/reset-password")
async def confirm_reset_password(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Confirm password reset"""
    errors = []

    if not token:
        errors.append("Reset token is missing")

    if new_password != confirm_password:
        errors.append("Passwords do not match")

    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        errors.append(msg)

    if errors:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "error": "<br>".join(errors),
                "success": None
            }
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT username FROM users WHERE password_reset_token = ? AND reset_token_expiry > ?",
            (token, datetime.now().isoformat())
        ).fetchone()

        if not user:
            return templates.TemplateResponse(
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "error": "Invalid or expired reset token",
                    "success": None
                }
            )

        try:
            hashed_password = hash_password(new_password)
            conn.execute(
                """
                UPDATE users 
                SET password = ?, 
                    password_reset_token = NULL, 
                    reset_token_expiry = NULL,
                    last_password_change = ?,
                    updated_at = ?
                WHERE username = ?
                """,
                (hashed_password, datetime.now().isoformat(), datetime.now().isoformat(), user["username"])
            )
            conn.commit()

            return templates.TemplateResponse(
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "error": None,
                    "success": "âœ“ Password reset successfully! Please login with your new password."
                }
            )
        except Exception as e:
            return templates.TemplateResponse(
                "reset_password.html",
                {
                    "request": request,
                    "token": token,
                    "error": f"Error: {str(e)}",
                    "success": None
                }
            )


# â”€â”€â”€ ADMIN USER MANAGEMENT ROUTES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def check_admin_access(request: Request) -> tuple[bool, str]:
    """Check if user is logged in as admin."""
    current_role = request.cookies.get("user_role", "").lower()
    current_username = request.cookies.get("username")
    
    if not current_username or current_role != "admin":
        return False, "Access denied. Admin privileges required."
    return True, ""


def check_audit_access(request: Request) -> tuple[bool, str]:
    """Check if user is logged in as auditor."""
    current_role = request.cookies.get("user_role", "").lower()
    current_username = request.cookies.get("username")
    
    if not current_username or current_role != "audit":
        return False, "Access denied. Audit privileges required."
    return True, ""


def check_role_access(request: Request, allowed_roles: list) -> tuple[bool, str]:
    """Check if user has one of the allowed roles."""
    current_role = request.cookies.get("user_role", "").lower()
    current_username = request.cookies.get("username")
    
    if not current_username:
        return False, "Authentication required."
    
    if current_role not in [role.lower() for role in allowed_roles]:
        return False, f"Access denied. Required roles: {', '.join(allowed_roles)}"
    return True, ""


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Display user management page (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    success_message = request.query_params.get("success")
    error_message = request.query_params.get("error")
    
    with get_db() as conn:
        users = conn.execute(
            "SELECT id, username, email, role, is_active FROM users ORDER BY role, username"
        ).fetchall()
    
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "users": [dict(u) for u in users],
            "success": success_message,
            "error": error_message
        }
    )


@app.post("/admin/assign-role")
async def assign_role(request: Request, username: str = Form(...), role: str = Form(...)):
    """Assign role to existing user (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    valid_roles = ['admin', 'finance', 'audit']
    if role not in valid_roles:
        return RedirectResponse(url="/admin/users?error=Invalid+role", status_code=303)
    
    try:
        conn = get_db()
        try:
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user:
                conn.close()
                return RedirectResponse(url="/admin/users?error=User+not+found", status_code=303)
            
            conn.execute(
                "UPDATE users SET role = ?, updated_at = datetime('now') WHERE username = ?",
                (role, username)
            )
            conn.commit()
        finally:
            conn.close()
        
        return RedirectResponse(
            url="/admin/users?success=Role+assigned+to+" + username,
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)


@app.post("/admin/toggle-user")
async def toggle_user_status(request: Request, username: str = Form(...)):
    """Activate/Deactivate user (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    try:
        conn = get_db()
        try:
            user = conn.execute(
                "SELECT id, is_active FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            
            if not user:
                conn.close()
                return RedirectResponse(url="/admin/users?error=User+not+found", status_code=303)
            
            new_status = 0 if user["is_active"] == 1 else 1
            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE username = ?",
                (new_status, username)
            )
            conn.commit()
        finally:
            conn.close()
            
        status_text = "activated" if new_status == 1 else "deactivated"
        return RedirectResponse(
            url=f"/admin/users?success=User+{status_text}",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)


@app.post("/admin/create-user")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    email: Optional[str] = Form(None)
):
    """Create new user (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    errors = []
    username = username.strip().lower()
    
    if not username or len(username) < 3:
        errors.append("Username must be at least 3 characters")
    
    valid_roles = ['admin', 'finance', 'audit']
    if role not in valid_roles:
        errors.append("Invalid role selected")
    
    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        errors.append(f"Password: {msg}")
    
    if errors:
        error_text = "+".join(errors)
        return RedirectResponse(url=f"/admin/users?error={error_text}", status_code=303)
    
    try:
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            
            if existing:
                conn.close()
                return RedirectResponse(
                    url="/admin/users?error=Username+already+exists",
                    status_code=303
                )
            
            hashed_pwd = hash_password(password)
            conn.execute(
                """
                INSERT INTO users (username, password, role, email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                """,
                (username, hashed_pwd, role, email or None)
            )
            conn.commit()
        finally:
            conn.close()
        
        return RedirectResponse(
            url=f"/admin/users?success=User+{username}+created+successfully",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)


@app.post("/admin/edit-user")
async def edit_user(
    request: Request,
    username: str = Form(...),
    email: Optional[str] = Form(None),
    role: str = Form(...),
    password: Optional[str] = Form(None)
):
    """Edit user details (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    errors = []
    valid_roles = ['admin', 'finance', 'audit']
    if role not in valid_roles:
        errors.append("Invalid role selected")
    
    if password and password.strip():
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            errors.append(f"Password: {msg}")
    
    if errors:
        error_text = "+".join(errors)
        return RedirectResponse(url=f"/admin/users?error={error_text}", status_code=303)
    
    try:
        conn = get_db()
        try:
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user:
                conn.close()
                return RedirectResponse(url="/admin/users?error=User+not+found", status_code=303)
            
            # Build update query dynamically
            update_fields = ["role = ?", "email = ?", "updated_at = datetime('now')"]
            update_values = [role, email or None]
            
            if password and password.strip():
                update_fields.append("password = ?")
                update_values.append(hash_password(password))
            
            update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE username = ?"
            update_values.append(username)
            
            conn.execute(update_query, update_values)
            conn.commit()
        finally:
            conn.close()
        
        return RedirectResponse(
            url=f"/admin/users?success=User+{username}+updated+successfully",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)


@app.post("/admin/delete-user")
async def delete_user(request: Request, username: str = Form(...)):
    """Delete user (admin only)"""
    is_admin, error_msg = check_admin_access(request)
    if not is_admin:
        return RedirectResponse(url="/login", status_code=303)
    
    # Prevent admin from deleting themselves
    current_username = request.cookies.get("username")
    if username == current_username:
        return RedirectResponse(url="/admin/users?error=Cannot+delete+your+own+account", status_code=303)
    
    try:
        conn = get_db()
        try:
            user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user:
                conn.close()
                return RedirectResponse(url="/admin/users?error=User+not+found", status_code=303)
            
            # Delete the user
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
        finally:
            conn.close()
        
        return RedirectResponse(
            url=f"/admin/users?success=User+{username}+deleted+successfully",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=303)


# ─── AUDIT LOG ROUTES (Audit Role Only) ──────────────────────────────────────

@app.get("/audit", response_class=HTMLResponse)
async def audit_dashboard(request: Request):
    """Audit dashboard - audit role only"""
    is_audit, error_msg = check_audit_access(request)
    if not is_audit:
        return RedirectResponse(url="/login", status_code=303)
    
    current_username = request.cookies.get("username")
    current_role = request.cookies.get("user_role")
    
    # Get audit statistics
    with get_db() as conn:
        total_transactions = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
        recent_transactions = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE date >= date('now', '-30 days')"
        ).fetchone()[0]
    
    return templates.TemplateResponse(
        "audit_dashboard.html",
        {
            "request": request,
            "current_username": current_username,
            "current_role": current_role,
            "total_transactions": total_transactions,
            "total_users": total_users,
            "active_users": active_users,
            "recent_transactions": recent_transactions,
        }
    )


@app.get("/audit/transactions", response_class=HTMLResponse)
async def audit_transaction_log(request: Request):
    """Transaction audit log - audit role only"""
    is_audit, error_msg = check_audit_access(request)
    if not is_audit:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get filter parameters
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")
    user_filter = request.query_params.get("user", "")
    action_filter = request.query_params.get("action", "")
    
    with get_db() as conn:
        # Build query for transaction audit log
        query = """
            SELECT 
                t.id,
                t.date,
                t.pv_number,
                t.reference,
                t.description,
                t.type,
                t.amount,
                t.month,
                t.project,
                t.main_account,
                t.sub_account,
                t.vendor_account_name,
                t.created_at,
                t.updated_at
            FROM transactions t
            ORDER BY t.updated_at DESC, t.created_at DESC
            LIMIT 1000
        """
        
        # Apply filters if provided
        params = []
        if date_from:
            query = query.replace("ORDER BY", f"WHERE t.date >= ? ORDER BY")
            params.append(date_from)
        if date_to and date_from:
            query = query.replace("ORDER BY", f"AND t.date <= ? ORDER BY")
            params.append(date_to)
        elif date_to:
            query = query.replace("ORDER BY", f"WHERE t.date <= ? ORDER BY")
            params.append(date_to)
        
        transactions = conn.execute(query, params).fetchall()
    
    return templates.TemplateResponse(
        "audit_transactions.html",
        {
            "request": request,
            "transactions": [dict(t) for t in transactions],
            "date_from": date_from,
            "date_to": date_to,
            "user_filter": user_filter,
            "action_filter": action_filter,
        }
    )


@app.get("/audit/users", response_class=HTMLResponse)
async def audit_user_activity(request: Request):
    """User activity audit log - audit role only"""
    is_audit, error_msg = check_audit_access(request)
    if not is_audit:
        return RedirectResponse(url="/login", status_code=303)
    
    with get_db() as conn:
        # Get user activity data
        users = conn.execute("""
            SELECT 
                username,
                email,
                role,
                is_active,
                created_at,
                updated_at,
                last_password_change,
                failed_login_attempts
            FROM users
            ORDER BY updated_at DESC, created_at DESC
        """).fetchall()
        
        # Get login activity summary (simplified)
        active_sessions = len([u for u in users if u["is_active"] == 1])
        total_users = len(users)
    
    return templates.TemplateResponse(
        "audit_users.html",
        {
            "request": request,
            "users": [dict(u) for u in users],
            "active_sessions": active_sessions,
            "total_users": total_users,
        }
    )


@app.get("/audit/system", response_class=HTMLResponse)
async def audit_system_log(request: Request):
    """System audit log - audit role only"""
    is_audit, error_msg = check_audit_access(request)
    if not is_audit:
        return RedirectResponse(url="/login", status_code=303)
    
    with get_db() as conn:
        # Get system statistics
        db_stats = {
            "total_transactions": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "total_accounts": conn.execute("SELECT COUNT(*) FROM chart_of_accounts").fetchone()[0],
            "total_subaccounts": conn.execute("SELECT COUNT(*) FROM subaccounts").fetchone()[0],
            "total_projects": conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "total_vendors": conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
            "total_budgets": conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0],
        }
        
        # Get recent system activity (last 30 days)
        recent_activity = {
            "transactions_added": conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE created_at >= date('now', '-30 days')"
            ).fetchone()[0],
            "accounts_modified": conn.execute(
                "SELECT COUNT(*) FROM chart_of_accounts WHERE updated_at >= date('now', '-30 days')"
            ).fetchone()[0],
            "users_modified": conn.execute(
                "SELECT COUNT(*) FROM users WHERE updated_at >= date('now', '-30 days')"
            ).fetchone()[0],
        }
    
    return templates.TemplateResponse(
        "audit_system.html",
        {
            "request": request,
            "db_stats": db_stats,
            "recent_activity": recent_activity,
        }
    )

# ─── PAYROLL MANAGEMENT ROUTES ──────────────────────────────────────

@app.get("/payroll", response_class=HTMLResponse)
async def payroll_dashboard(request: Request):
    """Payroll management dashboard"""
    with get_db() as conn:
        # Get payroll statistics
        stats = {
            "total_employees": conn.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1").fetchone()[0],
            "active_payroll_runs": conn.execute("SELECT COUNT(*) FROM payroll_runs WHERE status IN ('draft', 'processed')").fetchone()[0],
            "total_salary_components": conn.execute("SELECT COUNT(*) FROM salary_components WHERE is_active = 1").fetchone()[0],
            "recent_payroll_runs": conn.execute("""
                SELECT id, payroll_period, status, total_net, pay_date
                FROM payroll_runs
                ORDER BY created_at DESC LIMIT 5
            """).fetchall()
        }

    return templates.TemplateResponse("payroll_dashboard.html", {
        "request": request,
        "stats": stats
    })

@app.get("/employees", response_class=HTMLResponse)
async def employees_list(request: Request):
    """List all employees"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM employees 
            WHERE is_active = 1 
            ORDER BY last_name, first_name
        """).fetchall()
        employees = [normalize_employee_row(row) for row in rows]

    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees
    })

@app.get("/add-employee", response_class=HTMLResponse)
async def add_employee_form(request: Request):
    """Add new employee form"""
    return templates.TemplateResponse("add_employee.html", {"request": request})

@app.post("/add-employee")
async def add_employee(
    request: Request,
    employee_id: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    date_of_birth: str = Form(""),
    hire_date: str = Form(...),
    department: str = Form(""),
    position: str = Form(""),
    employment_type: str = Form("full-time"),
    basic_salary: float = Form(...),
    bank_name: str = Form(""),
    bank_account_number: str = Form(""),
    bank_account_name: str = Form(""),
    tax_id: str = Form(""),
    pension_fund: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form("")
):
    """Add new employee"""
    try:
        with get_db() as conn:
            columns = [
                "employee_id", "first_name", "last_name", "email", "phone", "address",
                "date_of_birth", "hire_date", "department", "position", "employment_type",
                "basic_salary", "bank_name", "bank_account_number", "bank_account_name",
                "tax_id", "pension_fund", "emergency_contact_name", "emergency_contact_phone"
            ]
            values = [
                employee_id, first_name, last_name, email, phone, address,
                date_of_birth, hire_date, department, position, employment_type,
                basic_salary, bank_name, bank_account_number, bank_account_name,
                tax_id, pension_fund, emergency_contact_name, emergency_contact_phone
            ]

            if table_has_column("employees", "full_name"):
                columns.append("full_name")
                values.append(f"{first_name.strip()} {last_name.strip()}".strip())
            if table_has_column("employees", "designation"):
                columns.append("designation")
                values.append(position or "")
            if table_has_column("employees", "monthly_salary"):
                columns.append("monthly_salary")
                values.append(basic_salary)
            if table_has_column("employees", "bank_account"):
                columns.append("bank_account")
                values.append(bank_account_number or "")

            column_list = ", ".join(columns)
            placeholder_list = ", ".join(["?" for _ in columns])
            conn.execute(
                f"INSERT INTO employees ({column_list}) VALUES ({placeholder_list})",
                tuple(values)
            )
            conn.commit()

        return RedirectResponse(url="/employees", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_employee.html", {
            "request": request,
            "error": f"Failed to add employee: {str(e)}"
        })

@app.get("/edit-employee/{employee_id}", response_class=HTMLResponse)
async def edit_employee_form(request: Request, employee_id: str):
    """Edit employee form"""
    with get_db() as conn:
        employee = conn.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee = normalize_employee_row(employee)
    return templates.TemplateResponse("edit_employee.html", {
        "request": request,
        "employee": employee
    })

@app.post("/edit-employee/{employee_id}")
async def edit_employee(
    request: Request,
    employee_id: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    date_of_birth: str = Form(""),
    hire_date: str = Form(...),
    department: str = Form(""),
    position: str = Form(""),
    employment_type: str = Form("full-time"),
    basic_salary: float = Form(...),
    bank_name: str = Form(""),
    bank_account_number: str = Form(""),
    bank_account_name: str = Form(""),
    tax_id: str = Form(""),
    pension_fund: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form("")
):
    """Update employee"""
    try:
        with get_db() as conn:
            update_columns = [
                "first_name = ?", "last_name = ?", "email = ?", "phone = ?", "address = ?",
                "date_of_birth = ?", "hire_date = ?", "department = ?", "position = ?",
                "employment_type = ?", "basic_salary = ?", "bank_name = ?",
                "bank_account_number = ?", "bank_account_name = ?", "tax_id = ?",
                "pension_fund = ?", "emergency_contact_name = ?", "emergency_contact_phone = ?"
            ]
            values = [
                first_name, last_name, email, phone, address, date_of_birth, hire_date,
                department, position, employment_type, basic_salary, bank_name,
                bank_account_number, bank_account_name, tax_id, pension_fund,
                emergency_contact_name, emergency_contact_phone
            ]

            if table_has_column("employees", "full_name"):
                update_columns.append("full_name = ?")
                values.append(f"{first_name.strip()} {last_name.strip()}".strip())
            if table_has_column("employees", "designation"):
                update_columns.append("designation = ?")
                values.append(position or "")
            if table_has_column("employees", "monthly_salary"):
                update_columns.append("monthly_salary = ?")
                values.append(basic_salary)
            if table_has_column("employees", "bank_account"):
                update_columns.append("bank_account = ?")
                values.append(bank_account_number or "")

            update_columns.append("updated_at = datetime('now')")
            sql = f"UPDATE employees SET {', '.join(update_columns)} WHERE employee_id = ?"
            values.append(employee_id)

            conn.execute(sql, tuple(values))
            conn.commit()

        return RedirectResponse(url="/employees", status_code=303)
    except Exception as e:
        with get_db() as conn:
            employee = conn.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
        employee = normalize_employee_row(employee)
        return templates.TemplateResponse("edit_employee.html", {
            "request": request,
            "employee": employee,
            "error": f"Failed to update employee: {str(e)}"
        })

@app.post("/delete-employee/{employee_id}")
async def delete_employee(employee_id: str):
    """Soft delete employee"""
    with get_db() as conn:
        conn.execute("UPDATE employees SET is_active = 0, updated_at = datetime('now') WHERE employee_id = ?", (employee_id,))
        conn.commit()

    return RedirectResponse(url="/employees", status_code=303)

@app.get("/salary-components", response_class=HTMLResponse)
async def salary_components_list(request: Request):
    """List salary components"""
    with get_db() as conn:
        components = conn.execute("""
            SELECT * FROM salary_components 
            WHERE is_active = 1 
            ORDER BY component_type, component_name
        """).fetchall()

    return templates.TemplateResponse("salary_components.html", {
        "request": request,
        "components": components
    })

@app.get("/add-salary-component", response_class=HTMLResponse)
async def add_salary_component_form(request: Request):
    """Add salary component form"""
    return templates.TemplateResponse("add_salary_component.html", {"request": request})

@app.post("/add-salary-component")
async def add_salary_component(
    request: Request,
    component_name: str = Form(...),
    component_type: str = Form(...),
    is_taxable: int = Form(1),
    is_percentage: int = Form(0),
    percentage_value: float = Form(0),
    fixed_amount: float = Form(0),
    description: str = Form("")
):
    """Add salary component"""
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO salary_components (
                    component_name, component_type, is_taxable, is_percentage,
                    percentage_value, fixed_amount, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                component_name, component_type, is_taxable, is_percentage,
                percentage_value, fixed_amount, description
            ))
            conn.commit()

        return RedirectResponse(url="/salary-components", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_salary_component.html", {
            "request": request,
            "error": f"Failed to add salary component: {str(e)}"
        })

@app.get("/employee-salary/{employee_id}", response_class=HTMLResponse)
async def employee_salary_structure(request: Request, employee_id: str):
    """View and manage employee salary structure"""
    with get_db() as conn:
        employee = conn.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee = normalize_employee_row(employee)

        # Get current salary structure
        salary_structure = conn.execute("""
            SELECT ess.*, sc.component_name, sc.component_type, sc.is_taxable
            FROM employee_salary_structure ess
            JOIN salary_components sc ON ess.component_id = sc.id
            WHERE ess.employee_id = ? AND ess.is_active = 1
            ORDER BY sc.component_type, sc.component_name
        """, (employee['id'],)).fetchall()

        # Get available components not yet assigned
        assigned_component_ids = [str(row['component_id']) for row in salary_structure]
        available_components = conn.execute("""
            SELECT * FROM salary_components 
            WHERE is_active = 1 AND id NOT IN ({})
            ORDER BY component_type, component_name
        """.format(','.join(assigned_component_ids) if assigned_component_ids else '0')).fetchall()

    return templates.TemplateResponse("employee_salary.html", {
        "request": request,
        "employee": employee,
        "salary_structure": salary_structure,
        "available_components": available_components
    })

@app.post("/add-employee-salary-component")
async def add_employee_salary_component(
    request: Request,
    employee_id: str = Form(...),
    component_id: int = Form(...),
    amount: float = Form(...),
    effective_date: str = Form(...)
):
    """Add salary component to employee"""
    try:
        with get_db() as conn:
            # Get employee ID
            employee = conn.execute("SELECT id FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")

            conn.execute("""
                INSERT INTO employee_salary_structure (
                    employee_id, component_id, amount, effective_date
                ) VALUES (?, ?, ?, ?)
            """, (employee['id'], component_id, amount, effective_date))
            conn.commit()

        return RedirectResponse(url=f"/employee-salary/{employee_id}", status_code=303)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.post("/remove-employee-salary-component/{structure_id}")
async def remove_employee_salary_component(structure_id: int, employee_id: str = Form(...)):
    """Remove salary component from employee"""
    with get_db() as conn:
        conn.execute("UPDATE employee_salary_structure SET is_active = 0 WHERE id = ?", (structure_id,))
        conn.commit()

    return RedirectResponse(url=f"/employee-salary/{employee_id}", status_code=303)

@app.get("/payroll-processing", response_class=HTMLResponse)
async def payroll_processing(request: Request):
    """Payroll processing page"""
    with get_db() as conn:
        # Get active employees
        employees = conn.execute("""
            SELECT id, employee_id, first_name, last_name, basic_salary, department
            FROM employees 
            WHERE is_active = 1 
            ORDER BY department, last_name, first_name
        """).fetchall()

        # Get recent payroll runs
        recent_runs = conn.execute("""
            SELECT pr.*, u.username as processed_by_name
            FROM payroll_runs pr
            LEFT JOIN users u ON pr.processed_by = u.id
            ORDER BY pr.created_at DESC LIMIT 10
        """).fetchall()

    return templates.TemplateResponse("payroll_processing.html", {
        "request": request,
        "employees": employees,
        "recent_runs": recent_runs
    })

@app.post("/process-payroll")
async def process_payroll(
    request: Request,
    payroll_period: str = Form(...),
    pay_date: str = Form(...),
    employee_ids: list = Form(...)
):
    """Process payroll for selected employees"""
    try:
        with get_db() as conn:
            # Create payroll run
            cursor = conn.execute("""
                INSERT INTO payroll_runs (payroll_period, pay_date, status)
                VALUES (?, ?, 'draft')
            """, (payroll_period, pay_date))
            payroll_run_id = cursor.lastrowid

            total_gross = 0
            total_deductions = 0
            total_net = 0
            processed_count = 0

            for employee_id in employee_ids:
                employee = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
                if not employee:
                    continue

                # Calculate salary components
                basic_salary = employee['basic_salary']

                # Get allowances
                allowances = conn.execute("""
                    SELECT SUM(ess.amount) as total_allowances
                    FROM employee_salary_structure ess
                    JOIN salary_components sc ON ess.component_id = sc.id
                    WHERE ess.employee_id = ? AND ess.is_active = 1 AND sc.component_type = 'allowance'
                """, (employee_id,)).fetchone()['total_allowances'] or 0

                # Get deductions
                deductions = conn.execute("""
                    SELECT SUM(ess.amount) as total_deductions
                    FROM employee_salary_structure ess
                    JOIN salary_components sc ON ess.component_id = sc.id
                    WHERE ess.employee_id = ? AND ess.is_active = 1 AND sc.component_type = 'deduction'
                """, (employee_id,)).fetchone()['total_deductions'] or 0

                gross_salary = basic_salary + allowances

                # Calculate taxes (simplified Nigerian PAYE)
                annual_gross = gross_salary * 12
                monthly_paye = calculate_paye(annual_gross) / 12
                pension = gross_salary * 0.08  # 8%
                nhf = gross_salary * 0.025     # 2.5%
                nhis = gross_salary * 0.05     # 5%

                total_tax_deductions = monthly_paye + pension + nhf + nhis + deductions
                net_salary = gross_salary - total_tax_deductions

                # Convert sqlite3.Row to regular dict before using get()
                employee_data = dict(employee)
                employee_name = " ".join(filter(None, [
                    (employee_data.get('first_name') or '').strip(),
                    (employee_data.get('last_name') or '').strip()
                ])).strip() or str(employee_data.get('employee_id', ''))

                payroll_detail_columns = [
                    'payroll_run_id', 'employee_id', 'basic_salary', 'total_allowances',
                    'total_deductions', 'gross_salary', 'income_tax', 'pension', 'nhf', 'nhis',
                    'paye', 'other_deductions', 'net_salary'
                ]
                payroll_detail_values = [
                    payroll_run_id, employee_id, basic_salary, allowances, deductions,
                    gross_salary, monthly_paye, pension, nhf, nhis, monthly_paye,
                    deductions, net_salary
                ]

                if table_has_column('payroll_details', 'employee_name'):
                    payroll_detail_columns.insert(2, 'employee_name')
                    payroll_detail_values.insert(2, employee_name)

                if table_has_column('payroll_details', 'status'):
                    payroll_detail_columns.append('status')
                    payroll_detail_values.append('pending')

                if table_has_column('payroll_details', 'net_pay'):
                    payroll_detail_columns.append('net_pay')
                    payroll_detail_values.append(net_salary)

                conn.execute(
                    f"INSERT INTO payroll_details ({', '.join(payroll_detail_columns)}) VALUES ({', '.join(['?' for _ in payroll_detail_columns])})",
                    tuple(payroll_detail_values)
                )

                total_gross += gross_salary
                total_deductions += total_tax_deductions
                total_net += net_salary
                processed_count += 1

            # Update payroll run totals
            conn.execute("""
                UPDATE payroll_runs SET
                    total_gross = ?, total_deductions = ?, total_net = ?,
                    total_employees = ?, status = 'processed', updated_at = datetime('now')
                WHERE id = ?
            """, (total_gross, total_deductions, total_net, processed_count, payroll_run_id))

            conn.commit()

        return RedirectResponse(url=f"/payroll-run/{payroll_run_id}", status_code=303)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

def calculate_paye(annual_income: float) -> float:
    """Calculate Nigerian PAYE tax"""
    if annual_income <= 300000:
        return annual_income * 0.07
    elif annual_income <= 600000:
        return 21000 + (annual_income - 300000) * 0.11
    elif annual_income <= 1100000:
        return 66000 + (annual_income - 600000) * 0.15
    elif annual_income <= 1600000:
        return 165000 + (annual_income - 1100000) * 0.19
    elif annual_income <= 3200000:
        return 285000 + (annual_income - 1600000) * 0.21
    else:
        return 669000 + (annual_income - 3200000) * 0.24

@app.get("/payroll-run/{run_id}", response_class=HTMLResponse)
async def view_payroll_run(request: Request, run_id: int):
    """View payroll run details"""
    with get_db() as conn:
        # Get payroll run
        payroll_run = conn.execute("""
            SELECT pr.*, u.username as processed_by_name
            FROM payroll_runs pr
            LEFT JOIN users u ON pr.processed_by = u.id
            WHERE pr.id = ?
        """, (run_id,)).fetchone()

        if not payroll_run:
            raise HTTPException(status_code=404, detail="Payroll run not found")

        # Get payroll details
        payroll_details = conn.execute("""
            SELECT pd.*, e.employee_id, e.first_name, e.last_name, e.department, e.position
            FROM payroll_details pd
            JOIN employees e ON pd.employee_id = e.id
            WHERE pd.payroll_run_id = ?
            ORDER BY e.department, e.last_name, e.first_name
        """, (run_id,)).fetchall()

    return templates.TemplateResponse("payroll_run.html", {
        "request": request,
        "payroll_run": payroll_run,
        "payroll_details": payroll_details
    })

@app.get("/payslip/{detail_id}", response_class=HTMLResponse)
async def generate_payslip(request: Request, detail_id: int):
    """Generate employee payslip"""
    with get_db() as conn:
        # Get payroll detail with employee info
        payslip_data = conn.execute("""
            SELECT pd.*, pr.payroll_period, pr.pay_date,
                   e.employee_id, e.first_name, e.last_name, e.department, e.position,
                   e.basic_salary, e.bank_name, e.bank_account_number, e.hire_date
            FROM payroll_details pd
            JOIN payroll_runs pr ON pd.payroll_run_id = pr.id
            JOIN employees e ON pd.employee_id = e.id
            WHERE pd.id = ?
        """, (detail_id,)).fetchone()

        if not payslip_data:
            raise HTTPException(status_code=404, detail="Payslip data not found")

    return templates.TemplateResponse("payslip.html", {
        "request": request,
        "payslip": payslip_data
    })

@app.get("/payroll-reports", response_class=HTMLResponse)
async def payroll_reports(request: Request):
    """Payroll reports page"""
    with get_db() as conn:
        # Get payroll summary by period
        payroll_summary = conn.execute("""
            SELECT payroll_period,
                   COUNT(*) as employees_count,
                   SUM(total_gross) as total_gross,
                   SUM(total_deductions) as total_deductions,
                   SUM(total_net) as total_net
            FROM payroll_runs
            WHERE status = 'processed'
            GROUP BY payroll_period
            ORDER BY payroll_period DESC
            LIMIT 12
        """).fetchall()

        # Get employee salary summary
        employee_summary = conn.execute("""
            SELECT e.employee_id, e.first_name, e.last_name, e.department,
                   AVG(pd.gross_salary) as avg_gross,
                   AVG(pd.net_salary) as avg_net,
                   COUNT(pd.id) as payroll_runs
            FROM employees e
            LEFT JOIN payroll_details pd ON e.id = pd.employee_id
            WHERE e.is_active = 1
            GROUP BY e.id, e.employee_id, e.first_name, e.last_name, e.department
            ORDER BY e.last_name, e.first_name
        """).fetchall()

    return templates.TemplateResponse("payroll_reports.html", {
        "request": request,
        "payroll_summary": payroll_summary,
        "employee_summary": employee_summary
    })

# ─── END PAYROLL MANAGEMENT ROUTES ──────────────────────────────────

def get_available_port(preferred_port: int = 8000, max_port: int = 8100) -> int:
    """Choose an available localhost port, falling back from the preferred port."""
    for port in range(preferred_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free ports available between {preferred_port} and {max_port}")


if __name__ == "__main__":
    preferred_port = int(os.getenv("PORT", 8000))
    port = get_available_port(preferred_port)
    if port != preferred_port:
        msg = f"Port {preferred_port} is busy. Starting on port {port} instead."
        print(msg)
        logging.info(msg)
    else:
        logging.info("Using port %s", port)

    url = f"http://127.0.0.1:{port}/dashboard"
    try:
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    except Exception as e:
        msg = f"Could not open browser automatically: {e}"
        print(msg)
        logging.warning(msg)

    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
            use_colors=False,
            log_config=UVICORN_LOG_CONFIG,
        )
    except Exception as e:
        logging.exception("Failed to start Uvicorn")
        raise
