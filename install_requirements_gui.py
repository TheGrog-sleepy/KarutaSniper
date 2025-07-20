import subprocess
import sys
import tkinter as tk
from tkinter import scrolledtext

# Add the new packages to the list of requirements
requirements = [
    "Levenshtein",
    "pillow",
    "pytesseract",
    "requests",
    "colorama",
    "opencv-python",
    "git+https://github.com/dolfies/discord.py-self.git",
    "pypiwin32",
    "pycryptodome",
    "aiohttp>=3.7.4,<4",
    "tzlocal>=4.0.0,<6",
    "discord_protos<1.0.0",
    "audioop-lts; python_version>='3.13'"
]

# Function to install a package
def install_package(package, text_widget):
    try:
        text_widget.insert(tk.END, f"Installing {package}...\n")
        text_widget.yview(tk.END)
        text_widget.update()
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        text_widget.insert(tk.END, f"Successfully installed {package}\n")
    except subprocess.CalledProcessError:
        text_widget.insert(tk.END, f"Failed to install {package}\n")
    text_widget.yview(tk.END)
    text_widget.update()

# Function to install all requirements
def install_requirements(text_widget):
    for package in requirements:
        install_package(package, text_widget)

# Create the GUI window
def create_gui():
    window = tk.Tk()
    window.title("Installing Requirements...")

    # Add a scrolled text widget to show progress
    text_widget = scrolledtext.ScrolledText(window, width=50, height=20, wrap=tk.WORD)
    text_widget.pack(padx=10, pady=10)

    # Add a button to start the installation
    install_button = tk.Button(window, text="Start Installation", command=lambda: install_requirements(text_widget))
    install_button.pack(pady=5)

    # Start the GUI loop
    window.mainloop()

if __name__ == "__main__":
    create_gui()
