import tkinter as tk
from tkinter import ttk
from adriq.ad9910 import *
import time
import serial.tools.list_ports
from adriq.Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
import threading

# Global flag to control scanning
scanning = False
scan_thread = None

# Function to apply settings
def apply_settings(event=None):
    Standalone_Boards = com_port_var.get()
    Board = int(board_var.get())
    profile = int(profile_var.get())
    A = amplitude_slider.get()
    f = frequency_slider.get()
    p = 0  # Assuming phase is fixed at 0

    print("Profile Setting profile:", profile, "of Board:", Board, "on COM port:", Standalone_Boards, "Amplitude:", A, "Frequency:", f, "Phase:", p)
    single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=A, Phase_Offset=p, Frequency=f, Verbose=False)

# Function to apply general settings
def apply_general_settings():
    Standalone_Boards = com_port_var.get()
    Board = int(board_var.get())
    print("General Setting Board:", Board, "on COM port:", Standalone_Boards)
    general_setting_standalone(Standalone_Boards, Board)

# Function to get available COM ports
def get_com_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

# Function to reset the upper limit of the slider
def reset_upper_limit(event=None):
    upper_limit_spinbox.set(5000)
    amplitude_slider.config(to=5000)

# Function to scan frequency
def scan_frequency():
    global scanning
    scanning = True
    Standalone_Boards = com_port_var.get()
    Board = int(board_var.get())
    profile = int(profile_var.get())
    A = amplitude_slider.get()
    f_start = float(frequency_start_entry.get())
    f_end = float(frequency_end_entry.get())
    points = int(points_entry.get())
    timestep = float(timestep_entry.get())

    f_step = (f_end - f_start) / (points - 1)
    while scanning:
        # Scan up
        for i in range(points):
            if not scanning:
                break
            f = f_start + i * f_step
            print(f"Scanning frequency: {f} Hz")
            single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=A, Phase_Offset=0, Frequency=f, Verbose=False)
            time.sleep(timestep)
        # Scan down
        for i in range(points):
            if not scanning:
                break
            f = f_end - i * f_step
            print(f"Scanning frequency: {f} Hz")
            single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=A, Phase_Offset=0, Frequency=f, Verbose=False)
            time.sleep(timestep)

# Function to start scanning in a new thread
def start_scan_thread():
    global scan_thread
    if scan_thread is None or not scan_thread.is_alive():
        scan_thread = threading.Thread(target=scan_frequency)
        scan_thread.start()

# Function to stop scanning
def stop_scanning():
    global scanning
    scanning = False
    if scan_thread is not None:
        scan_thread.join()

# Create main window
root = tk.Tk()
root.title("AD9910 Profile Settings")

# COM port selection
tk.Label(root, text="COM Port").pack()
com_port_var = tk.StringVar()
com_port_menu = ttk.Combobox(root, textvariable=com_port_var)
com_port_menu['values'] = get_com_ports()
com_port_menu.current(0)  # Default to the first available COM port
com_port_menu.pack()
com_port_menu.bind("<<ComboboxSelected>>", reset_upper_limit)

# Amplitude slider
tk.Label(root, text="Amplitude").pack()
amplitude_slider = tk.Scale(root, from_=0, to=5000, orient=tk.HORIZONTAL, length=400)
amplitude_slider.set(1500)
amplitude_slider.pack()
amplitude_slider.bind("<ButtonRelease-1>", apply_settings)

# Frequency slider
tk.Label(root, text="Frequency").pack()
frequency_slider = tk.Scale(root, from_=0, to=1000, orient=tk.HORIZONTAL, length=400)
frequency_slider.set(200)
frequency_slider.pack()
frequency_slider.bind("<ButtonRelease-1>", apply_settings)

# Upper limit spinbox
tk.Label(root, text="Amplitude Upper Limit").pack()
upper_limit_spinbox = CustomSpinbox(root, from_=0, to=2**14-1, increment=100) #14 bit ASF
upper_limit_spinbox.set(5000)
upper_limit_spinbox.pack()
upper_limit_spinbox.bind("<ButtonRelease-1>", lambda event: amplitude_slider.config(to=int(upper_limit_spinbox.get())))

# Board selection
tk.Label(root, text="Board").pack()
board_var = tk.StringVar()
board_menu = ttk.Combobox(root, textvariable=board_var)
board_menu['values'] = [str(i) for i in range(8)]
board_menu.current(3)  # Default to Board 3
board_menu.pack()
board_menu.bind("<<ComboboxSelected>>", reset_upper_limit)

# Profile selection
tk.Label(root, text="Profile").pack()
profile_var = tk.StringVar()
profile_menu = ttk.Combobox(root, textvariable=profile_var)
profile_menu['values'] = [str(i) for i in range(8)]
profile_menu.current(7)  # Default to Profile 7
profile_menu.pack()

# Frequency scan settings
tk.Label(root, text="Frequency Start (Hz)").pack()
frequency_start_entry = tk.Entry(root)
frequency_start_entry.pack()

tk.Label(root, text="Frequency End (Hz)").pack()
frequency_end_entry = tk.Entry(root)
frequency_end_entry.pack()

tk.Label(root, text="Number of Points").pack()
points_entry = tk.Entry(root)
points_entry.pack()

tk.Label(root, text="Timestep (s)").pack()
timestep_entry = tk.Entry(root)
timestep_entry.pack()

# Apply General Settings button
general_settings_button = tk.Button(root, text="Apply General Settings", command=apply_general_settings)
general_settings_button.pack()

# Frequency Scan button
scan_button = tk.Button(root, text="Scan Frequency", command=start_scan_thread)
scan_button.pack()

# Stop Scan button
stop_button = tk.Button(root, text="Stop Scan", command=stop_scanning)
stop_button.pack()

# Run the GUI loop
root.mainloop()