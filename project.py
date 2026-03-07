import tkinter as tk
from tkinter import messagebox
from database import get_connection


def project_screen():

    win = tk.Toplevel()
    win.title("Projects")
    win.geometry("500x450")

    tk.Label(win, text="Project Name").pack()
    project_name = tk.Entry(win)
    project_name.pack()

    tk.Label(win, text="Donor").pack()
    donor = tk.Entry(win)
    donor.pack()

    tk.Label(win, text="Project Budget").pack()
    budget = tk.Entry(win)
    budget.pack()

    listbox = tk.Listbox(win, width=70)
    listbox.pack(pady=10)

    def load_projects():

        listbox.delete(0, tk.END)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, project_name, donor, budget FROM projects")

        for row in cursor.fetchall():

            project_id = row[0]
            name = row[1]
            donor_name = row[2]
            budget_value = row[3]

            # calculate expenses
            cursor.execute(
                "SELECT SUM(amount) FROM transactions WHERE project_id=?",
                (name,)
            )

            spent = cursor.fetchone()[0] or 0
            remaining = float(budget_value) - float(spent)

            listbox.insert(
                tk.END,
                f"{name} | Donor: {donor_name} | Budget: {budget_value} | Spent: {spent} | Remaining: {remaining}"
            )

        conn.close()

    def add_project():

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO projects (project_name, donor, budget) VALUES (?,?,?)",
            (project_name.get(), donor.get(), budget.get())
        )

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Project Added")

        load_projects()

    tk.Button(win, text="Add Project", command=add_project).pack(pady=10)

    load_projects()