# Standard library imports
import time
import atexit
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import socket
import pickle


# Third-party imports
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
# Local application/library-specific imports
from mcculw import ul
from mcculw.enums import (ErrorCode, Status, ChannelType, TimerIdleState,
                          PulseOutOptions, TInOptions, ULRange, DigitalIODirection)
from mcculw.structs import DaqDeviceDescriptor
from mcculw.device_info import DaqDeviceInfo
from .Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
from .Counters import sine_wave, MicromotionWindow
from .Servers import Server

from adriq.pulse_sequencer import *

#at the moment i initialise the dac every time it is addressed
#This is to avoid any potential errors with addressing long after initialisation
#can be changed in the future but doesn't have a big effect as this is fast compared to what we want to do with the dac.
Redlabs_Dac = 0
v1_chan, v2_chan, v3_chan, v4_chan = 4, 3, 1, 2
Shutter_Pin = 0
Oven_Pin = 1
rf_atten_chan = 7
daq_dev_info = DaqDeviceInfo(Redlabs_Dac)
ao_info = daq_dev_info.get_ao_info()
ao_range = ao_info.supported_ranges[0]
dio_info = daq_dev_info.get_dio_info()


def write_analog_voltage(Channel, Voltage):
    print(f"Writing {Voltage} V to channel {Channel}")
    raw_value = ul.from_eng_units(Redlabs_Dac, ao_range, Voltage)
    try:
        ul.a_out(Redlabs_Dac, Channel, ao_range, raw_value)
    except ULError as e:
        show_ul_error(e)
  
def dc_min_shift(H, V, Q=0, S=0):
    """
    Calculate V_i based on the provided values.
 
    Parameters:
    - H: Value for H = (V_1 + V_4) - (V_2 + V_3)
    - V: Value for V = (V_1 + V_2) - (V_3 + V_4)
    - Q: Value for Q = (V_1 + V_3) - (V_2 + V_4) (default is 0)
    - S: Value for S = (V_1 + V_2) - (V_3 + V_4) (default is 0)
 
    Returns:
    - Tuple containing V_1, V_2, V_3, and V_4.
    """
 
    # Calculate V_2, V_3, and V_4 using the provided formulas
    V_1 = (H + V + Q + S) / 4
    V_2 = (V + S - H - Q) / 4
    V_3 = (Q + S - H - V) / 4
    V_4 = (H + S - V - Q) / 4
    write_analog_voltage(v1_chan, V_1)
    write_analog_voltage(v2_chan, V_2)
    write_analog_voltage(v3_chan, V_3)
    write_analog_voltage(v4_chan, V_4)
    # print(V_1, V_2, V_3, V_4)
    return V_1, V_2, V_3, V_4

def scan_dc_min_shift(H_range, V_range, count_manager, threshold, no_runs, rate, no_bins, timeout=10):
    amplitudes = np.zeros((len(H_range), len(V_range)))
    retries = 2

    for i, H in enumerate(H_range):
        for j, V in enumerate(V_range):
            success = False
            for attempt in range(retries):
                dc_min_shift(H, V)
                amplitude, frequency, phase, N = count_manager.RF_correlation(no_runs, rate, no_bins)
                if N > threshold:
                    amplitudes[i, j] = amplitude
                    success = True
                    break
                else:
                    print(f"Attempt {attempt + 1} failed for H={H}, V={V}. Retrying...")
            if not success:
                print(f"Failed to get valid data for H={H}, V={V} after {retries} attempts.")
                break

    # Create a 3D plot of the amplitude for H and V
    H_grid, V_grid = np.meshgrid(H_range, V_range)
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(H_grid, V_grid, amplitudes.T, cmap='viridis')
    ax.set_xlabel('H')
    ax.set_ylabel('V')
    ax.set_zlabel('Amplitude')
    ax.set_title('Amplitude for H and V')
    plt.show()

def set_trap_depth(attenuation_voltage):
    # Check if the absolute value of attenuation_voltage is greater than 2
    if np.abs(attenuation_voltage) > 3:
        raise ValueError("Attenuation voltage is out of range. Must be between -2 and 2.")
    else:
        # If within range, call the write_analog_voltage function
        write_analog_voltage(rf_atten_chan, attenuation_voltage)

def load(Count_Manager, Threshold, Timeout):
    port_number = 0 
    Redlabs_DIO_Port = dio_info.port_info[port_number]
    
    if Redlabs_DIO_Port.is_port_configurable:
        ul.d_config_port(Redlabs_Dac, Redlabs_DIO_Port.type, DigitalIODirection.OUT)

    def reset_pins():
        """Ensure the pins are reset to 0 when exiting."""
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Shutter_Pin, 0)
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Oven_Pin, 0)

    # Register the reset function to be called upon normal exit or an exception
    atexit.register(reset_pins)

    # Set the pins to high
    ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Shutter_Pin, 1)
    ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Oven_Pin, 1)

    # Ensure counting is true
    if not Count_Manager.counting:
        Count_Manager.counting = True

    # Start the timer
    start_time = time.time()
    
    try:
        while True:
            # Check for timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > Timeout:
                print("Timeout reached")
                return True  # Completed due to timeout

            # Check if there are enough counts
            count_len = len(Count_Manager.counts)
            if count_len > 0:
                # Determine the number of counts to average
                num_counts = min(count_len, 5)
                recent_counts = Count_Manager.counts[-num_counts:]

                # Flatten the list if it's a list of lists with single elements
                flattened_counts = [item[0] for item in recent_counts]

                # Calculate the average
                average_count = sum(flattened_counts) / len(flattened_counts)
                
                # Check if the average exceeds the threshold
                if average_count > Threshold:
                    print("Threshold exceeded")
                    return False  # Exceeded the threshold

            # Sleep for a duration based on the Count_Manager's rate
            time.sleep(1 / Count_Manager.rate)
    
    finally:
        # Ensure pins are reset
        reset_pins()

class TrapControlFrame(tk.Frame):
    def __init__(self, master=None, Count_Reader=None, default_h=0, default_v=0, default_trap_depth=0):
        super().__init__(master)
        self.master = master
        self.grid(padx=10, pady=10)
        self.create_widgets(default_h, default_v, default_trap_depth)
        self.scan_thread = None
        self.micromotion_thread = None
        self.scan_hv_thread = None
        self.scanning = False
        self.scan_window = None
        self.scan_hv_window = None
        self.micromotion_window = None
        self.Count_Reader = Count_Reader
        self.ax = None  # Initialize ax to None

    def create_widgets(self, default_h, default_v, default_trap_depth):
        static_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        static_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        self.label_H = tk.Label(static_frame, text="H Value:")
        self.label_H.grid(row=0, column=0, padx=5, pady=5)
        self.spinbox_H = CustomSpinbox(static_frame, from_=-5.0, to=5.0, increment=0.0001, initial_value=default_h)
        self.spinbox_H.grid(row=0, column=1, padx=5, pady=5)
        self.spinbox_H.set_callback(self.update_H)

        self.label_V = tk.Label(static_frame, text="V Value:")
        self.label_V.grid(row=1, column=0, padx=5, pady=5)
        self.spinbox_V = CustomSpinbox(static_frame, from_=-5.0, to=5.0, increment=0.0001, initial_value=default_v)
        self.spinbox_V.grid(row=1, column=1, padx=5, pady=5)
        self.spinbox_V.set_callback(self.update_V)

        self.label_trap_depth = tk.Label(static_frame, text="Trap Depth Voltage:")
        self.label_trap_depth.grid(row=2, column=0, padx=5, pady=5)
        self.spinbox_trap_depth = CustomSpinbox(static_frame, from_=0, to=2.0, increment=0.001, initial_value=default_trap_depth)
        self.spinbox_trap_depth.grid(row=2, column=1, padx=5, pady=5)
        self.spinbox_trap_depth.set_callback(self.update_trap_depth)
        self.update_trap_depth(default_trap_depth)  # Call the callback with the initial value

        self.vi_output = tk.Text(static_frame, height=4, width=30, relief=tk.SUNKEN, borderwidth=2)
        self.vi_output.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        self.scan_button = tk.Button(static_frame, text="Scan Trap Depth", command=self.open_scan_window)
        self.scan_button.grid(row=4, column=0, columnspan=2, padx=5, pady=10)

        self.micromotion_button = tk.Button(static_frame, text="Single Micromotion Fit", command=self.open_micromotion_window)
        self.micromotion_button.grid(row=5, column=0, columnspan=2, padx=5, pady=10)

        self.scan_hv_button = tk.Button(static_frame, text="Scan H and V", command=self.open_scan_hv_window)
        self.scan_hv_button.grid(row=6, column=0, columnspan=2, padx=5, pady=10)

        self.configure(bg="#f0f0f0")
        static_frame.configure(bg="#f0f0f0")
    
        self.update_H(default_h)  # Call the callback with the initial value
        self.update_V(default_v)  # Call the callback with the initial value

    def open_micromotion_window(self):
        if self.micromotion_window is not None and self.micromotion_window.micromotion_window is not None and tk.Toplevel.winfo_exists(self.micromotion_window.micromotion_window):
            self.micromotion_window.micromotion_window.lift()
            return

        if self.scan_window is not None and tk.Toplevel.winfo_exists(self.scan_window):
            print("Cannot open Single Micromotion Fit window while Trap Depth scan window is open.")
            return

        if self.scan_hv_window is not None and tk.Toplevel.winfo_exists(self.scan_hv_window):
            print("Cannot open Single Micromotion Fit window while H and V scan window is open.")
            return

        self.micromotion_window = MicromotionWindow(self, self.Count_Reader)
        if self.micromotion_window is not None and tk.Toplevel.winfo_exists(self.micromotion_window.micromotion_window):
            self.micromotion_window.micromotion_window.lift()
            return

        if self.scan_window is not None and tk.Toplevel.winfo_exists(self.scan_window):
            print("Cannot open Single Micromotion Fit window while Trap Depth scan window is open.")
            return

        if self.scan_hv_window is not None and tk.Toplevel.winfo_exists(self.scan_hv_window):
            print("Cannot open Single Micromotion Fit window while H and V scan window is open.")
            return

        self.micromotion_window = MicromotionWindow(self, self.Count_Reader)

    def update_progress_bar(self, value):
        self.progress_bar["value"] = value
        self.micromotion_window.update_idletasks()

    def update_trap_depth(self, value):
        # Update the trap depth voltage directly
        set_trap_depth(value)

    def display_vi_values(self, v1, v2, v3, v4):
        # Display the V_i values in the Text widget
        self.vi_output.delete(1.0, tk.END)  # Clear previous values
        self.vi_output.insert(tk.END, f"V_1: {v1:.3f}\n")
        self.vi_output.insert(tk.END, f"V_2: {v2:.3f}\n")
        self.vi_output.insert(tk.END, f"V_3: {v3:.3f}\n")
        self.vi_output.insert(tk.END, f"V_4: {v4:.3f}\n")

    def open_scan_window(self):
        if self.scan_window is not None and tk.Toplevel.winfo_exists(self.scan_window):
            self.scan_window.lift()
            return

        if self.scan_hv_window is not None and tk.Toplevel.winfo_exists(self.scan_hv_window):
            print("Cannot open Trap Depth scan window while H and V scan window is open.")
            return
        if self.micromotion_window is not None and self.micromotion_window.micromotion_window is not None and tk.Toplevel.winfo_exists(self.micromotion_window.micromotion_window):
            print("Cannot open Trap Depth scan window while micromotion window is open.")
            return

        # Create a new window for the scan panel
        self.scan_window = tk.Toplevel(self)
        self.scan_window.title("Scan Panel")
        self.scan_window.protocol("WM_DELETE_WINDOW", self.close_scan_window)

        # Frame for scan parameters
        scan_frame = tk.Frame(self.scan_window, relief=tk.RAISED, borderwidth=2)
        scan_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # Create input fields for voltage range, n_points, and timestep in the scan frame
        self.label_start_voltage = tk.Label(scan_frame, text="Start Voltage:")
        self.label_start_voltage.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_start_voltage = CustomSpinbox(scan_frame, from_=0, to=100)
        self.entry_start_voltage.grid(row=0, column=1, padx=5, pady=5)

        self.label_end_voltage = tk.Label(scan_frame, text="End Voltage:")
        self.label_end_voltage.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_end_voltage = CustomSpinbox(scan_frame, from_=0, to=100)
        self.entry_end_voltage.grid(row=1, column=1, padx=5, pady=5)

        self.label_n_points = tk.Label(scan_frame, text="Number of Points:")
        self.label_n_points.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.entry_n_points = CustomIntSpinbox(scan_frame, from_=1, to=100)
        self.entry_n_points.grid(row=2, column=1, padx=5, pady=5)

        self.label_timestep = tk.Label(scan_frame, text="Timestep (s):")
        self.label_timestep.grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.entry_timestep = CustomSpinbox(scan_frame, from_=0, to=100)
        self.entry_timestep.grid(row=3, column=1, padx=5, pady=5)

        # Create buttons to start and stop the scan
        self.start_button = tk.Button(scan_frame, text="Start Scan", command=self.start_scan_thread)
        self.start_button.grid(row=4, column=0, padx=5, pady=10)

        self.stop_button = tk.Button(scan_frame, text="Stop Scan", command=self.stop_scan)
        self.stop_button.grid(row=4, column=1, padx=5, pady=10)

        # Styling adjustments
        self.scan_window.configure(bg="#f0f0f0")
        scan_frame.configure(bg="#f0f0f0")

    def close_scan_window(self):
        self.stop_scan()
        self.scan_window.destroy()
        self.scan_window = None

    def start_scan_thread(self):
        if self.scan_thread and self.scan_thread.is_alive():
            print("Scan already in progress.")
            return

        self.scanning = True
        self.spinbox_trap_depth.config(state='disabled')  # Disable trap depth input
        self.scan_thread = threading.Thread(target=self.start_scan)
        self.scan_thread.start()

    def start_scan(self):
        # Get the user inputs for the scan parameters
        try:
            start_voltage = float(self.entry_start_voltage.get())
            end_voltage = float(self.entry_end_voltage.get())
            n_points = int(self.entry_n_points.get())
            timestep = float(self.entry_timestep.get())
        except ValueError:
            print("Invalid input, please enter valid numbers.")
            return

        # Calculate the voltage steps
        self.voltages = np.linspace(start_voltage, end_voltage, n_points)
        self.timestep = timestep
        self.current_index = 0
        self.direction = 1  # 1 for forward, -1 for backward

        # Disable trap depth input
        self.spinbox_trap_depth.config(state='disabled')

        # Start the scan loop
        self.scan_loop()

    def scan_loop(self):
        if not self.scanning:
            # Enable trap depth input and exit if scanning is stopped
            self.spinbox_trap_depth.config(state='normal')
            return

        # Get the current voltage
        voltage = self.voltages[self.current_index]
        set_trap_depth(voltage)
        self.spinbox_trap_depth.set(voltage)  # Update trap depth input value

        # Update the index for the next step
        self.current_index += self.direction
        if self.current_index >= len(self.voltages):
            self.current_index = len(self.voltages) - 2
            self.direction = -1
        elif self.current_index < 0:
            self.current_index = 1
            self.direction = 1

        # Schedule the next step
        self.master.after(int(self.timestep * 1000), self.scan_loop)

    def stop_scan(self):
        self.scanning = False
        if self.scan_thread and self.scan_thread.is_alive():
            print("Stopping scan...")
        else:
            print("No scan to stop.")

    def open_scan_hv_window(self):
        if self.scan_hv_window is not None and tk.Toplevel.winfo_exists(self.scan_hv_window):
            self.scan_hv_window.lift()
            return

        if self.scan_window is not None and tk.Toplevel.winfo_exists(self.scan_window):
            print("Cannot open H/V scan window while Trap Depth scan window is open.")
            return

        if self.micromotion_window is not None and self.micromotion_window.micromotion_window is not None and tk.Toplevel.winfo_exists(self.micromotion_window.micromotion_window):
            print("Cannot open scan H/V window while micromotion window is open.")
            return

        self.scan_hv_window = tk.Toplevel(self)
        self.scan_hv_window.title("Scan H and V")
        self.scan_hv_window.protocol("WM_DELETE_WINDOW", self.close_scan_hv_window)

        scan_hv_frame = tk.Frame(self.scan_hv_window, relief=tk.RAISED, borderwidth=2)
        scan_hv_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # H inputs
        self.label_h_start = tk.Label(scan_hv_frame, text="H Start:")
        self.label_h_start.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_h_start = CustomSpinbox(scan_hv_frame, from_=-5.0, to=5.0, increment=0.1)
        self.entry_h_start.grid(row=0, column=1, padx=5, pady=5)

        self.label_h_end = tk.Label(scan_hv_frame, text="H End:")
        self.label_h_end.grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_h_end = CustomSpinbox(scan_hv_frame, from_=-5.0, to=5.0, increment=0.1)
        self.entry_h_end.grid(row=0, column=3, padx=5, pady=5)

        self.label_h_points = tk.Label(scan_hv_frame, text="H Points:")
        self.label_h_points.grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.entry_h_points = CustomIntSpinbox(scan_hv_frame, from_=1, to=100)
        self.entry_h_points.grid(row=0, column=5, padx=5, pady=5)

        # V inputs
        self.label_v_start = tk.Label(scan_hv_frame, text="V Start:")
        self.label_v_start.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_v_start = CustomSpinbox(scan_hv_frame, from_=-5.0, to=5.0, increment=0.1)
        self.entry_v_start.grid(row=1, column=1, padx=5, pady=5)

        self.label_v_end = tk.Label(scan_hv_frame, text="V End:")
        self.label_v_end.grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_v_end = CustomSpinbox(scan_hv_frame, from_=-5.0, to=5.0, increment=0.1)
        self.entry_v_end.grid(row=1, column=3, padx=5, pady=5)

        self.label_v_points = tk.Label(scan_hv_frame, text="V Points:")
        self.label_v_points.grid(row=1, column=4, sticky="e", padx=5, pady=5)
        self.entry_v_points = CustomIntSpinbox(scan_hv_frame, from_=1, to=100)
        self.entry_v_points.grid(row=1, column=5, padx=5, pady=5)

        # Additional inputs
        self.label_threshold = tk.Label(scan_hv_frame, text="Threshold:")
        self.label_threshold.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.entry_threshold = CustomIntSpinbox(scan_hv_frame, from_=0, to=10000)
        self.entry_threshold.grid(row=2, column=1, padx=5, pady=5)

        self.label_no_runs = tk.Label(scan_hv_frame, text="Number of Runs:")
        self.label_no_runs.grid(row=2, column=2, sticky="e", padx=5, pady=5)
        self.entry_no_runs = CustomIntSpinbox(scan_hv_frame, from_=1, to=100)
        self.entry_no_runs.grid(row=2, column=3, padx=5, pady=5)

        self.label_rate = tk.Label(scan_hv_frame, text="Rate:")
        self.label_rate.grid(row=2, column=4, sticky="e", padx=5, pady=5)
        self.entry_rate = CustomSpinbox(scan_hv_frame, from_=0.1, to=100.0, increment=0.1)
        self.entry_rate.grid(row=2, column=5, padx=5, pady=5)

        self.start_scan_hv_button = tk.Button(scan_hv_frame, text="Start", command=self.start_scan_hv_thread)
        self.start_scan_hv_button.grid(row=3, column=0, columnspan=6, padx=5, pady=10)

        self.scan_hv_window.configure(bg="#f0f0f0")
        scan_hv_frame.configure(bg="#f0f0f0")

        # Add output boxes for minimal amplitude and corresponding H and V values
        self.label_min_amplitude = tk.Label(scan_hv_frame, text="Min Amplitude:")
        self.label_min_amplitude.grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.entry_min_amplitude = tk.Entry(scan_hv_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_min_amplitude.grid(row=4, column=1, padx=5, pady=5)

        self.label_min_h = tk.Label(scan_hv_frame, text="Min H:")
        self.label_min_h.grid(row=4, column=2, sticky="e", padx=5, pady=5)
        self.entry_min_h = tk.Entry(scan_hv_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_min_h.grid(row=4, column=3, padx=5, pady=5)

        self.label_min_v = tk.Label(scan_hv_frame, text="Min V:")
        self.label_min_v.grid(row=4, column=4, sticky="e", padx=5, pady=5)
        self.entry_min_v = tk.Entry(scan_hv_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_min_v.grid(row=4, column=5, padx=5, pady=5)

        # Add matplotlib plots
        self.fig_hv = Figure(figsize=(5, 4), dpi=100)
        self.ax_hv = self.fig_hv.add_subplot(111)
        self.canvas_hv = FigureCanvasTkAgg(self.fig_hv, master=self.scan_hv_window)
        self.canvas_hv.draw()
        self.canvas_hv.get_tk_widget().grid(row=5, column=0, columnspan=6, padx=5, pady=5)

        self.fig_fit = Figure(figsize=(5, 4), dpi=100)
        self.ax_fit = self.fig_fit.add_subplot(111)
        self.canvas_fit = FigureCanvasTkAgg(self.fig_fit, master=self.scan_hv_window)
        self.canvas_fit.draw()
        self.canvas_fit.get_tk_widget().grid(row=5, column=6, columnspan=6, padx=5, pady=5)

        # Add output boxes for fit parameters m and c
        self.label_m = tk.Label(scan_hv_frame, text="Slope (m):")
        self.label_m.grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.entry_m = tk.Entry(scan_hv_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_m.grid(row=6, column=1, padx=5, pady=5)

        self.label_c = tk.Label(scan_hv_frame, text="Intercept (c):")
        self.label_c.grid(row=6, column=2, sticky="e", padx=5, pady=5)
        self.entry_c = tk.Entry(scan_hv_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_c.grid(row=6, column=3, padx=5, pady=5)

    def start_scan_hv_thread(self):
        if self.scan_thread and self.scan_thread.is_alive():
            print("Scan already in progress.")
            return

        self.scanning = True
        self.scan_thread = threading.Thread(target=self.start_scan_hv)
        self.scan_thread.start()

    def start_scan_hv(self):
        try:
            h_start = float(self.entry_h_start.get())
            h_end = float(self.entry_h_end.get())
            h_points = int(self.entry_h_points.get())
            v_start = float(self.entry_v_start.get())
            v_end = float(self.entry_v_end.get())
            v_points = int(self.entry_v_points.get())
            threshold = int(self.entry_threshold.get())
            no_runs = int(self.entry_no_runs.get())
            rate = float(self.entry_rate.get())
        except ValueError:
            print("Invalid input, please enter valid numbers.")
            return

        h_values = np.linspace(h_start, h_end, h_points)
        v_values = np.linspace(v_start, v_end, v_points)
        amplitudes = np.full((h_points, v_points), np.nan)  # Initialize with NaN

        for i, h in enumerate(h_values):
            for j, v in enumerate(v_values):
                dc_min_shift(h, v)
                total_counts = 0
                retries = 0
                while total_counts < threshold and retries < 3:
                    try:
                        popt, hist, bin_edges = self.Count_Reader.RF_correlation(no_runs, rate, v_points)
                        total_counts = np.sum(hist)
                        if total_counts >= threshold:
                            amplitudes[i, j] = popt[0]  # Store the amplitude from popt
                            print("H:",h," V:", v, " A:", popt[0], " f:", popt[1])
                            break
                    except RuntimeError as e:
                        print(f"Error fitting sine wave at H={h}, V={v}: {e}")
                    retries += 1
                if total_counts < threshold and retries >= 3:
                    if not messagebox.askyesno("Continue?", f"Total counts below threshold at H={h}, V={v}. Continue?"):
                        print("Scan aborted by user.")
                        return

        # Ensure ax_hv is initialized
        if self.ax_hv is None:
            print("Error: ax_hv is not initialized.")
            return

        # Update 2D histogram plot
        self.ax_hv.clear()
        h_mesh, v_mesh = np.meshgrid(h_values, v_values)
        c = self.ax_hv.pcolormesh(h_mesh, v_mesh, amplitudes.T, shading='auto')
        self.fig_hv.colorbar(c, ax=self.ax_hv)
        self.ax_hv.set_xlabel('H')
        self.ax_hv.set_ylabel('V')
        self.canvas_hv.draw()

        # Find minimal amplitude and corresponding H and V values
        min_amplitudes = np.nanmin(np.abs(amplitudes), axis=1)
        min_v_indices = np.nanargmin(amplitudes, axis=1)
        min_v_values = v_values[min_v_indices]

        # Perform linear fit
        fit_params = np.polyfit(h_values, min_v_values, 1)
        m, c = fit_params

        # Ensure ax_fit is initialized
        if self.ax_fit is None:
            print("Error: ax_fit is not initialized.")
            return

        # Update linear fit plot
        self.ax_fit.clear()
        self.ax_fit.plot(h_values, min_v_values, 'o', label='Min V values')
        self.ax_fit.plot(h_values, m * h_values + c, '-', label=f'Fit: V = {m:.3f}H + {c:.3f}')
        self.ax_fit.set_xlabel('H')
        self.ax_fit.set_ylabel('V')
        self.ax_fit.legend()
        self.canvas_fit.draw()

        # Update output boxes
        self.entry_min_amplitude.config(state='normal')
        self.entry_min_amplitude.delete(0, tk.END)
        self.entry_min_amplitude.insert(0, f"{np.nanmin(min_amplitudes):.3f}")
        self.entry_min_amplitude.config(state='readonly')

        self.entry_min_h.config(state='normal')
        self.entry_min_h.delete(0, tk.END)
        self.entry_min_h.insert(0, f"{h_values[np.nanargmin(min_amplitudes)]:.3f}")
        self.entry_min_h.config(state='readonly')

        self.entry_min_v.config(state='normal')
        self.entry_min_v.delete(0, tk.END)
        self.entry_min_v.insert(0, f"{min_v_values[np.nanargmin(min_amplitudes)]:.3f}")
        self.entry_min_v.config(state='readonly')

        self.entry_m.config(state='normal')
        self.entry_m.delete(0, tk.END)
        self.entry_m.insert(0, f"{m:.3f}")
        self.entry_m.config(state='readonly')

        self.entry_c.config(state='normal')
        self.entry_c.delete(0, tk.END)
        self.entry_c.insert(0, f"{c:.3f}")
        self.entry_c.config(state='readonly')

    def stop_scan_hv(self):
        self.scanning = False
        if self.scan_thread and self.scan_thread.is_alive():
            print("Stopping scan...")
        else:
            print("No scan to stop.")

    def close_scan_hv_window(self):
        self.stop_scan_hv()
        self.scan_hv_window.destroy()
        self.scan_hv_window = None
    
    def update_H(self, value):
        # Call dc_min_shift function with updated H and current V value
        current_V = float(self.spinbox_V.get())
        v1, v2, v3, v4 = dc_min_shift(value, current_V)
        self.display_vi_values(v1, v2, v3, v4)

    def update_V(self, value):
        # Call dc_min_shift function with updated V and current H value
        current_H = float(self.spinbox_H.get())
        v1, v2, v3, v4 = dc_min_shift(current_H, value)
        self.display_vi_values(v1, v2, v3, v4)

class LoadControlPanel(tk.Frame):
    def __init__(self, parent, Count_Reader, Threshold, Timeout, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.Count_Reader = Count_Reader
        
        # Initialize IntVars with initial values from arguments
        self.Threshold = tk.IntVar(value=Threshold)
        self.Timeout = tk.IntVar(value=Timeout)
        self.remaining_time = tk.IntVar(value=0)  # Assuming remaining time starts at 0
        
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
        self.threshold_entry = CustomIntSpinbox(self.control_frame, from_=0, to=None, initial_value=self.Threshold, textvariable=self.Threshold)
        self.threshold_entry.grid(row=0, column=1, padx=10, pady=10)

        # Timeout input
        ttk.Label(self.control_frame, text="Timeout (s):").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.timeout_entry = CustomIntSpinbox(self.control_frame, from_=0, to=1000, initial_value=self.Timeout, textvariable=self.Timeout)
        self.timeout_entry.grid(row=1, column=1, padx=10, pady=10)

        # Countdown display
        ttk.Label(self.control_frame, text="Remaining Time:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.time_label = ttk.Label(self.control_frame, textvariable=self.remaining_time, relief=tk.SUNKEN, borderwidth=2, width=20)  # Adjust the width as needed
        self.time_label.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # Start button
        self.start_button = ttk.Button(self.control_frame, text="Start", command=self.start_load)
        self.start_button.grid(row=3, columnspan=2, padx=10, pady=10)

    def start_load(self):
        # Check the server status
        server_status = Server.status_check(self.Count_Reader, 1)
        if server_status == 0:
            print("Server was not running. Starting server for Ion loading.")
            self.server_started = True  # Mark that the server has been started
        else:
            self.server_started = False  # Server was already running
        print("sending command")
        # Send a command to check if counting is active
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.Count_Reader.host, self.Count_Reader.port))
            client_socket.sendall(pickle.dumps("GET_COUNTING"))
            print("command sent")
            # Receive response and check if counting is active
            self.was_counting = pickle.loads(client_socket.recv(4096))
            
            # Check if counting is not active
            if not self.was_counting:
                print("PMT_Reader is not counting. Starting counting...")
                client_socket.sendall(pickle.dumps("START_COUNTING"))
                response = pickle.loads(client_socket.recv(4096))  # You can check the response if needed
        client_socket.close()
        # Disable the start button to prevent multiple starts
        self.start_button.config(text="Stop", command=self.stop_load)

        # Start the countdown timer in a separate thread
        self.loading = True
        self.remaining_time.set(self.Timeout.get())
        print("starting load")
        threading.Thread(target=self.countdown, daemon=True).start()

        # Start the load function in a separate thread
        threading.Thread(target=self.load_function, daemon=True).start()

    def stop_load(self):
        # Reset pins and update the UI button
        self.reset_pins()
        self.start_button.config(text="Start", command=self.start_load)
        self.loading = False

        # Check if it was counting and stop counting if true
        if not self.was_counting:
            print("Stopping counting...")
            stop_counting_command = "STOP_COUNTING"
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.Count_Reader.host, self.Count_Reader.port))
                client_socket.sendall(pickle.dumps(stop_counting_command))
                response = pickle.loads(client_socket.recv(4096))  # Check response if necessary
                if response:
                    print("Counting has been stopped successfully.")

        # Check if the server was started in start_load
        if self.server_started:
            print("Shutting down the server...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.Count_Reader.host, self.Count_Reader.port))
                client_socket.sendall(pickle.dumps("SHUTDOWN"))
                # Optional: receive a response here if needed
                response = pickle.loads(client_socket.recv(4096))  # Optional: check if needed

    def countdown(self):
        timeout = self.Timeout.get()
        while timeout > 0 and self.loading:
            time.sleep(1)
            timeout -= 1
            self.remaining_time.set(timeout)
        
        # Stop the load function if the countdown completes
        self.loading = False
        # Re-enable the start button when the countdown is done
        self.start_button.config(text="Start", command=self.start_load)

    def load_function(self):
        port_number = 0 
        Redlabs_DIO_Port = dio_info.port_info[port_number]
        
        if Redlabs_DIO_Port.is_port_configurable:
            ul.d_config_port(Redlabs_Dac, Redlabs_DIO_Port.type, DigitalIODirection.OUT)

        def reset_pins():
            """Ensure the pins are reset to 0 when exiting."""
            ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Shutter_Pin, 0)
            ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Oven_Pin, 0)

        # Register the reset function to be called upon normal exit or an exception
        atexit.register(reset_pins)
        # Set the pins to high
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Shutter_Pin, 1)
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Oven_Pin, 1)

        # Start the timer
        start_time = time.time()
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.Count_Reader.host, self.Count_Reader.port))
        client_socket.sendall(pickle.dumps("GET_RATE"))
        response_data = client_socket.recv(4096)
        rate = pickle.loads(response_data) if response_data else 0.5
        try:
            while self.loading:
                # Check for timeout
                elapsed_time = time.time() - start_time
                if elapsed_time > self.Timeout.get():
                    print("Timeout reached")
                    break  # Completed due to timeout

                # Request counts from the server
                client_socket.sendall(pickle.dumps("GET_COUNTS"))
                response_data = client_socket.recv(4096)
                counts = pickle.loads(response_data) if response_data else None
                # Handle the counts received
                if counts and isinstance(counts, tuple) and len(counts) == 2:
                    times, count_values = counts
                    
                    # Get the last 5 values (or fewer if there are not enough)
                    recent_counts = count_values[-5:]  # Get the last 5 count values
                    
                    # Flatten the list of lists and convert to integers
                    flattened_counts = [item for sublist in recent_counts for item in sublist]  # Flattening
                                        
                    # Calculate the average from the flattened counts
                    average_count = sum(flattened_counts) / len(flattened_counts) if flattened_counts else 0
                    
                    # Check if the average exceeds the threshold
                    if average_count > self.Threshold.get():
                        print("Threshold exceeded")
                        break  # Exceeded the threshold

                # Sleep for a duration based on the Count_Reader's rate
                time.sleep(1 / rate if self.Count_Reader else 1)

        except Exception as e:
            print(f"Error occurred while getting counts: {e}")

        finally:
            # Ensure pins are reset
            reset_pins()
            self.stop_load()
            self.start_button.config(text="Start", command=self.start_load)
            client_socket.close()  # Close the socket connection

    def reset_pins(self):
        """Ensure the pins are reset to 0."""
        port_number = 0 
        Redlabs_DIO_Port = dio_info.port_info[port_number]
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Shutter_Pin, 0)
        ul.d_bit_out(Redlabs_Dac, Redlabs_DIO_Port.type, Oven_Pin, 0)