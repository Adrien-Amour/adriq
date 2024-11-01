import tkinter as tk
import json
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib import style
import nidaqmx
from nidaqmx.constants import CountDirection, Edge
import time
from ad9910 import *
from Count_Managers import *
import threading
import QuTau
import numpy as np
import os
from tkinter import BooleanVar
from RedLabs_Dac import *
from Custom_Tkinter import CustomSpinbox
from tkinter import ttk

class CountPrinter(tk.Frame):
    def __init__(self, parent, count_manager, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.count_manager = count_manager

        # Create a sunken frame to hold the label
        self.sunken_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
        self.sunken_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create a label inside the sunken frame
        self.label = tk.Label(self.sunken_frame, text="No counts available yet.", font=("Helvetica", 20))
        self.label.pack(padx=10, pady=10)

        # Start the printing thread
        self.update_thread = threading.Thread(target=self.update_count, daemon=True)
        self.update_thread.start()

    def update_count(self):
        while True:
            if self.count_manager.counting and self.count_manager.counts:
                last_count = self.count_manager.counts[-1]
                self.label.config(text=f"{last_count}")
            else:
                self.label.config(text="No counts available yet.")
            time.sleep(1 / self.count_manager.rate)
 
class LoadControlPanel(tk.Frame):
    def __init__(self, parent, DAC_Board_Num, Shutter_Pin, Oven_Pin, Count_Manager, Threshold, Timeout, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Store parameters as class attributes
        self.DAC_Board_Num = DAC_Board_Num
        self.Shutter_Pin = Shutter_Pin
        self.Oven_Pin = Oven_Pin
        self.Count_Manager = Count_Manager
        
        # Initialize DoubleVars with initial values from arguments
        self.Threshold = tk.DoubleVar(value=Threshold)
        self.Timeout = tk.DoubleVar(value=Timeout)
        self.remaining_time = tk.DoubleVar(value=0)  # Assuming remaining time starts at 0
        
        # Flag to control loading
        self.loading = False
        
        # GUI setup
        self.configure(padx=10, pady=10)

        # Create a raised frame to hold all widgets
        self.control_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        self.control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Create widgets inside the raised frame
        self.create_widgets()

    def create_widgets(self):
        # Threshold input
        ttk.Label(self.control_frame, text="Threshold:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.threshold_entry = ttk.Entry(self.control_frame, textvariable=self.Threshold)
        self.threshold_entry.grid(row=0, column=1, padx=10, pady=10)

        # Timeout input
        ttk.Label(self.control_frame, text="Timeout (s):").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.timeout_entry = ttk.Entry(self.control_frame, textvariable=self.Timeout)
        self.timeout_entry.grid(row=1, column=1, padx=10, pady=10)

        # Countdown display
        ttk.Label(self.control_frame, text="Remaining Time:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.time_label = ttk.Label(self.control_frame, textvariable=self.remaining_time, relief=tk.SUNKEN, borderwidth=2, width=20)  # Adjust the width as needed
        self.time_label.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # Start button
        self.start_button = ttk.Button(self.control_frame, text="Start", command=self.start_load)
        self.start_button.grid(row=3, columnspan=2, padx=10, pady=10)

    def start_load(self):
        # Disable the start button to prevent multiple starts
        self.start_button.config(state=tk.DISABLED)
        
        # Start the countdown timer in a separate thread
        self.loading = True
        self.remaining_time.set(self.Timeout.get())
        threading.Thread(target=self.countdown, daemon=True).start()
        
        # Start the load function in a separate thread
        threading.Thread(target=self.load_function, daemon=True).start()

    def countdown(self):
        timeout = self.Timeout.get()
        while timeout > 0 and self.loading:
            time.sleep(1)
            timeout -= 1
            self.remaining_time.set(timeout)
        
        # Stop the load function if the countdown completes
        self.loading = False
        # Re-enable the start button when the countdown is done
        self.start_button.config(state=tk.NORMAL)

    def load_function(self):
        # Call the load function and check for the threshold
        result = load(
            self.Shutter_Pin,
            self.Oven_Pin,
            self.Count_Manager,
            self.Threshold.get(),
            self.Timeout.get()
        )
        
        # Handle the result
        if not result:  # If load returns False, the threshold was exceeded
            self.loading = False
        
        # Ensure the start button is re-enabled after load function completes
        self.start_button.config(state=tk.NORMAL)

# class MainApp(tk.Tk):
#     def __init__(self):
#         super().__init__()

#         # Set up main window properties
#         self.title("Control Centre")
#         self.geometry("1500x800")  # Set the size of the main window


#     def _setup_lasers(self):
#         """Set up lasers on standalone boards."""
#         calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"
#         standalone_boards = "COM9"
#         standalone_lasers = [
#             ("397b", 0, "397b_calib.csv", 2900),
#             ("OP 866", 1, "854_rp_calib.csv", 10700),
#             ("397a", 2, "397a_calib.csv", 2400),
#             ("RP 854", 3, "854_rp_calib.csv", 4800),
#             ("SP 854 (Temporary)", 4, "854_calib.csv", 7300),
#             ("RP 850", 5, "850_rp_calib.csv", 7450),
#             ("866", 6, "866_calib.csv", 7800)
#         ]

#         for name, board, calibration_file, max_power in standalone_lasers:
#             calibration_path = os.path.join(calib_directory, calibration_file)  # Correct path joining
#             laser = Laser(name, standalone_boards, "standalone", board, calibration_path, max_power)
#             self.laser_control._add_laser(laser)

#         # Uncomment and modify the following block to add more standalone lasers if needed
#         # standalone_boards = "COM10"
#         # standalone_lasers = [
#         #     ("SP 850 (1)", 0, "397b_calib.csv", 2900),
#         #     ("SP 850 (2)", 1, "854_rp_calib.csv", 10700),
#         #     ("SP 854 (1)", 2, "397a_calib.csv", 2400),
#         #     ("SP 854 (2)", 3, "854_rp_calib.csv", 4800)]
#         #
#         # for name, board, calibration_file, max_power in standalone_lasers:
#         #     calibration_path = os.path.join(calib_directory, calibration_file)
#         #     laser = Laser(name, standalone_boards, "standalone", board, calibration_path, max_power)
#         #     self.laser_control._add_laser(laser)

#     def _setup_presets(self):
#         """Set up quick presets for laser control."""
#         self.laser_control._quick_preset("presets/Cooling.json", "Cooling", color="lightblue")
#         self.laser_control._quick_preset("presets/trapping.json", "trapping", color="lightcoral")

#     def _setup_graphs(self):
#         """Create and place graph widgets in the GUI."""
#         self.graph_frame = tk.Frame(self)  # Create a new frame for stacking graphs
#         self.graph_frame.pack(side='left', fill='both', expand=True)  # Pack the frame to the left side and expand it

#         # PMT manager and live plotting
#         self.pmt_manager = get_pmt_manager()
#         self.pmt_counts = Live_Plot(self, self.pmt_manager)
#         self.pmt_counts.pack(side='top', fill='both', expand=False)

#         # Uncomment to add QuTau manager and live plotting
#         # self.qutau_manager = get_qutau_manager()
#         # self.qutau_counts = Live_Plot(self, self.qutau_manager)
#         # self.qutau_counts.pack(side='bottom', fill='both', expand=False)

#     def _setup_load_control_panel(self):
#         """Initialize the loadControlPanel as part of the main application."""
#         DAC_Board_Num = 0
#         Shutter_Pin = 0
#         Oven_Pin = 1
#         load_panel = LoadControlPanel(self, DAC_Board_Num, Shutter_Pin, Oven_Pin, self.pmt_manager, 2000, 100)
#         load_panel.pack(padx=20, pady=20)



def create_laser_objects():
    """Creates laser objects based on the given configuration."""
    calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"
    standalone_boards = "COM9"
    standalone_lasers = [
        ("397b", 0, "397b_calib.csv", 2900),
        ("OP 866", 1, "854_rp_calib.csv", 10700),
        ("397a", 2, "397a_calib.csv", 2400),
        ("RP 854", 3, "854_rp_calib.csv", 4800),
        ("SP 854 (Temporary)", 4, "854_calib.csv", 7300),
        ("RP 850", 5, "850_rp_calib.csv", 7450),
        ("866", 6, "866_calib.csv", 7800)
    ]
    
    lasers = []
    for name, board, calib_file, max_rf_power in standalone_lasers:
        # Create a laser object
        print(type(board),board)
        laser = Laser(name, standalone_boards, "standalone", board, f"{calib_directory}\\{calib_file}", max_rf_power)
        lasers.append(laser)
    
    return lasers


def run_laser_control_app():
    """Runs the main app that includes the LaserControl widget."""
    # Create the root Tkinter window
    root = tk.Tk()
    root.title("Laser Control App")
    
    # Create and pack the LaserControl widget
    laser_control = LaserControl(root)
    laser_control.pack(fill=tk.BOTH, expand=True)

    # Create laser objects and add them to the LaserControl widget
    lasers = create_laser_objects()
    for laser in lasers:
        laser_control.add_laser(laser)

    # Start the Tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    run_laser_control_app()