from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import pandas as pd
from reportlab.pdfgen import canvas

app = FastAPI()

# ---------------- STATIC FILES ----------------

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- TEMPLATES ----------------

templates = Jinja2Templates(directory="templates")

# ---------------- DATABASE ----------------

def get_db():
conn = sqlite3.connect("ngo.db")
conn.row_factory = sqlite3.Row
return conn

# ---------------- MODELS ----------------

class Donation(BaseModel):
date: str
description: str
amount: float

class Expense(BaseModel):
date: str
description: str
amount: float

# ---------------- DASHBOARD ----------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):

```
conn = get_db()
cur = conn.cursor()

cur.execute("SELECT SUM(amount) FROM transactions WHERE credit_account=3")
donations = cur.fetchone()[0] or 0

cur.execute("SELECT SUM(amount) FROM transactions WHERE debit_account=4")
expenses = cur.fetchone()[0] or 0

balance = donations - expenses

conn.close()

return templates.TemplateResponse(
    "dashboard.html",
    {
        "request": request,
        "total_donations": donations,
        "total_expenses": expenses,
        "balance": balance,
        "total_projects": 4,
        "project_names": ["Education", "Health", "Food"],
        "project_amounts": [1200, 800, 600]
    }
)
```

@app.get("/dashboard-data")
def dashboard_data():

```
conn = get_db()
cur = conn.cursor()

cur.execute("SELECT SUM(amount) FROM transactions WHERE credit_account=3")
donations = cur.fetchone()[0] or 0

cur.execute("SELECT SUM(amount) FROM transactions WHERE debit_account=4")
expenses = cur.fetchone()[0] or 0

balance = donations - expenses

conn.close()

return {
    "donations": donations,
    "expenses": expenses,
    "balance": balance
}
```

# ---------------- DONATIONS ----------------

@app.post("/add-donation")
def add_donation(donation: Donation):

```
conn = get_db()
cur = conn.cursor()

cur.execute("""
    INSERT INTO transactions
    (date, description, debit_account, credit_account, amount)
    VALUES (?, ?, ?, ?, ?)
""", (
    donation.date,
    donation.description,
    1,
    3,
    donation.amount
))

conn.commit()
conn.close()

return {"message": "Donation added successfully"}
```

# ---------------- EXPENSES ----------------

@app.post("/add-expense")
def add_expense(expense: Expense):

```
conn = get_db()
cur = conn.cursor()

cur.execute("""
    INSERT INTO transactions
    (date, description, debit_account, credit_account, amount)
    VALUES (?, ?, ?, ?, ?)
""", (
    expense.date,
    expense.description,
    4,
    1,
    expense.amount
))

conn.commit()
conn.close()

return {"message": "Expense recorded"}
```

# ---------------- LEDGER ----------------

@app.get("/ledger")
def ledger():

```
conn = get_db()
cur = conn.cursor()

cur.execute("""
    SELECT date, description, debit_account, credit_account, amount
    FROM transactions
    ORDER BY date DESC
""")

rows = cur.fetchall()
conn.close()

return rows
```

# ---------------- EXPORT EXCEL ----------------

@app.get("/export-excel")
def export_excel():

```
conn = get_db()

df = pd.read_sql_query("SELECT * FROM transactions", conn)

file = "financial_report.xlsx"
df.to_excel(file, index=False)

conn.close()

return {"message": "Excel report created"}
```

# ---------------- EXPORT PDF ----------------

@app.get("/export-pdf")
def export_pdf():

```
file = "financial_report.pdf"

c = canvas.Canvas(file)

conn = sqlite3.connect("ngo.db")
cur = conn.cursor()

cur.execute("SELECT date, description, amount FROM transactions")
rows = cur.fetchall()

y = 750
c.drawString(50, 800, "NGO Financial Report")

for row in rows:
    text = f"{row[0]} - {row[1]} - {row[2]}"
    c.drawString(50, y, text)
    y -= 20

conn.close()

c.save()

return FileResponse(file, filename="financial_report.pdf")
```

# ---------------- PAGES ----------------

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

# ---------------- ANALYTICS ----------------

@app.get("/monthly-finance")
def monthly_finance():

```
conn = get_db()
cur = conn.cursor()

cur.execute("""
    SELECT
    substr(date,1,7) as month,
    SUM(CASE WHEN credit_account=3 THEN amount ELSE 0 END) as donations,
    SUM(CASE WHEN debit_account=4 THEN amount ELSE 0 END) as expenses
    FROM transactions
    GROUP BY month
""")

rows = cur.fetchall()
conn.close()

return rows
```

@app.get("/project-expenses")
def project_expenses():

```
conn = get_db()
cur = conn.cursor()

cur.execute("""
    SELECT project_id, SUM(amount)
    FROM transactions
    WHERE debit_account=4
    GROUP BY project_id
""")

rows = cur.fetchall()
conn.close()

return rows
```

@app.get("/income-statement")
def income_statement():

```
conn = get_db()
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
```
