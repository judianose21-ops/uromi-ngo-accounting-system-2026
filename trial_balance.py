import tkinter as tk
import sqlite3


def trial_balance_screen(frame):

    conn = sqlite3.connect("uromi.db")
    cursor = conn.cursor()

    tk.Label(frame,text="Trial Balance",
             font=("Arial",18)).pack(pady=20)

    cursor.execute("""
    SELECT a.name,
    SUM(CASE WHEN j.debit_account=a.id THEN j.amount ELSE 0 END) -
    SUM(CASE WHEN j.credit_account=a.id THEN j.amount ELSE 0 END)
    FROM accounts a
    LEFT JOIN journal j
    ON a.id=j.debit_account OR a.id=j.credit_account
    GROUP BY a.id
    """)

    for acc,balance in cursor.fetchall():

        tk.Label(frame,
                 text=f"{acc} : {balance}",
                 font=("Arial",12)).pack()