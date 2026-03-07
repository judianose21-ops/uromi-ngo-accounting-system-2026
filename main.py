import tkinter as tk

from database import initialize
from auth import login_screen
from accounts import accounts_screen
from project import project_screen
from transaction import transaction_screen
from reports import trial_balance_screen, income_expense_screen


# Initialize database
initialize()


def start_app(role):

    app = tk.Tk()
    app.title("UROMI PRO NGO Accounting System")
    app.geometry("900x500")
    app.configure(bg="white")

    # Sidebar
    sidebar = tk.Frame(app, bg="#2c3e50", width=200)
    sidebar.pack(side="left", fill="y")

    # Main area
    main_area = tk.Frame(app, bg="white")
    main_area.pack(side="right", expand=True, fill="both")

    title = tk.Label(
        main_area,
        text="UROMI PRO Dashboard",
        font=("Arial", 20, "bold"),
        bg="white"
    )
    title.pack(pady=20)

    # Sidebar title
    tk.Label(
        sidebar,
        text="UROMI",
        bg="#2c3e50",
        fg="white",
        font=("Arial", 16, "bold")
    ).pack(pady=20)

    btn_style = {
        "bg": "#34495e",
        "fg": "white",
        "width": 20,
        "height": 2,
        "bd": 0
    }

    # Buttons
    tk.Button(sidebar, text="Chart of Accounts", command=accounts_screen, **btn_style).pack(pady=5)
    tk.Button(sidebar, text="Projects", command=project_screen, **btn_style).pack(pady=5)
    tk.Button(sidebar, text="Transactions", command=transaction_screen, **btn_style).pack(pady=5)
    tk.Button(sidebar, text="Trial Balance", command=trial_balance_screen, **btn_style).pack(pady=5)
    tk.Button(sidebar, text="Income & Expense", command=income_expense_screen, **btn_style).pack(pady=5)
    tk.Button(sidebar, text="Donors", command=donor_screen, **btn_style).pack(pady=5)
    if role == "admin":
        tk.Label(
            sidebar,
            text="Admin Access",
            bg="#2c3e50",
            fg="#2ecc71",
            font=("Arial", 10, "bold")
        ).pack(pady=30)

    app.mainloop()
from donor import donor_screen

# Start login
login_screen(start_app)