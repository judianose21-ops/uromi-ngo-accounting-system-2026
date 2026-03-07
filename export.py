import sqlite3
import pandas as pd


def export_transactions():

    conn = sqlite3.connect("uromi.db")

    df = pd.read_sql_query(
        "SELECT * FROM transactions", conn)

    df.to_excel("transactions.xlsx", index=False)

    conn.close()

from export import export_transactions

tk.Button(frame,text="Export Excel",
command=export_transactions).grid(row=1,column=4)