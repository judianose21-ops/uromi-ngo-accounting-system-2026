from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
from fastapi import FastAPI
import sqlite3

app = FastAPI()

def get_db():
    conn = sqlite3.connect("ngo.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard-data")
def dashboard_data():
    import sqlite3
    
    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    # Donations
    cur.execute("SELECT SUM(amount) FROM transactions WHERE credit_account=3")
    donations = cur.fetchone()[0] or 0

    # Expenses
    cur.execute("SELECT SUM(amount) FROM transactions WHERE debit_account=4")
    expenses = cur.fetchone()[0] or 0

    balance = donations - expenses

    conn.close()

    return {
        "donations": donations,
        "expenses": expenses,
        "balance": balance
    }
    # total income
    cur.execute("SELECT SUM(amount) FROM transactions WHERE amount > 0")
    donations = cur.fetchone()[0] or 0

    # total expenses
    cur.execute("SELECT SUM(amount) FROM transactions WHERE amount < 0")
    expenses = cur.fetchone()[0] or 0

    balance = donations + expenses

    return {
        "donations": donations,
        "expenses": abs(expenses),
        "balance": balance
    }
from pydantic import BaseModel

class Donation(BaseModel):
    date: str
    description: str
    amount: float
@app.post("/add-donation")
def add_donation(donation: Donation):
    import sqlite3
    
    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO transactions (date, description, debit_account, credit_account, amount)
    VALUES (?, ?, ?, ?, ?)
    """, (
        donation.date,
        donation.description,
        1,  # Cash
        3,  # Donations
        donation.amount
    ))

    conn.commit()
    conn.close()

    return {"message": "Donation added successfully"}
class Expense(BaseModel):
    date: str
    description: str
    amount: float
@app.post("/add-expense")
def add_expense(expense: Expense):
    import sqlite3
    
    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO transactions (date, description, debit_account, credit_account, amount)
    VALUES (?, ?, ?, ?, ?)
    """, (
        expense.date,
        expense.description,
        4,  # Expenses
        1,  # Cash
        expense.amount
    ))

    conn.commit()
    conn.close()

    return {"message": "Expense recorded"}
@app.get("/ledger")
def ledger():
    import sqlite3
    
    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT date, description, debit_account, credit_account, amount
    FROM transactions
    ORDER BY date DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows
@app.get("/export-excel")
def export_excel():
    import pandas as pd
    import sqlite3

    conn = sqlite3.connect("ngo.db")

    df = pd.read_sql_query("SELECT * FROM transactions", conn)

    file = "financial_report.xlsx"
    df.to_excel(file, index=False)

    conn.close()

    return {"message": "Excel report created"}
@app.get("/donations", response_class=HTMLResponse)
def donations_page(request: Request):
    return templates.TemplateResponse("donations.html", {"request": request})


@app.get("/expenses", response_class=HTMLResponse)
def expenses_page(request: Request):
    return templates.TemplateResponse("expenses.html", {"request": request})


@app.get("/ledger-page", response_class=HTMLResponse)
def ledger_page(request: Request):
    return templates.TemplateResponse("ledger.html", {"request": request})


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    return templates.TemplateResponse("projects.html", {"request": request})


@app.get("/budgets", response_class=HTMLResponse)
def budgets_page(request: Request):
    return templates.TemplateResponse("budgets.html", {"request": request})
@app.get("/monthly-finance")
def monthly_finance():

    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT substr(date,1,7) as month,
    SUM(CASE WHEN credit_account=3 THEN amount ELSE 0 END) as donations,
    SUM(CASE WHEN debit_account=4 THEN amount ELSE 0 END) as expenses
    FROM transactions
    GROUP BY month
    """)

    rows = cur.fetchall()
    conn.close()

    return rows
@app.get("/project-expenses")
def project_expenses():

    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT project_id,SUM(amount)
    FROM transactions
    WHERE debit_account=4
    GROUP BY project_id
    """)

    rows = cur.fetchall()

    conn.close()

    return rows
@app.get("/income-statement")
def income_statement():

    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute("SELECT SUM(amount) FROM transactions WHERE credit_account=3")
    donations = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM transactions WHERE debit_account=4")
    expenses = cur.fetchone()[0] or 0

    net = donations - expenses

    conn.close()

    return {
        "donations": donations,
        "expenses": expenses,
        "net_income": net
    }