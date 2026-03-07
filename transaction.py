import tkinter as tk
from tkinter import messagebox
from database import get_connection


def transaction_screen():

    win = tk.Toplevel()
    win.title("Transactions")
    win.geometry("500x450")

    conn = get_connection()
    cursor = conn.cursor()

    # DATE
    tk.Label(win, text="Date").pack()
    date = tk.Entry(win)
    date.pack()

    # DESCRIPTION
    tk.Label(win, text="Description").pack()
    description = tk.Entry(win)
    description.pack()

    # AMOUNT
    tk.Label(win, text="Amount").pack()
    amount = tk.Entry(win)
    amount.pack()

    # DEBIT ACCOUNT
    tk.Label(win, text="Debit Account").pack()
    debit_var = tk.StringVar()
    debit_menu = tk.OptionMenu(win, debit_var, "")
    debit_menu.pack()

    # CREDIT ACCOUNT
    tk.Label(win, text="Credit Account").pack()
    credit_var = tk.StringVar()
    credit_menu = tk.OptionMenu(win, credit_var, "")
    credit_menu.pack()

    # PROJECT
    tk.Label(win, text="Project").pack()
    project_var = tk.StringVar()
    project_menu = tk.OptionMenu(win, project_var, "")
    project_menu.pack()

    # TRANSACTION LIST
    listbox = tk.Listbox(win, width=70)
    listbox.pack(pady=10)

    # LOAD ACCOUNTS
    cursor.execute("SELECT account_name FROM chart_of_accounts")
    accounts = [row[0] for row in cursor.fetchall()]

    debit_menu["menu"].delete(0, "end")
    credit_menu["menu"].delete(0, "end")

    for acc in accounts:
        debit_menu["menu"].add_command(label=acc, command=lambda v=acc: debit_var.set(v))
        credit_menu["menu"].add_command(label=acc, command=lambda v=acc: credit_var.set(v))

    # LOAD PROJECTS
    cursor.execute("SELECT project_name FROM projects")
    projects = [row[0] for row in cursor.fetchall()]

    project_menu["menu"].delete(0, "end")

    for proj in projects:
        project_menu["menu"].add_command(label=proj, command=lambda v=proj: project_var.set(v))

    conn.close()

    # LOAD TRANSACTIONS
    def load_transactions():

        listbox.delete(0, tk.END)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT date, description, debit_account, credit_account, amount, project_id
        FROM transactions
        """)

        for row in cursor.fetchall():
            listbox.insert(tk.END, row)

        conn.close()

    # ADD TRANSACTION
    def add_transaction():

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO transactions
            (date, description, debit_account, credit_account, amount, project_id)
            VALUES (?,?,?,?,?,?)
            """,
            (
                date.get(),
                description.get(),
                debit_var.get(),
                credit_var.get(),
                amount.get(),
                project_var.get()
            )
        )

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Transaction Saved")

        load_transactions()

    tk.Button(win, text="Save Transaction", command=add_transaction).pack(pady=10)

    load_transactions()