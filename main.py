from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
from pathlib import Path
from typing import List, Optional

app = FastAPI(title="UROMI NGO Accounting System")

# Add this function near the top (after imports)
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
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─── Register custom Jinja filter (must be right after templates) ───
def format_currency(value):
    try:
        return f"₦{float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["format_currency"] = format_currency

DB_FILE = Path("ngo.db")


def get_db() -> sqlite3.Connection:
    """Get a new database connection with row factory set."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


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
            role TEXT
        )
        """)

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

        # Transactions (with WHT and net_amount)
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
            'net_amount': 'REAL DEFAULT 0.0'
        }

        for col_name, col_def in missing_cols.items():
            if col_name not in columns:
                c.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_def}")
                print(f"→ Added missing column to transactions: {col_name}")

        conn.commit()

        # 3. Verification & debug output
        tables = ['chart_of_accounts', 'subaccounts', 'transactions', 'budgets', 'expenses']
        for tbl in tables:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
            if c.fetchone():
                print(f"✓ Table '{tbl}' exists")
            else:
                print(f"✗ Table '{tbl}' NOT created!")

        # Show current columns in transactions
        c.execute("PRAGMA table_info(transactions)")
        print("Columns in transactions:", [row[1] for row in c.fetchall()])


init_db()

# ─── Database Helpers ────────────────────────────────────────────────
def get_main_accounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM chart_of_accounts ORDER BY account_code").fetchall()


def get_subaccounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM subaccounts ORDER BY sub_account_code").fetchall()


def get_projects() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM projects ORDER BY project_name").fetchall()


def get_transactions() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC").fetchall()
# Usually near the top of your database init file
import os
import sqlite3

DB_PATH = "ngo.db"

def init_db():
    conn = sqlite3.connect("ngo.db")
    cursor = conn.cursor()

    # ── Transactions table ────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        date              TEXT NOT NULL,
        pv_number         TEXT,
        amount            REAL NOT NULL,
        WHT               REAL DEFAULT 0,
        net_amount        REAL,
        vendor_name       TEXT,
        vendor_tin        TEXT,
        bank_name         TEXT,
        account_number    TEXT,
        account_name      TEXT,
        description       TEXT,
        project           TEXT,
        type              TEXT CHECK(type IN ('Income', 'Expense')),
        main_account      TEXT,
        main_account_code TEXT,
        sub_account       TEXT,
        sub_account_code  TEXT,
        created_at        TEXT DEFAULT (datetime('now')),
        month             INTEGER,
        wht_rate          REAL DEFAULT 0.0,
        is_wht_percentage INTEGER DEFAULT 0
    )
    """)

    # ── Other tables (projects, chart_of_accounts, subaccounts, etc.) ──────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        code        TEXT UNIQUE,
        description TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )
    """)

    # ... add your other CREATE TABLE statements here ...

    conn.commit()
    conn.close()
    print("Database schema initialized.")

# ─── Database Helpers ────────────────────────────────────────────────
def get_main_accounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM chart_of_accounts ORDER BY account_code").fetchall()


def get_subaccounts() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM subaccounts ORDER BY sub_account_code").fetchall()


def get_projects() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM projects ORDER BY project_name").fetchall()


def get_transactions() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC").fetchall()


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
                project, payee, payee_tin,
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
        "payee": tx_dict.get("payee", "—"),
        "payee_tin": tx_dict.get("payee_tin", "—"),
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

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
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
            conn.execute(
                """
                INSERT INTO chart_of_accounts
                (account_code, account_name, account_type, description)
                VALUES (?, ?, ?, ?)
                """,
                (account_code, account_name, account_type, description)
            )
            conn.commit()
            return RedirectResponse("/chart-of-accounts", status_code=303)
        except sqlite3.IntegrityError:
            error = f"Account code '{account_code}' already exists."
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
            conn.execute(
                """
                INSERT INTO subaccounts
                (parent_account_code, sub_account_code, sub_account_name, description)
                VALUES (?, ?, ?, ?)
                """,
                (parent_account, sub_account_code, sub_account_name, description)
            )
            conn.commit()
            return RedirectResponse("/chart-of-accounts", status_code=303)
        except sqlite3.IntegrityError:
            error = f"Sub-account code '{sub_account_code}' already exists or invalid parent."
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

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

# ─── Delete Main Account ─────────────────────────────────────────────────

@app.post("/delete-main-account/{account_code}")
async def delete_main_account(
    account_code: str,
    request: Request
):
    with get_db() as conn:
        try:
            # Optional: check if account is used in transactions
            used = conn.execute(
                """
                SELECT COUNT(*) as count 
                FROM transactions 
                WHERE main_account_code = ?
                """,
                (account_code,)
            ).fetchone()["count"]

            if used > 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Cannot+delete+account+in+use+in+transactions",
                    status_code=303
                )

            # Delete the account
            cursor = conn.execute(
                "DELETE FROM chart_of_accounts WHERE account_code = ?",
                (account_code,)
            )
            
            if cursor.rowcount == 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Account+not+found",
                    status_code=303
                )

            conn.commit()
            return RedirectResponse(
                "/chart-of-accounts?success=Main+account+deleted",
                status_code=303
            )

        except Exception as e:
            conn.rollback()
            return RedirectResponse(
                f"/chart-of-accounts?error={str(e)}",
                status_code=303
            )


# ─── Delete Sub-Account ──────────────────────────────────────────────────

@app.post("/delete-subaccount/{sub_account_code}")
async def delete_subaccount(
    sub_account_code: str,
    request: Request
):
    with get_db() as conn:
        try:
            # Optional: check if sub-account is used
            used = conn.execute(
                """
                SELECT COUNT(*) as count 
                FROM transactions 
                WHERE sub_account_code = ?
                """,
                (sub_account_code,)
            ).fetchone()["count"]

            if used > 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Cannot+delete+sub-account+in+use+in+transactions",
                    status_code=303
                )

            cursor = conn.execute(
                "DELETE FROM subaccounts WHERE sub_account_code = ?",
                (sub_account_code,)
            )

            if cursor.rowcount == 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Sub-account+not+found",
                    status_code=303
                )

            conn.commit()
            return RedirectResponse(
                "/chart-of-accounts?success=Sub-account+deleted",
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
    project: Optional[str] = Form(None),           # ← changed to project (recommended)
    main_account_code: str = Form(...),
    sub_account_code: Optional[str] = Form(None),
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
                month, project, project,
                main_account, main_account_code,
                sub_account, sub_account_code,
                wht_applied, wht_rate, wht_amount, net_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.strip(),
            pv_number.strip() if pv_number else None,
            description.strip(),
            type.strip(),
            amount,
            month,
            None,                   # ← project name (optional – can remove if using id)
            project.strip() if project else None,   # ← project foreign key
            main_account_name,
            main_account_code.strip(),
            sub_account_name,
            sub_account_code.strip() if sub_account_code else None,
            wht_applied_flag,
            wht_rate_pct,
            wht_amount,
            net_amount
        ))

        conn.commit()

    return RedirectResponse("/transactions?success=created", status_code=303)

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

# ─── Edit Transaction Form ────────────────────────────────────────────────

@app.get("/edit-transaction/{transaction_id}", response_class=HTMLResponse)
async def edit_transaction_form(request: Request, transaction_id: int):
    """Display the edit form pre-filled with existing transaction data"""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 
                id, date, pv_number, description, type, amount,
                project, main_account_code, sub_account_code,
                wht_applied, wht_rate
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
        "wht_applied": "on" if tx.get("wht_applied", False) else "off",
        "wht_rate": f"{(tx.get('wht_rate', 0.0) * 100):.2f}",
    }

    return templates.TemplateResponse(
        "add_transaction.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "projects": get_projects(),
            "subaccounts": get_subaccounts(),
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
    project: Optional[str] = Form(None),          # ← using project
    main_account_code: str = Form(...),
    sub_account_code: Optional[str] = Form(None),
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
                net_amount = ?
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
                date, pv_number, description, type, amount,
                project, main_account, main_account_code,
                sub_account, sub_account_code
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
                main_account_code,
                main_account,
                sub_account_code,
                sub_account,
                SUM(CASE WHEN type = 'Income' OR type = 'Credit' THEN amount ELSE 0 END) as credit,
                SUM(CASE WHEN type = 'Expense' OR type = 'Debit' THEN amount ELSE 0 END) as debit
            FROM transactions
            GROUP BY main_account_code, sub_account_code
            ORDER BY main_account_code, sub_account_code
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
        # Income (by main account or type)
        income = conn.execute("""
            SELECT 
                main_account_code,
                main_account,
                SUM(amount) as total_income
            FROM transactions
            WHERE type = 'Income'
            GROUP BY main_account_code, main_account
            ORDER BY total_income DESC
        """).fetchall()

        # Expenditure (expenses + any debit-like entries)
        expenditure = conn.execute("""
            SELECT 
                main_account_code,
                main_account,
                SUM(amount) as total_expenditure
            FROM transactions
            WHERE type = 'Expense'
            GROUP BY main_account_code, main_account
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
                main_account_code,
                main_account,
                sub_account_code,
                sub_account,
                SUM(CASE 
                    WHEN type IN ('Income', 'Credit') THEN amount
                    WHEN type IN ('Expense', 'Debit') THEN -amount
                    ELSE 0 
                END) as balance
            FROM transactions
            WHERE main_account_code LIKE '1%'  -- typical asset codes start with 1
            GROUP BY main_account_code, sub_account_code
            HAVING balance != 0
            ORDER BY main_account_code, sub_account_code
        """).fetchall()

        # Liabilities & Equity (negative or credit-heavy accounts)
        liabilities_equity = conn.execute("""
            SELECT 
                main_account_code,
                main_account,
                sub_account_code,
                sub_account,
                SUM(CASE 
                    WHEN type IN ('Income', 'Credit') THEN amount
                    WHEN type IN ('Expense', 'Debit') THEN -amount
                    ELSE 0 
                END) as balance
            FROM transactions
            WHERE main_account_code LIKE '2%' OR main_account_code LIKE '3%'  -- liabilities 2, equity 3
            GROUP BY main_account_code, sub_account_code
            HAVING balance != 0
            ORDER BY main_account_code, sub_account_code
        """).fetchall()

        # Totals
        totals = conn.execute("""
            SELECT 
                SUM(CASE WHEN main_account_code LIKE '1%' THEN 
                    CASE WHEN type IN ('Income', 'Credit') THEN amount ELSE -amount END 
                ELSE 0 END) as total_assets,
                SUM(CASE WHEN main_account_code LIKE '2%' OR main_account_code LIKE '3%' THEN 
                    CASE WHEN type IN ('Income', 'Credit') THEN amount ELSE -amount END 
                ELSE 0 END) as total_liab_equity
            FROM transactions
        """).fetchone()

    total_assets = totals["total_assets"] or 0
    total_liab_equity = totals["total_liab_equity"] or 0

    return templates.TemplateResponse(
        "balance_sheet.html",
        {
            "request": request,
            "assets": assets,
            "liabilities_equity": liabilities_equity,
            "total_assets": total_assets,
            "total_liab_equity": total_liab_equity,
            "net_difference": total_assets - total_liab_equity,
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

    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": budgets,
            "grand_total": grand_total,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
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

    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": conn.execute("SELECT * FROM budgets ORDER BY project, account_code").fetchall(),
            "grand_total": conn.execute("SELECT SUM(total) FROM budgets").fetchone()[0] or 0,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
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

# ─── Projects Management ─────────────────────────────────────────────

@app.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    """Show list of all projects"""
    with get_db() as conn:
        projects = conn.execute("""
            SELECT id, project_name, donor, start_date, end_date 
            FROM projects 
            ORDER BY project_name
        """).fetchall()

    return templates.TemplateResponse(
        "projects.html",
        {
            "request": request,
            "projects": projects
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
):
    errors = []
    if not project_name.strip():
        errors.append("Project name is required")

    if errors:
        return templates.TemplateResponse(
            "project_form.html",
            {
                "request": request,
                "project": {
                    "project_name": project_name,
                    "donor": donor,
                    "start_date": start_date,
                    "end_date": end_date
                },
                "error": "<br>".join(errors)
            }
        )

    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO projects (project_name, donor, start_date, end_date)
                VALUES (?, ?, ?, ?)
            """, (
                project_name.strip(),
                donor.strip() if donor else None,
                start_date.strip() if start_date else None,
                end_date.strip() if end_date else None
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
                        "end_date": end_date
                    },
                    "error": "Project name already exists"
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
):
    errors = []
    if not project_name.strip():
        errors.append("Project name is required")

    if errors:
        with get_db() as conn:
            project = conn.execute(
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
                    "end_date": end_date
                },
                "error": "<br>".join(errors)
            }
        )

    with get_db() as conn:
        try:
            conn.execute("""
                UPDATE projects
                SET project_name = ?, donor = ?, start_date = ?, end_date = ?
                WHERE id = ?
            """, (
                project_name.strip(),
                donor.strip() if donor else None,
                start_date.strip() if start_date else None,
                end_date.strip() if end_date else None,
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
                        "end_date": end_date
                    },
                    "error": "Project name already exists"
                }
            )


    return RedirectResponse("/projects?success=updated", status_code=303)

from fastapi import Request
from fastapi.responses import HTMLResponse

@app.get("/transactions", response_class=HTMLResponse)
@app.get("/transactions-page", response_class=HTMLResponse)  # optional alias
async def list_transactions(request: Request):
    with get_db() as conn:
        # Only select columns that actually exist in your table
        # Adjust this list based on your real schema
        transactions = conn.execute("""
            SELECT
                id,
                date,
                pv_number,
                description,
                type,
                amount,
                wht_applied,          -- boolean / 1 or 0
                wht_rate,             -- decimal e.g. 0.05 = 5%
                project,
                main_account_code,
                sub_account_code
                -- Add other real columns you want to display:
                -- payee, vendor, status, created_at, etc.
            FROM transactions
            ORDER BY date DESC, id DESC
            LIMIT 500               -- safety limit - consider real pagination later
        """).fetchall()

    # Optional: get success/error messages from query params (after redirect)
    success_msg = request.query_params.get("success")
    error_msg   = request.query_params.get("error")

    # Optional debug (uncomment when needed)
    # if transactions:
    #     print("Available columns:", transactions[0].keys())

    return templates.TemplateResponse(
        "transactions.html",
        {
            "request":      request,
            "transactions": transactions,
            "success_msg":  success_msg,
            "error_msg":    error_msg,
            # You can also pre-compute display values here if needed
            # e.g. "transactions_display": [
            #     {**tx, "wht_amount": tx["amount"] * tx["wht_rate"] if tx["wht_applied"] else 0}
            #     for tx in transactions
            # ]
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

