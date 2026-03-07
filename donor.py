import tkinter as tk
from tkinter import messagebox
from database import get_connection


def donor_screen():

    win = tk.Toplevel()
    win.title("Donor Management")
    win.geometry("450x400")

    tk.Label(win, text="Donor Name").pack()
    name = tk.Entry(win)
    name.pack()

    tk.Label(win, text="Email").pack()
    email = tk.Entry(win)
    email.pack()

    tk.Label(win, text="Phone").pack()
    phone = tk.Entry(win)
    phone.pack()

    listbox = tk.Listbox(win, width=60)
    listbox.pack(pady=10)

    def load_donors():

        listbox.delete(0, tk.END)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, email, phone FROM donors")

        for row in cursor.fetchall():
            listbox.insert(tk.END, row)

        conn.close()

    def add_donor():

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO donors (name, email, phone) VALUES (?,?,?)",
            (name.get(), email.get(), phone.get())
        )

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Donor Added")

        load_donors()

    tk.Button(win, text="Add Donor", command=add_donor).pack(pady=5)

    load_donors()