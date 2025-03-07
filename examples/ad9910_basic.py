import tkinter as tk
from tkinter import ttk
from adriq.ad9910 import *
import time
import serial.tools.list_ports
from adriq.Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
import threading

# Global flags and threads
scanning = False
scan_thread = None
flashing = False
flash_thread = None

# Function to apply settings
def apply_settings(event=None):
    Standalone_Boards = com_port_var.get()
    Board = int(board_var.get())
    profile = int(profile_var.get())
    A = amplitude_slider.get()
    f = frequency_slider.get() / 10.0  # Scale down the frequency value
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

# Function to flash amplitude
def flash_amplitude():
    global flashing
    flashing = True
    Standalone_Boards = com_port_var.get()
    Board = int(board_var.get())
    profile = int(profile_var.get())
    flash_amp = int(flash_amplitude_entry.get())
    on_time = float(on_time_entry.get())
    off_time = float(off_time_entry.get())

    while flashing:
        single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=flash_amp, Phase_Offset=0, Frequency=frequency_slider.get() / 10.0, Verbose=False)  # Scale down the frequency value
        time.sleep(on_time)
        single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=frequency_slider.get() / 10.0, Verbose=False)  # Scale down the frequency value
        time.sleep(off_time)

# Function to start flashing in a new thread
def start_flash_thread():
    global flash_thread
    if flash_thread is None or not flash_thread.is_alive():
        flash_thread = threading.Thread(target=flash_amplitude)
        flash_thread.start()

# Function to stop flashing
def stop_flashing():
    global flashing
    flashing = False
    if flash_thread is not None:
        flash_thread.join()

# Function to update the displayed frequency value
def update_frequency_label(event=None):
    frequency_value = frequency_slider.get() / 10.0
    frequency_label_var.set(f"Frequency: {frequency_value:.1f} Hz")

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
frequency_slider = tk.Scale(root, from_=1500, to=2500, orient=tk.HORIZONTAL, length=400, resolution=1)  # Scale up by 10
frequency_slider.set(2000)
frequency_slider.pack()
frequency_slider.bind("<ButtonRelease-1>", apply_settings)
frequency_slider.bind("<Motion>", update_frequency_label)

# Frequency label
frequency_label_var = tk.StringVar()
frequency_label_var.set(f"Frequency: {frequency_slider.get() / 10.0:.1f} Hz")
frequency_label = tk.Label(root, textvariable=frequency_label_var)
frequency_label.pack()

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
profile_menu.current(0)  # Default to Profile 7
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

# Flash amplitude settings
tk.Label(root, text="Flash Amplitude").pack()
flash_amplitude_entry = tk.Entry(root)
flash_amplitude_entry.pack()

tk.Label(root, text="On Time (s)").pack()
on_time_entry = tk.Entry(root)
on_time_entry.pack()

tk.Label(root, text="Off Time (s)").pack()
off_time_entry = tk.Entry(root)
off_time_entry.pack()

# Apply General Settings button
general_settings_button = tk.Button(root, text="Apply General Settings", command=apply_general_settings)
general_settings_button.pack()

# Frequency Scan button
scan_button = tk.Button(root, text="Scan Frequency", command=start_scan_thread)
scan_button.pack()

# Stop Scan button
stop_button = tk.Button(root, text="Stop Scan", command=stop_scanning)
stop_button.pack()

# Flash Amplitude button
flash_button = tk.Button(root, text="Flash Amplitude", command=start_flash_thread)
flash_button.pack()

# Stop Flash button
stop_flash_button = tk.Button(root, text="Stop Flash", command=stop_flashing)
stop_flash_button.pack()

# Run the GUI loop
root.mainloop()