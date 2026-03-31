# =========================================================
# IMPORTS
# =========================================================

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

import sqlite3
import os
import traceback

DB_PATH = os.path.join(os.path.dirname(__file__), "ngo.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT UNIQUE,
            account_name TEXT,
            account_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()

# =========================================================
# LIFESPAN
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("✅ Database initialized")
    yield
    print("🛑 Application shutdown")


# =========================================================
# CREATE FASTAPI APP
# =========================================================
app = FastAPI(
    title="UROMI NGO Accounting System",
    lifespan=lifespan
)


# =========================================================
# MIDDLEWARE
# =========================================================
app.add_middleware(
    SessionMiddleware,
    secret_key="uromi-ngo-secure-key"
)


# =========================================================
# STATIC FILES & TEMPLATES
# =========================================================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# =========================================================
# JINJA FILTERS
# =========================================================
def format_currency(value):
    try:
        return f"₦{float(value):,.2f}"
    except:
        return "₦0.00"

templates.env.filters["format_currency"] = format_currency


# =========================================================
# DATABASE HELPER FUNCTIONS
# =========================================================

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


# =========================================================
# UTILITY FUNCTIONS
# =========================================================

def log_action(username: str, action: str):
    """Log user actions for audit"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO audit_logs (username, action)
            VALUES (?, ?)
        """, (username, action))
        conn.commit()


def require_role(request: Request, allowed_roles: list):
    """Check if user has required role"""
    role = request.session.get("role")
    if not role:
        return RedirectResponse("/login")
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Access denied")
    return True


def safe_float(value) -> float:
    """Convert value to float safely"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def number_to_ngn_words(amount: float) -> str:
    """Convert naira amount to words"""
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


# =========================================================
# ROUTES - HOME & DASHBOARD
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard view"""
    try:
        with get_db() as conn:
            total_budget = conn.execute("""
                SELECT COALESCE(SUM(amount),0)
                FROM budgets
            """).fetchone()[0]

            total_income = conn.execute("""
                SELECT COALESCE(SUM(amount),0)
                FROM transactions
                WHERE type='Income'
            """).fetchone()[0]

            total_expenses = conn.execute("""
                SELECT COALESCE(SUM(amount),0)
                FROM transactions
                WHERE type='Expense'
            """).fetchone()[0]

        balance = total_income - total_expenses
        burn_rate = round((total_expenses / total_budget) * 100, 2) if total_budget > 0 else 0.0

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": request.session.get("user", "User"),
                "total_income": total_income,
                "total_expenses": total_expenses,
                "total_budget": total_budget,
                "balance": balance,
                "burn_rate": burn_rate,
            }
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": "User",
                "total_income": 0,
                "total_expenses": 0,
                "total_budget": 0,
                "balance": 0,
                "burn_rate": 0,
            }
        )


# =========================================================
# ROUTES - AUTHENTICATION
# =========================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle user login"""
    # Simple credential check (in production, use proper authentication)
    valid_users = {
        "admin": "admin123",
        "finance": "finance123",
        "audit": "audit123"
    }
    
    if username in valid_users and valid_users[username] == password:
        request.session["user"] = username
        request.session["role"] = username
        log_action(username, "Logged in")
        return RedirectResponse(url="/dashboard", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Invalid credentials"
    })


@app.get("/logout")
async def logout(request: Request):
    """Handle user logout"""
    user = request.session.get("user")
    if user:
        log_action(user, "Logged out")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# =========================================================
# ROUTES - ROLE-BASED PAGES
# =========================================================

@app.get("/admin")
async def admin_dashboard(request: Request):
    require_role(request, ["admin"])
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/finance")
async def finance_dashboard(request: Request):
    require_role(request, ["finance"])
    return templates.TemplateResponse("finance.html", {"request": request})


@app.get("/audit")
async def audit_dashboard(request: Request):
    require_role(request, ["audit"])
    return templates.TemplateResponse("audit.html", {"request": request})


# =========================================================
# ROUTES - CHART OF ACCOUNTS
# =========================================================

@app.get("/chart-of-accounts", response_class=HTMLResponse)
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
    
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO chart_of_accounts
                (account_code, account_name, account_type, description)
                VALUES (?, ?, ?, ?)
            """, (account_code, account_name, account_type, description.strip()))
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
            "form_data": {"account_code": account_code, "account_name": account_name},
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
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO subaccounts
                (parent_account_code, sub_account_code, sub_account_name, description)
                VALUES (?, ?, ?, ?)
            """, (parent_account.strip(), sub_account_code.strip(), sub_account_name.strip(), description.strip()))
            conn.commit()
            return RedirectResponse("/chart-of-accounts", status_code=303)
        except sqlite3.IntegrityError:
            error = f"Sub-account code '{sub_account_code}' already exists."
        except Exception as e:
            error = str(e)
    
    return templates.TemplateResponse(
        "chart_of_accounts.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": {"parent_account": parent_account, "sub_account_code": sub_account_code},
            "error": error
        }
    )


@app.post("/delete-main-account/{account_code}")
async def delete_main_account(account_code: str, request: Request):
    with get_db() as conn:
        try:
            used = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE main_account_code = ?",
                (account_code,)
            ).fetchone()[0]
            
            if used > 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Cannot+delete+account+in+use",
                    status_code=303
                )
            
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
            return RedirectResponse("/chart-of-accounts?success=deleted", status_code=303)
        except Exception as e:
            return RedirectResponse(
                f"/chart-of-accounts?error={str(e)}",
                status_code=303
            )


@app.post("/delete-subaccount/{sub_account_code}")
async def delete_subaccount(sub_account_code: str, request: Request):
    with get_db() as conn:
        try:
            used_txn = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE sub_account_code = ?",
                (sub_account_code,)
            ).fetchone()[0]
            
            used_budget = conn.execute(
                "SELECT COUNT(*) FROM budgets WHERE subaccount_code = ?",
                (sub_account_code,)
            ).fetchone()[0]
            
            if used_txn > 0 or used_budget > 0:
                return RedirectResponse(
                    "/chart-of-accounts?error=Cannot+delete+sub-account+in+use",
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
            return RedirectResponse("/chart-of-accounts?success=deleted", status_code=303)
        except Exception as e:
            return RedirectResponse(
                f"/chart-of-accounts?error={str(e)}",
                status_code=303
            )


# =========================================================
# ROUTES - TRANSACTIONS
# =========================================================

@app.get("/add-transaction", response_class=HTMLResponse)
async def add_transaction_form(request: Request):
    return templates.TemplateResponse(
        "add_transaction.html",
        {
            "request": request,
            "main_accounts": get_main_accounts(),
            "projects": get_projects(),
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
    project: Optional[str] = Form(None),
    main_account_code: str = Form(...),
    sub_account_code: Optional[str] = Form(None),
    wht_applied: str = Form(default="off"),
    wht_rate: str = Form(default="0.0"),
):
    errors = []
    
    # Validate amount
    try:
        amount = float(gross_amount.strip().replace(",", ""))
        if amount <= 0:
            errors.append("Amount must be greater than zero")
    except (ValueError, TypeError):
        errors.append("Invalid amount format")
    
    if not main_account_code.strip():
        errors.append("Main account is required")
    
    # Calculate WHT
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
            errors.append("Invalid WHT rate")
    
    if errors:
        return templates.TemplateResponse(
            "add_transaction.html",
            {
                "request": request,
                "main_accounts": get_main_accounts(),
                "projects": get_projects(),
                "subaccounts": get_subaccounts(),
                "form_data": {
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
                },
                "error": "<br>".join(errors),
                "transaction": None,
                "is_edit": False,
            }
        )
    
    # Save to database
    with get_db() as conn:
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
                    "form_data": {},
                    "error": f"Account code '{main_account_code}' not found",
                    "transaction": None,
                    "is_edit": False,
                }
            )
        
        main_account_name = main_row["account_name"]
        
        sub_account_name = None
        if sub_account_code and sub_account_code.strip():
            sub_row = conn.execute(
                "SELECT sub_account_name FROM subaccounts WHERE sub_account_code = ?",
                (sub_account_code.strip(),)
            ).fetchone()
            if sub_row:
                sub_account_name = sub_row["sub_account_name"]
        
        month = None
        if date:
            try:
                _, mm, _ = date.split("-")
                month = int(mm)
            except:
                pass
        
        conn.execute("""
            INSERT INTO transactions (
                date, pv_number, description, type, amount,
                month, project,
                main_account, main_account_code,
                sub_account, sub_account_code,
                wht_applied, wht_rate, wht_amount, net_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            int(wht_applied_flag),
            wht_rate_pct,
            round(wht_amount, 2),
            round(net_amount, 2)
        ))
        conn.commit()
    
    return RedirectResponse("/transactions?success=created", status_code=303)


@app.get("/transactions", response_class=HTMLResponse)
async def transactions_page(request: Request):
    transactions = get_transactions()
    success_msg = request.query_params.get("success")
    return templates.TemplateResponse(
        "transactions.html",
        {
            "request": request,
            "transactions": transactions,
            "success_msg": success_msg
        }
    )


@app.get("/edit-transaction/{transaction_id}", response_class=HTMLResponse)
async def edit_transaction_form(request: Request, transaction_id: int):
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


@app.post("/update-transaction")
async def update_transaction(
    id: str = Form(None),
    date: str = Form(...),
    pv_number: str = Form(...),
    description: str = Form(...),
    type: str = Form(...),
    gross_amount: str = Form(...),
    project: str = Form(...),
    main_account_code: str = Form(...),
    sub_account_code: str = Form(...),
    wht_applied: str = Form(None),
    wht_rate: str = Form(default="0"),
):
    try:
        amount = float(gross_amount) if gross_amount else 0
        wht_rate_val = float(wht_rate) if wht_rate else 0
        wht_applied_flag = 1 if wht_applied == 'on' else 0
        
        wht_amount = (amount * wht_rate_val) / 100 if wht_applied_flag else 0
        net_amount = amount - wht_amount
        
        with get_db() as conn:
            if id and id.strip():
                conn.execute("""
                    UPDATE transactions SET
                        date=?, pv_number=?, description=?, type=?,
                        amount=?, project=?, main_account_code=?, sub_account_code=?,
                        wht_applied=?, wht_rate=?, wht_amount=?, net_amount=?
                    WHERE id=?
                """, (date, pv_number, description, type, amount,
                      project, main_account_code, sub_account_code,
                      wht_applied_flag, wht_rate_val, round(wht_amount, 2), round(net_amount, 2), id))
            else:
                conn.execute("""
                    INSERT INTO transactions (
                        date, pv_number, description, type, amount,
                        project, main_account_code, sub_account_code,
                        wht_applied, wht_rate, wht_amount, net_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, pv_number, description, type, amount,
                      project, main_account_code, sub_account_code,
                      wht_applied_flag, wht_rate_val, round(wht_amount, 2), round(net_amount, 2)))
            
            conn.commit()
        
        return RedirectResponse("/transactions?success=updated", status_code=303)
    except Exception as e:
        print(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/delete-transaction/{id}")
async def delete_transaction(id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (id,))
        conn.commit()
    
    return RedirectResponse("/transactions?success=deleted", status_code=303)


# =========================================================
# ROUTES - VOUCHER/PAYMENT PRINTING
# =========================================================

@app.get("/voucher/{transaction_id}", response_class=HTMLResponse)
async def view_voucher(transaction_id: int, request: Request):
    try:
        with get_db() as conn:
            row = conn.execute("""
                SELECT
                    id, date, pv_number, reference, description, type, amount,
                    wht_applied, wht_rate, project, main_account, main_account_code,
                    sub_account, sub_account_code
                FROM transactions
                WHERE id = ?
            """, (transaction_id,)).fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            tx = dict(row)
        
        # Calculate amounts
        gross_amount = float(safe_float(tx.get("amount", 0)))
        wht_applied = bool(float(safe_float(tx.get("wht_applied", 0))))
        wht_rate = float(safe_float(tx.get("wht_rate", 0.0)))
        wht_amount = float(gross_amount * wht_rate) if wht_applied else 0.0
        net_amount = float(gross_amount - wht_amount)
        
        context = {
            "request": request,
            "tx": tx,
            "organization": "CARE INTERNATIONAL",
            "voucher_title": "PAYMENT VOUCHER" if tx.get("type") == "Expense" else "RECEIPT VOUCHER",
            "pv_number": tx.get("pv_number") or f"PV-{tx['id']:04d}",
            "date": tx.get("date", "—"),
            "description": tx.get("description", "—"),
            "project": tx.get("project", "—"),
            "payee": tx.get("reference") or "Not specified",
            "payee_tin": tx.get("vendor_tin") or "—",
            "main_account_code": tx.get("main_account_code", "—"),
            "main_account": tx.get("main_account", "—"),
            "sub_account_code": tx.get("sub_account_code", "—"),
            "sub_account": tx.get("sub_account", "—"),
            "gross_amount": gross_amount,
            "gross_amount_formatted": f"₦{gross_amount:,.2f}",
            "wht_applied": wht_applied,
            "wht_rate_percent": f"{wht_rate * 100:.1f}" if wht_applied else "0.0",
            "wht_amount": wht_amount,
            "wht_amount_formatted": f"₦{wht_amount:,.2f}" if wht_applied else "₦0.00",
            "net_amount": net_amount,
            "net_amount_formatted": f"₦{net_amount:,.2f}",
            "net_amount_in_words": number_to_ngn_words(net_amount),
            "prepared_by": "Finance Officer",
            "approved_by": "Director",
        }
        
        response = templates.TemplateResponse("payment-voucher-print.html", context)
        response.headers["Content-Disposition"] = f'inline; filename="voucher-{context["pv_number"]}.html"'
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load voucher: {str(e)}"
        )


# =========================================================
# ROUTES - REPORTS
# =========================================================

@app.get("/ledger", response_class=HTMLResponse)
async def ledger_page(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    project: str = None
):
    with get_db() as conn:
        query = """
            SELECT 
                id, date, pv_number, description, type, amount,
                project, main_account, main_account_code, sub_account, sub_account_code
            FROM transactions
            WHERE 1=1
        """
        
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if project:
            query += " AND project = ?"
            params.append(project)
        
        query += " ORDER BY date ASC, id ASC"
        rows = conn.execute(query, params).fetchall()
        
        ledger_data = []
        balance = 0
        total_debit = 0
        total_credit = 0
        
        for tx in rows:
            amount = tx["amount"] or 0
            
            if tx["type"] == "Income":
                debit = amount
                credit = 0
                balance += amount
                total_debit += amount
            else:
                debit = 0
                credit = amount
                balance -= amount
                total_credit += amount
            
            ledger_data.append({
                "date": tx["date"],
                "pv": tx["pv_number"],
                "description": tx["description"],
                "account": f"{tx['main_account_code']} - {tx['main_account']}",
                "sub_account": f"{tx['sub_account_code']} - {tx['sub_account']}" if tx["sub_account"] else "",
                "debit": debit,
                "credit": credit,
                "balance": balance
            })
    
    return templates.TemplateResponse("ledger.html", {
        "request": request,
        "transactions": ledger_data,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "closing_balance": balance
    })


@app.get("/trial-balance", response_class=HTMLResponse)
async def trial_balance_page(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    project: str = None
):
    with get_db() as conn:
        query = """
            SELECT 
                main_account_code, main_account, sub_account_code, sub_account,
                COALESCE(SUM(CASE WHEN type IN ('Expense', 'Debit') THEN amount ELSE 0 END), 0) AS debit,
                COALESCE(SUM(CASE WHEN type IN ('Income', 'Credit') THEN amount ELSE 0 END), 0) AS credit
            FROM transactions
            WHERE 1=1
        """
        
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if project:
            query += " AND project = ?"
            params.append(project)
        
        query += " GROUP BY main_account_code, main_account, sub_account_code, sub_account ORDER BY main_account_code, sub_account_code"
        
        rows = conn.execute(query, params).fetchall()
        
        trial_data = []
        total_debit = 0
        total_credit = 0
        
        for r in rows:
            debit = r["debit"]
            credit = r["credit"]
            
            if debit > credit:
                net_debit = debit - credit
                net_credit = 0
            elif credit > debit:
                net_debit = 0
                net_credit = credit - debit
            else:
                net_debit = 0
                net_credit = 0
            
            total_debit += debit
            total_credit += credit
            
            trial_data.append({
                "account_code": r["main_account_code"],
                "account_name": r["main_account"],
                "sub_account": f"{r['sub_account_code']} - {r['sub_account']}" if r["sub_account"] else "",
                "debit": debit,
                "credit": credit,
                "net_debit": net_debit,
                "net_credit": net_credit
            })
    
    return templates.TemplateResponse(
        "trial_balance.html",
        {
            "request": request,
            "accounts": trial_data,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": abs(total_debit - total_credit),
            "start_date": start_date,
            "end_date": end_date,
            "project": project
        }
    )


@app.get("/income-expenditure", response_class=HTMLResponse)
async def income_expenditure_report(request: Request):
    with get_db() as conn:
        income = conn.execute("""
            SELECT 
                main_account_code, main_account,
                SUM(amount) as total_income
            FROM transactions
            WHERE type = 'Income'
            GROUP BY main_account_code, main_account
            ORDER BY total_income DESC
        """).fetchall()
        
        expenditure = conn.execute("""
            SELECT 
                main_account_code, main_account,
                SUM(amount) as total_expenditure
            FROM transactions
            WHERE type = 'Expense'
            GROUP BY main_account_code, main_account
            ORDER BY total_expenditure DESC
        """).fetchall()
        
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
        assets = conn.execute("""
            SELECT 
                main_account_code, main_account, sub_account_code, sub_account,
                SUM(CASE WHEN type IN ('Income', 'Credit') THEN amount WHEN type IN ('Expense', 'Debit') THEN -amount ELSE 0 END) as balance
            FROM transactions
            WHERE main_account_code LIKE '1%'
            GROUP BY main_account_code, sub_account_code
            HAVING balance != 0
            ORDER BY main_account_code, sub_account_code
        """).fetchall()
        
        liabilities_equity = conn.execute("""
            SELECT 
                main_account_code, main_account, sub_account_code, sub_account,
                SUM(CASE WHEN type IN ('Income', 'Credit') THEN amount WHEN type IN ('Expense', 'Debit') THEN -amount ELSE 0 END) as balance
            FROM transactions
            WHERE main_account_code LIKE '2%' OR main_account_code LIKE '3%'
            GROUP BY main_account_code, sub_account_code
            HAVING balance != 0
            ORDER BY main_account_code, sub_account_code
        """).fetchall()
        
        totals = conn.execute("""
            SELECT 
                SUM(CASE WHEN main_account_code LIKE '1%' THEN CASE WHEN type IN ('Income', 'Credit') THEN amount ELSE -amount END ELSE 0 END) as total_assets,
                SUM(CASE WHEN main_account_code LIKE '2%' OR main_account_code LIKE '3%' THEN CASE WHEN type IN ('Income', 'Credit') THEN amount ELSE -amount END ELSE 0 END) as total_liab_equity
            FROM transactions
        """).fetchone()
    
    total_assets = totals["total_assets"] or 0
    total_liab_equity = totals["total_liab_equity"] or 0
    
    return templates.TemplateResponse(
        "balance_sheet.html",
        {
            "request": request,
            "assets": assets,
            "libilities_equity": liabilities_equity,
            "total_assets": total_assets,
            "total_liab_equity": total_liab_equity,
            "net_difference": total_assets - total_liab_equity,
        }
    )


# =========================================================
# ROUTES - BUDGET MANAGEMENT
# =========================================================

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
    
    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": budgets,
            "grand_total": grand_total,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": {},
            "error": None
        }
    )


@app.post("/add-budget")
async def add_budget(
    project: str = Form(...),
    account_code: str = Form(...),
    account_name: str = Form(...),
    subaccount_code: str = Form(None),
    subaccount_name: str = Form(None),
    detail: str = Form(None),
    quantity: float = Form(...),
    unit_cost: float = Form(...),
    periods: int = Form(...),
):
    try:
        total = quantity * unit_cost * periods
        
        with get_db() as conn:
            conn.execute("""
                INSERT INTO budgets (
                    project, account_code, account_name,
                    subaccount_code, subaccount_name, detail,
                    quantity, unit_cost, periods, total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project, account_code, account_name,
                subaccount_code, subaccount_name, detail,
                quantity, unit_cost, periods, total
            ))
            conn.commit()
        
        return RedirectResponse("/budget?success=added", status_code=303)
    
    except Exception as e:
        return RedirectResponse(f"/budget?error={str(e)}", status_code=303)


@app.get("/edit-budget/{budget_id}", response_class=HTMLResponse)
async def edit_budget_form(request: Request, budget_id: int):
    with get_db() as conn:
        budget = conn.execute(
            "SELECT * FROM budgets WHERE id=?",
            (budget_id,)
        ).fetchone()
        
        if not budget:
            raise HTTPException(status_code=404, detail="Budget line not found")
        
        budgets = conn.execute("""
            SELECT * FROM budgets
            ORDER BY project, account_code
        """).fetchall()
        
        grand_total = conn.execute("""
            SELECT COALESCE(SUM(total),0)
            FROM budgets
        """).fetchone()[0]
    
    return templates.TemplateResponse(
        "budget.html",
        {
            "request": request,
            "budgets": budgets,
            "grand_total": grand_total,
            "main_accounts": get_main_accounts(),
            "subaccounts": get_subaccounts(),
            "form_data": dict(budget),
            "editing_id": budget_id,
            "error": None,
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
    detail: str = Form(""),
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
            budgets = conn.execute("""
                SELECT * FROM budgets
                ORDER BY project, account_code
            """).fetchall()
            
            grand_total = conn.execute("""
                SELECT COALESCE(SUM(total),0)
                FROM budgets
            """).fetchone()[0]
        
        return templates.TemplateResponse(
            "budget.html",
            {
                "request": request,
                "budgets": budgets,
                "grand_total": grand_total,
                "main_accounts": get_main_accounts(),
                "subaccounts": get_subaccounts(),
                "form_data": {
                    "id": id, "project": project, "account_code": account_code,
                    "account_name": account_name, "subaccount_code": subaccount_code,
                    "subaccount_name": subaccount_name, "detail": detail,
                    "quantity": quantity, "unit_cost": unit_cost, "periods": periods,
                },
                "editing_id": id,
                "error": "<br>".join(errors),
            }
        )
    
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE budgets
                SET project=?, account_code=?, account_name=?,
                    subaccount_code=?, subaccount_name=?, detail=?,
                    quantity=?, unit_cost=?, periods=?, total=?
                WHERE id=?
            """, (
                project.strip(), account_code.strip(), account_name.strip(),
                subaccount_code.strip() if subaccount_code else None,
                subaccount_name.strip() if subaccount_name else None,
                detail.strip(), quantity, unit_cost, periods, total, id,
            ))
            conn.commit()
        
        return RedirectResponse("/budget?success=updated", status_code=303)
    
    except Exception as e:
        with get_db() as conn:
            budgets = conn.execute("""
                SELECT * FROM budgets
                ORDER BY project, account_code
            """).fetchall()
            grand_total = conn.execute("""
                SELECT COALESCE(SUM(total),0)
                FROM budgets
            """).fetchone()[0]
        
        return templates.TemplateResponse(
            "budget.html",
            {
                "request": request,
                "budgets": budgets,
                "grand_total": grand_total,
                "main_accounts": get_main_accounts(),
                "subaccounts": get_subaccounts(),
                "form_data": {
                    "id": id, "project": project, "account_code": account_code,
                    "account_name": account_name, "subaccount_code": subaccount_code,
                    "subaccount_name": subaccount_name, "detail": detail,
                    "quantity": quantity, "unit_cost": unit_cost, "periods": periods,
                },
                "editing_id": id,
                "error": f"Update failed: {str(e)}",
            }
        )


@app.post("/delete-budget/{budget_id}")
async def delete_budget(budget_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        conn.commit()
    return RedirectResponse("/budget?success=deleted", status_code=303)


# =========================================================
# ROUTES - PROJECTS MANAGEMENT
# =========================================================

@app.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
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
    return templates.TemplateResponse(
        "project_form.html",
        {
            "request": request,
            "project": None,
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
                "request": None,
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
                end_date.strip() if end_date else None,
            ))
            conn.commit()
        except Exception as e:
            return templates.TemplateResponse(
                "project_form.html",
                {
                    "request": None,
                    "project": {
                        "project_name": project_name,
                        "donor": donor,
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "error": f"Failed to create project: {str(e)}"
                }
            )
    
    return RedirectResponse("/projects", status_code=303)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ============================== END ==============================
