import os
from PIL import Image
import subprocess

# ---------------- CONFIG ---------------- #
png_path = "70ba05d1-10ed-4384-a233-d7689b19e0eb.png"  # your uploaded PNG
ico_path = "uromi.ico"
exe_name = "UROMI"
main_script = "main.py"

# ---------------- CONVERT PNG TO ICO ---------------- #
print("Converting PNG to ICO...")
img = Image.open(png_path)
img.save(ico_path, format='ICO', sizes=[(256,256)])
print(f"Saved icon as {ico_path}")

# ---------------- BUILD EXE ---------------- #
print("Building UROMI.exe with PyInstaller...")

# PyInstaller command
cmd = [
    "pyinstaller",
    "--onefile",
    "--windowed",
    f"--name={exe_name}",
    f"--icon={ico_path}",
    main_script
]

subprocess.run(cmd)
print("Build finished!")
print("Your UROMI.exe will be in the dist/ folder")