import tkinter as tk
import sqlite3


def dashboard_screen(frame):

    # Create database connection
    conn = sqlite3.connect("uromi.db")
    cursor = conn.cursor()

    # Get donors
    cursor.execute("SELECT COUNT(*) FROM donors")
    donors = cursor.fetchone()[0]

    # Get projects
    cursor.execute("SELECT COUNT(*) FROM projects")
    projects = cursor.fetchone()[0]

    # Get income
    cursor.execute("SELECT SUM(debit) FROM transactions")
    income = cursor.fetchone()[0]
    if income is None:
        income = 0

    # Get expenses
    cursor.execute("SELECT SUM(credit) FROM transactions")
    expenses = cursor.fetchone()[0]
    if expenses is None:
        expenses = 0

    balance = income - expenses

    # UI Title
    tk.Label(frame,
             text="UROMI Financial Dashboard",
             font=("Arial", 20)).pack(pady=20)

    # Dashboard cards
    tk.Label(frame, text=f"Total Donors: {donors}",
             font=("Arial", 14)).pack(pady=10)

    tk.Label(frame, text=f"Total Projects: {projects}",
             font=("Arial", 14)).pack(pady=10)

    tk.Label(frame, text=f"Total Income: {income}",
             font=("Arial", 14)).pack(pady=10)

    tk.Label(frame, text=f"Total Expenses: {expenses}",
             font=("Arial", 14)).pack(pady=10)

    tk.Label(frame, text=f"Balance: {balance}",
             font=("Arial", 16, "bold")).pack(pady=20)

    conn.close()