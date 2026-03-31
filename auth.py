import tkinter as tk
from tkinter import messagebox
from database import get_connection
from passlib.context import CryptContext

# 🔐 Password setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def login_screen(start_app):

    window = tk.Tk()
    window.title("UROMI Login")
    window.geometry("320x220")
    window.resizable(False, False)

    tk.Label(window, text="UROMI Login", font=("Arial", 14, "bold")).pack(pady=10)

    tk.Label(window, text="Username").pack()
    username = tk.Entry(window)
    username.pack(pady=5)

    tk.Label(window, text="Password").pack()
    password = tk.Entry(window, show="*")
    password.pack(pady=5)

    def login():
        user_input = username.get().strip()
        pass_input = password.get().strip()

        if not user_input or not pass_input:
            messagebox.showerror("Error", "Please enter username and password")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # ✅ Get user by username ONLY
            cursor.execute(
                "SELECT password, role FROM users WHERE username=?",
                (user_input,)
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                stored_password, role = result

                # ✅ Verify hashed password
                if verify_password(pass_input, stored_password):
                    window.destroy()
                    start_app(role)
                    return

            # ❌ If anything fails
            messagebox.showerror("Error", "Invalid username or password")

        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {str(e)}")

    tk.Button(window, text="Login", width=15, command=login).pack(pady=15)

    window.mainloop()