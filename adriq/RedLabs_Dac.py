# Standard library imports
import time
import atexit
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime
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
from .Servers import Server, Client

from adriq.pulse_sequencer import *


class Redlabs_DAC:
    host = "localhost"
    port = 8002
    def __init__(self, device_id=0, v1_chan=1, v2_chan=2, v3_chan=3, v4_chan=4, rf_atten_chan=7, piezo_chan=8, PI_lock_chan=11,
                 shutter_pin=0, oven_pin=1):
        """
        Initializes the RedlabsDAC class with the given device ID and optional pin assignments.

        Args:
        - device_id (int): The ID of the Redlabs DAC device (default is 0).
        - v1_chan, v2_chan, v3_chan, v4_chan (int): Pin numbers for the analog output channels (default 1-4).
        - rf_atten_chan (int): Pin number for the RF attenuation (default 7).
        - shutter_pin, oven_pin (int): Pin numbers for digital channels (default 0 and 1).
        """
        self.device_id = device_id
        self.daq_dev_info = DaqDeviceInfo(device_id)
        self.ao_info = self.daq_dev_info.get_ao_info()
        self.dio_info = self.daq_dev_info.get_dio_info()
        self.ao_range = self.ao_info.supported_ranges[0]  # Assuming first supported range
        # Analog channels (can be changed by arguments)
        self.v1_chan = v1_chan
        self.v2_chan = v2_chan
        self.v3_chan = v3_chan
        self.v4_chan = v4_chan

        self.rf_atten_chan = rf_atten_chan
        self.piezo_chan = piezo_chan
        self.PI_lock_chan = PI_lock_chan #feedback to 423 Piezo

        # Digital channels (can be changed by arguments)
        self.shutter_pin = shutter_pin
        self.oven_pin = oven_pin
        Redlabs_DIO_Port = self.dio_info.port_info[self.device_id]



        self.v1 = 0
        self.v2 = 0
        self.v3 = 0
        self.v4 = 0

        self.rf_atten = 0

        self.piezo_v = 0

        self.PI_lock_v = 0
        
        if Redlabs_DIO_Port.is_port_configurable:
            ul.d_config_port(self.device_id, Redlabs_DIO_Port.type, DigitalIODirection.OUT)

        self.reset_pins()

    def __del__(self):
        """Destructor method to reset pins when the instance is destroyed."""
        self.reset_pins()

    def write_analog_voltage(self, channel, voltage, Verbose=True):
        """Writes the specified voltage to the specified analog channel."""
        if Verbose:
            print(f"Writing {voltage} V to channel {channel}")
            
        raw_value = ul.from_eng_units(self.device_id, self.ao_range, voltage)
        try:
            ul.a_out(self.device_id, channel, self.ao_range, raw_value)
        except ULError as e:
            self.show_ul_error(e)

    def dc_min_shift(self, H, V, Q=0, S=0):
        """
        Calculate V_i based on provided values and write to corresponding channels.
        In this function, we use the values described in Nicholas Seymour Smith's thesis.
        Parameters:
        - H: Value for H = (V_1 + V_4) - (V_2 + V_3)
        - V: Value for V = (V_1 + V_2) - (V_3 + V_4)
        - Q: Value for Q = (V_1 + V_3) - (V_2 + V_4) (default 0)
        - S: Value for S = (V_1 + V_2) - (V_3 + V_4) (default 0)

        Returns:
        - Tuple containing V_1, V_2, V_3, and V_4.
        """
        # Calculate the voltages for the channels
        V_1 = (H + V + Q + S) / 4
        V_2 = (V + S - H - Q) / 4
        V_3 = (Q + S - H - V) / 4
        V_4 = (H + S - V - Q) / 4
        
        # Write to analog channels
        self.write_analog_voltage(self.v1_chan, V_1)
        self.write_analog_voltage(self.v2_chan, V_2)
        self.write_analog_voltage(self.v3_chan, V_3)
        self.write_analog_voltage(self.v4_chan, V_4)

        self.v1 = V_1
        self.v2 = V_2
        self.v3 = V_3
        self.v4 = V_4


        return V_1, V_2, V_3, V_4

    def set_digital_pin(self, pin, value):
        """
        Sets the specified digital pin high or low.

        Args:
        - pin (int): The digital pin to set.
        - value (int): 1 to set high, 0 to set low.
        """
        try:
            ul.d_bit_out(self.device_id, self.dio_info.port_info[0].type, pin, value)
            print(f"Set pin {pin} to {'HIGH' if value else 'LOW'}")
        except ULError as e:
            self.show_ul_error(e)


    def set_trap_depth(self, attenuation_voltage):
        """Sets the trap depth (attenuation voltage) on the rf_atten_chan."""
        if np.abs(attenuation_voltage) > 3:
            raise ValueError("Attenuation voltage is out of range. Must be between -3 and 3.")
        else:
            self.write_analog_voltage(self.rf_atten_chan, attenuation_voltage)
            self.rf_atten = attenuation_voltage

    def set_piezo_voltage(self, voltage, step_size=0.005, rate=2.0):
        """
        Sets the piezo voltage on the piezo_chan with a smooth ramp.

        Args:
        - voltage (float): Target voltage to set.
        - step_size (float): Minimum step size for the ramp. Default is 0.001.
        - rate (float): Rate of change in volts per second. Default is 1.0 V/s.
        """
        if np.abs(voltage) > 10:
            raise ValueError("Piezo voltage is out of range. Must be between -10 and 10.")

        current_voltage = self.piezo_v
        voltage_diff = voltage - current_voltage

        # Determine the direction of the ramp
        step_direction = 1 if voltage_diff > 0 else -1

        # Calculate the number of steps required
        total_steps = max(int(np.abs(voltage_diff) / step_size), 1)

        # Calculate the delay between steps to achieve the desired rate
        delay = step_size / rate

        # Ramp the voltage
        for _ in range(total_steps):
            current_voltage += step_direction * step_size
            self.write_analog_voltage(self.piezo_chan, current_voltage, Verbose = False)
            time.sleep(delay)

            # Stop ramping if the target voltage is reached or exceeded
            if (step_direction > 0 and current_voltage >= voltage) or (step_direction < 0 and current_voltage <= voltage):
                break

        # Set the final voltage to ensure accuracy
        self.write_analog_voltage(self.piezo_chan, voltage)
        self.piezo_v = voltage

    def set_PI_lock_voltage(self, voltage):
        """Sets the PI lock voltage on the PI_lock_chan."""
        if np.abs(voltage) > 10:
            raise ValueError("PI lock voltage is out of range. Must be between -10 and 10.")
        else:
            self.write_analog_voltage(self.PI_lock_chan, voltage, Verbose=False)
            self.PI_lock_v = voltage

    def show_ul_error(self, error):
        """Handles error reporting."""
        print(f"UL Error: {error}")

    def start_oven(self):
        """Turns on the oven by setting the oven pin high."""
        self.set_digital_pin(self.oven_pin, 1)
    
    def open_pi_shutter(self):
        """Opens the PI shutter by setting the shutter pin high."""
        self.set_digital_pin(self.shutter_pin, 1)

    def get_device_info(self):
        """Returns information about the device."""
        return {
            "Device ID": self.device_id,
            "Analog Output Range": self.ao_range,
            "Digital IO Info": self.dio_info
        }
    
    def reset_pins(self):
        """
        Resets all relevant pins to LOW (0) for safety.
        Oven pin high is bad news.
        """
        self.set_digital_pin(self.shutter_pin, 0)
        self.set_digital_pin(self.oven_pin, 0)
        print("All pins reset to LOW")
    
    def get_piezo_v(self):
        """Returns the current piezo voltage."""
        return self.piezo_v


class TrapControlFrame(tk.Frame):
    def __init__(self, master, tdc_reader, redlabs_dac, config_file="dc_null_history.csv", default_trap_depth=0):
        super().__init__(master)
        self.master = master
        self.tdc_client = Client(tdc_reader)
        self.redlabs_dac_client = Client(redlabs_dac)
        self.config_file = config_file
        self.default_h, self.default_v = self.load_default_hv()
        self.grid(padx=10, pady=10)
        self.create_widgets(self.default_h, self.default_v, default_trap_depth)
        self.scan_thread = None
        self.micromotion_thread = None
        self.scan_hv_thread = None
        self.scanning = False
        self.scan_window = None
        self.scan_hv_window = None
        self.micromotion_window = None
        self.ax = None  # Initialize ax to None

    def load_default_hv(self):
        try:
            data = np.genfromtxt(self.config_file, delimiter=',', dtype=None, names=True, encoding=None)
            if data.size == 0:
                raise ValueError("Config file is empty.")
            if data.ndim == 0:  # Handle case where there's only one row of data
                data = np.array([data])
            latest_entry = data[-1]
            return latest_entry['H'], latest_entry['V']
        except Exception as e:
            print(f"Error loading config file: {e}")
            return 0, 0  # Default values if loading fails

    def save_hv(self):
        try:
            data = np.genfromtxt(self.config_file, delimiter=',', dtype=None, names=True, encoding=None)
            if data.size == 0:
                raise ValueError("Config file is empty.")
            if data.ndim == 0:  # Handle case where there's only one row of data
                data = np.array([data])
        except (IOError, ValueError):
            data = np.array([], dtype=[('H', 'f8'), ('V', 'f8'), ('Date', 'U19')])

        new_entry = np.array([(self.spinbox_H.get(), self.spinbox_V.get(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))],
                            dtype=[('H', 'f8'), ('V', 'f8'), ('Date', 'U19')])
        if data.size == 0:
            data = new_entry
        else:
            data = np.concatenate((data, new_entry))
        np.savetxt(self.config_file, data, delimiter=',', fmt=['%.4f', '%.4f', '%s'], header='H,V,Date', comments='')
        print("H and V values saved.")

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

        self.vi_output = tk.Text(static_frame, height=3, width=30, relief=tk.SUNKEN, borderwidth=2)  # Adjust the width
        self.vi_output.grid(row=3, column=0, columnspan=2, padx=5, pady=5)  # Adjust columnspan

        self.save_button = tk.Button(static_frame, text="Save DC Min", command=self.save_hv)
        self.save_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5)  # Move the button to the same row as vi_output

        self.scan_button = tk.Button(static_frame, text="Scan Trap Depth", command=self.open_scan_window)
        self.scan_button.grid(row=5, column=0, columnspan=2, padx=5, pady=10)

        self.micromotion_button = tk.Button(static_frame, text="Single Micromotion Fit", command=self.open_micromotion_window)
        self.micromotion_button.grid(row=6, column=0, columnspan=2, padx=5, pady=10)

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

        self.micromotion_window = MicromotionWindow(self, self.tdc_client)
        if self.micromotion_window is not None and tk.Toplevel.winfo_exists(self.micromotion_window.micromotion_window):
            self.micromotion_window.micromotion_window.lift()
            return

        if self.scan_window is not None and tk.Toplevel.winfo_exists(self.scan_window):
            print("Cannot open Single Micromotion Fit window while Trap Depth scan window is open.")
            return

        if self.scan_hv_window is not None and tk.Toplevel.winfo_exists(self.scan_hv_window):
            print("Cannot open Single Micromotion Fit window while H and V scan window is open.")
            return

        self.micromotion_window = MicromotionWindow(self, self.tdc_client)

    def update_trap_depth(self, value):
        # Update the trap depth voltage directly
        self.redlabs_dac_client.set_trap_depth(value)

    def display_vi_values(self, v1, v2, v3, v4):
        # Display the V_i values in the Text widget
        self.vi_output.delete(1.0, tk.END)  # Clear previous values
        self.vi_output.insert(tk.END, f"V_1: {v1:.3f}  V_2: {v2:.3f}\n")
        self.vi_output.insert(tk.END, f"\n")
        self.vi_output.insert(tk.END, f"V_3: {v3:.3f}  V_4: {v4:.3f}")

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
        self.redlabs_dac_client.set_trap_depth(voltage)
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
    
    def update_H(self, value):
        # Call dc_min_shift function with updated H and current V value
        current_V = float(self.spinbox_V.get())
        v1, v2, v3, v4 = self.redlabs_dac_client.dc_min_shift(value, current_V)
        self.display_vi_values(v1, v2, v3, v4)

    def update_V(self, value):
        # Call dc_min_shift function with updated V and current H value
        current_H = float(self.spinbox_H.get())
        v1, v2, v3, v4 = self.redlabs_dac_client.dc_min_shift(current_H, value)
        self.display_vi_values(v1, v2, v3, v4)

class LoadControlPanel(tk.Frame):
    def __init__(self, parent, PMT_Reader, Redlabs_DAC, Threshold, Timeout, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Initialize clients for PMT_Reader and RedlabsDAC
        self.pmt_reader_client = Client(PMT_Reader)
        self.redlabs_dac_client = Client(Redlabs_DAC)

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
        # Start the RedlabsDAC ports configuration
        try:
            self.redlabs_dac_client.start_oven()
            self.redlabs_dac_client.open_pi_shutter()
        except Exception as e:
            print(f"Failed to initialize digital pins: {e}")
            return

        # Start the PMT_Reader server if not already running
        try:
            counting_status = self.pmt_reader_client.get_counting()
            if not counting_status:
                print("PMT_Reader is not counting. Starting counting...")
                self.pmt_reader_client.start_counting()
        except Exception as e:
            print(f"Failed to communicate with PMT_Reader: {e}")
            return

        # Start the countdown and load function in separate threads
        self.loading = True
        self.remaining_time.set(self.Timeout.get())
        threading.Thread(target=self.countdown, daemon=True).start()
        threading.Thread(target=self.load_function, daemon=True).start()

        # Update UI
        self.start_button.config(text="Stop", command=self.stop_load)

    def stop_load(self):
        # Reset the DAC pins
        try:
            self.redlabs_dac_client.reset_pins()
        except Exception as e:
            print(f"Failed to reset DAC pins: {e}")

        # Stop the PMT counting if it was started by this session
        try:
            a = 0
            #self.pmt_reader_client.stop_counting()
        except Exception as e:
            print(f"Failed to stop PMT_Reader counting: {e}")

        self.loading = False
        self.start_button.config(text="Start", command=self.start_load)

    def countdown(self):
        timeout = self.Timeout.get()
        while timeout > 0 and self.loading:
            time.sleep(1)
            timeout -= 1
            self.remaining_time.set(timeout)

        # Stop the load function if the countdown completes
        self.stop_load()

    def load_function(self):
        rate = self.pmt_reader_client.get_rate()
        try:
            while self.loading:
                # Get counts from the PMT_Reader
                counts = self.pmt_reader_client.get_counts()
                if counts:
                    # Check the average of recent counts
                    counts = counts[1]['PMT']
                    recent_counts = counts[-3:]  # Assuming counts is a list of values
                    avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
                    if avg_counts > self.Threshold.get():
                        print("Threshold exceeded")
                        break

                # Sleep based on PMT_Reader's rate
                time.sleep(1 / rate)

        except Exception as e:
            print(f"Error during load function: {e}")

        finally:
            self.stop_load()

class PiezoControlPanel(tk.Frame):
    def __init__(self, master, Redlabs_DAC):
        super().__init__(master, relief=tk.RAISED, borderwidth=2)
        
        
        # Create a DAC client and store it as an instance variable
        self.DAC = Client(Redlabs_DAC)

        # Create a label
        label = tk.Label(self, text="Piezo Voltage:")
        label.pack(side=tk.LEFT, padx=5)

        # Create a CustomSpinbox
        self.spinbox = CustomSpinbox(self, from_=-10.0, to=10.0, initial_value=0.0, increment=0.1, width=10)
        self.spinbox.set_callback(self.set_piezo_voltage)  # Set the callback for the spinbox
        self.spinbox.pack(side=tk.LEFT, padx=5)

        # Start periodic voltage reading
        self.update_spinbox_with_current_voltage()

    def set_piezo_voltage(self, voltage):
        """Set the piezo voltage using the DAC client."""
        try:
            self.DAC.set_piezo_voltage(voltage, step_size=0.005, rate=5)
            print(f"Piezo voltage set to: {voltage} V")
        except Exception as e:
            print(f"Error setting piezo voltage: {e}")

    def update_spinbox_with_current_voltage(self):
        """Periodically update the spinbox with the current piezo voltage."""
        try:
            # Only update if the spinbox does NOT have focus
            if self.spinbox.focus_get() != self.spinbox:
                current_voltage = self.DAC.get_piezo_v()
                self.spinbox.var.set(f"{current_voltage:.3f}")  # Update the spinbox's StringVar directly
        except Exception as e:
            print(f"Error reading piezo voltage: {e}")

        # Schedule the next update after 1 second (1000 ms)
        self.after(1000, self.update_spinbox_with_current_voltage)


