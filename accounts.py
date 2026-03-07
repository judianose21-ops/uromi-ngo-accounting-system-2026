import tkinter as tk
from tkinter import messagebox
from database import get_connection


def accounts_screen():

    win = tk.Toplevel()
    win.title("Chart of Accounts")
    win.geometry("500x400")

    tk.Label(win, text="Account Name").pack()
    account_name = tk.Entry(win)
    account_name.pack()

    tk.Label(win, text="Account Type").pack()
    account_type = tk.Entry(win)
    account_type.pack()

    tk.Label(win, text="Description").pack()
    description = tk.Entry(win)
    description.pack()

    listbox = tk.Listbox(win, width=60)
    listbox.pack(pady=10)

    def load_accounts():

        listbox.delete(0, tk.END)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, account_name, account_type FROM chart_of_accounts")

        for row in cursor.fetchall():
            listbox.insert(tk.END, row)

        conn.close()

    def add_account():

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO chart_of_accounts (account_name, account_type, description) VALUES (?,?,?)",
            (account_name.get(), account_type.get(), description.get())
        )

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Account Added")

        load_accounts()

    tk.Button(win, text="Add Account", command=add_account).pack(pady=5)

    load_accounts()