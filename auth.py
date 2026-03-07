import tkinter as tk
from tkinter import messagebox
from database import get_connection


def login_screen(start_app):

    window = tk.Tk()
    window.title("UROMI Login")
    window.geometry("300x200")

    tk.Label(window, text="Username").pack()
    username = tk.Entry(window)
    username.pack()

    tk.Label(window, text="Password").pack()
    password = tk.Entry(window, show="*")
    password.pack()

    def login():

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT role FROM users WHERE username=? AND password=?",
            (username.get(), password.get())
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            window.destroy()
            start_app(result[0])
        else:
            messagebox.showerror("Error", "Invalid login")

    tk.Button(window, text="Login", command=login).pack(pady=10)

    window.mainloop()