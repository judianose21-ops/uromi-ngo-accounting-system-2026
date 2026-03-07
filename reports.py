import tkinter as tk
from database import get_connection


def trial_balance_screen():

    win = tk.Toplevel()
    win.title("Trial Balance")
    win.geometry("500x400")

    listbox = tk.Listbox(win, width=70)
    listbox.pack(pady=20)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT account_name FROM chart_of_accounts")
    accounts = cursor.fetchall()

    for acc in accounts:

        name = acc[0]

        cursor.execute(
            "SELECT SUM(amount) FROM transactions WHERE debit_account=?",
            (name,)
        )
        debit = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT SUM(amount) FROM transactions WHERE credit_account=?",
            (name,)
        )
        credit = cursor.fetchone()[0] or 0

        balance = debit - credit

        listbox.insert(
            tk.END,
            f"{name} | Debit: {debit} | Credit: {credit} | Balance: {balance}"
        )

    conn.close()


def income_expense_screen():

    win = tk.Toplevel()
    win.title("Income & Expense Report")
    win.geometry("400x300")

    conn = get_connection()
    cursor = conn.cursor()

    # Total Income
    cursor.execute("""
    SELECT SUM(amount) FROM transactions
    WHERE credit_account='Donations'
    """)
    income = cursor.fetchone()[0] or 0

    # Total Expenses
    cursor.execute("""
    SELECT SUM(amount) FROM transactions
    WHERE debit_account LIKE '%Expense%'
    """)
    expenses = cursor.fetchone()[0] or 0

    surplus = income - expenses

    tk.Label(win, text="Income & Expense Report", font=("Arial", 16)).pack(pady=20)

    tk.Label(win, text=f"Total Income: {income}", font=("Arial", 12)).pack(pady=5)
    tk.Label(win, text=f"Total Expenses: {expenses}", font=("Arial", 12)).pack(pady=5)
    tk.Label(win, text=f"Net Surplus: {surplus}", font=("Arial", 12)).pack(pady=5)

    conn.close()