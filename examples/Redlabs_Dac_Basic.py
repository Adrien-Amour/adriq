from adriq.RedLabs_Dac import *

import tkinter as tk
from tkinter import ttk

# Function to apply the voltage to the specified channel
def apply_voltage():
    try:
        channel = int(channel_var.get())
        voltage = float(voltage_var.get())
        write_analog_voltage(channel, voltage)
    except ValueError as e:
        print(f"Invalid input: {e}")

# Create main window
root = tk.Tk()
root.title("Analog Voltage Writer")

# Channel input
tk.Label(root, text="Channel").pack()
channel_var = tk.StringVar()
channel_entry = ttk.Entry(root, textvariable=channel_var)
channel_entry.pack()

# Voltage input
tk.Label(root, text="Voltage").pack()
voltage_var = tk.StringVar()
voltage_entry = ttk.Entry(root, textvariable=voltage_var)
voltage_entry.pack()

# Apply button
apply_button = tk.Button(root, text="Apply Voltage", command=apply_voltage)
apply_button.pack()

# Run the GUI loop
root.mainloop()