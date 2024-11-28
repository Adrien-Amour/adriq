# Standard library imports
import time
import threading
import random
import warnings
import pickle
import socket
from datetime import datetime
from collections import Counter

# Third-party imports
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import nidaqmx
from nidaqmx.constants import Edge
import tkinter as tk
from tkinter import ttk, BooleanVar
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,  QFrame
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QCheckBox, QHBoxLayout
from PyQt5.QtWidgets import QSpinBox
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from .Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
from .tdc_functions import filter_trailing_zeros, compute_time_diffs, count_channel_events

# Local application/library-specific imports
from . import QuTau
from .Servers import Server, Client

def sine_wave(x, amplitude, frequency, phase, offset):
    return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset


class PMT_Reader:
    host = 'localhost'
    port = 8000
    
    def __init__(self, rate=10, N=100):
        self.rate = rate
        self.N = N
        self.counting = False
        self.counts = []
        self.times = []
        self.lock = threading.Lock()
        self.task = nidaqmx.Task()

        self.channel = self.task.ci_channels.add_ci_count_edges_chan(
            "Dev1/ctr0",
            edge=Edge.RISING,
            initial_count=0,
            count_direction=nidaqmx.constants.CountDirection.COUNT_UP
        )
        self.channel.ci_count_edges_term = "/Dev1/PFI8"
        self.initialized = True

    def update_rate(self, new_rate):
        self.rate = new_rate
        return True

    def update_N(self, new_N):
        self.N = new_N
        return True

    def get_rate(self):
        return self.rate

    def get_N(self):
        return self.N

    def count_rate(self):
        start_time = time.time()  # Record the start time
        self.task.start()
        time.sleep(1 / self.rate)
        read_data = self.task.read(number_of_samples_per_channel=1)
        count1, end_time = (read_data if isinstance(read_data, int) else read_data[0] if len(read_data) > 0 else 0), time.time()
        elapsed_time = end_time - start_time  # Calculate the elapsed time
        count_rate = int(count1 / elapsed_time)  # Use the elapsed time to calculate the count rate
        self.task.stop()
        end_time = time.time()  # End timing
        current_time = datetime.now()
        return count_rate, current_time

    def start_counting(self):
        self.counts = []
        self.times = []
        self.counting = True
        print("Counting started...")
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def _counting_loop(self):
        while self.counting:
            count_rate, current_time = self.count_rate()
            with self.lock:  # Ensure thread-safe access
                self.counts.append(count_rate)  # Store only the first element
                self.times.append(current_time)

                # Trim lists if necessary
                if len(self.counts) > self.N:
                    self.counts.pop(0)
                if len(self.times) > self.N:
                    self.times.pop(0)

    def stop_counting(self):
        self.counting = False

    def get_counts(self):
        with self.lock:  # Ensure thread-safe access
            return self.times, {"PMT": self.counts}
    
    def recv_command(self, command):
        if command == "GET_COUNTING":
            return self.counting
        if command == "START_COUNTING":
            self.start_counting()
            return True
        elif command == "STOP_COUNTING":
            self.stop_counting()
            return True
        if command == "GET_COUNTS":
            counts = self.get_counts()
            return counts
        elif command == "GET_RATE":
            return self.get_rate()
        elif command == "GET_N":
            return self.get_N()
        elif command.startswith("SET_RATE"):
            _, new_rate = command.split()
            return self.update_rate(int(new_rate))
        elif command.startswith("SET_N"):
            _, new_N = command.split()
            return self.update_N(int(new_N))
        else:
            return "Unknown command"

    def close(self):
        self.stop_counting()  # Ensure counting is stopped
        self.task.stop()  # Stop the task if it's running
        self.task.close()  # Explicitly release the resources
        print("NIDAQmx Task closed.")

class QuTau_Channel:
    def __init__(self, name, number, mode="idle"):
        self.name = name
        self.number = number
        self.mode = mode
        self.active = mode != "idle"
        self.recent_time_diffs = []
        self.time_diffs = []
        self.counts = []  # Initialize counts attribute

    def save_recent_time_diffs(self):
        """Save recent time differences by extending the time_diffs attribute."""
        self.time_diffs.extend(self.recent_time_diffs)
        for i, diff in enumerate(self.time_diffs):
            if diff > 1e-4:
                print(f"Channel {self.name} - Time diff: {diff} at index {i}/{len(self.time_diffs)}")

    def discard_recent_time_diffs(self):
        """Discard recent time differences."""
        self.recent_time_diffs = []

    def clear_time_diffs(self):
        """Clear the time_diffs attribute."""
        self.time_diffs = []

class QuTau_Reader:

    host = 'localhost'
    port = 8001  # Set a unique port number for QuTau_Reader

    def __init__(self, channels=None):
        if channels is None:
            channels = [
                QuTau_Channel("single_photon_chan1", 0, mode="signal-sp"),
                QuTau_Channel("single_photon_chan2", 1, mode="signal-sp"),
                QuTau_Channel("single_photon_chan3", 2, mode="signal-sp"),
                QuTau_Channel("single_photon_chan4", 3, mode="signal-sp"),
                QuTau_Channel("Inactive-4", 4, mode="idle"),
                QuTau_Channel("trap_drive_chan", 5, mode="trap"),
                QuTau_Channel("pmt_counts_chan", 6, mode="signal-f"),
                QuTau_Channel("ps_sync_chan", 7, mode="trigger")
            ]
        self.qutau = QuTau.QuTau() # Initialize QuTau object
        self.timebase = self.qutau.getTimebase()
        self.channels = channels
        self.ensure_all_channels()
        self.ensure_single_trap_drive_and_ps_sync()
        self.default_modes = {ch.number: ch.mode for ch in self.channels}
        self.rate = 5
        self.N = 100
        self.current_mode = "idle"
        self.times = []  # Initialize times array
        self.update_active_channels()

    def ensure_all_channels(self):
        existing_numbers = {ch.number for ch in self.channels}
        for i in range(8):
            if i not in existing_numbers:
                self.channels.append(QuTau_Channel(f"idle-{i}", i, mode="idle"))

    def ensure_single_trap_drive_and_ps_sync(self):
        trap_drive_channels = [ch for ch in self.channels if ch.mode == "trap"]
        ps_sync_channels = [ch for ch in self.channels if ch.mode == "trigger"]

        if len(trap_drive_channels) > 1:
            raise ValueError("Only one trap drive channel is allowed.")
        if len(ps_sync_channels) > 1:
            raise ValueError("Only one PS sync channel is allowed.")

    def set_active_channels(self, modes):
        self.active_channels = [ch.number for ch in self.channels if ch.mode in modes]
        self.qutau.enableChannels(self.active_channels)
        print(f"Active channels: {self.active_channels}")

    def enter_idle_mode(self):
        self.current_mode = "idle"
        self.set_active_channels([])  # No active channels in idle mode

    def enter_counting_mode(self):
        self.current_mode = "counting"
        self.times = []  # Clear times array
        self.set_active_channels(["signal-f", "signal-sp"])

    def enter_rf_correlation_mode(self):
        self.current_mode = "rf_correlation"
        self.set_active_channels(["signal-f", "trap"])

    def enter_experiment_mode(self, experiment_config=None):
        self.current_mode = "experiment"
        
        # Standard experiment configuration
        standard_experiment_config = {
            0: "signal-sp",  # single_photon_chan1
            1: "signal-sp",  # single_photon_chan2
            2: "signal-sp",  # single_photon_chan3
            3: "signal-sp",  # single_photon_chan4
            4: "idle",       # Inactive-4
            5: "trap",       # trap_drive_chan
            6: "signal-f",   # pmt_counts_chan
            7: "trigger"     # ps_sync_chan
        }
        
        # Use standard settings if no experiment_config is provided
        if experiment_config is None:
            experiment_config = standard_experiment_config
        
        # Set channel modes based on experiment_config
        for ch in self.channels:
            if ch.number in experiment_config:
                ch.mode = experiment_config[ch.number]
                ch.active = ch.mode not in ["idle", "trap"]
        
        
        self.update_active_channels()

    def exit_experiment_mode(self):
        self.current_mode = "idle"
        # Reset channel modes to default
        for ch in self.channels:
            ch.mode = self.default_modes[ch.number]
            ch.active = ch.mode != "idle"
        self.update_active_channels()

    def update_active_channels(self):
        self.active_channels = [ch.number for ch in self.channels if ch.active]
        self.qutau.enableChannels(self.active_channels)
        print(f"Active channels: {self.active_channels}")

    def get_data(self):
        self.timestamps = self.qutau.getLastTimestamps(True)
        self.tchannel = np.array(self.timestamps[1], dtype=np.int64)
        self.tstamp = np.array(self.timestamps[0], dtype=np.float64) * self.timebase
        self.tstamp, self.tchannel = filter_trailing_zeros(self.tstamp, self.tchannel)
        return self.tstamp, self.tchannel

    def compute_time_diff(self):
        trigger_chan = next(ch.number for ch in self.channels if ch.mode == "trigger")
        
        # Start timing
        start_time = time.time()
        
        signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]], dtype=np.int64)
        
        # End timing
        end_time = time.time()
        
        # Calculate elapsed time
        elapsed_time = end_time - start_time
        
        time_diffs = compute_time_diffs(self.tstamp, self.tchannel, trigger_chan, signal_chans, sequence_length=26E-6)
        # Store time differences in the corresponding channel objects
        for ch in self.channels:
            if ch.number in signal_chans:
                ch.recent_time_diffs = time_diffs[signal_chans.tolist().index(ch.number)]
                ch.time_diffs.extend(ch.recent_time_diffs)

    def start_counting(self):
        if self.current_mode in ["experiment", "rf_correlation"]:
            print("Cannot start counting in experiment or RF correlation mode.")
            return

        self.counts = {ch.number: [] for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}
        self.counting = True
        self.enter_counting_mode()
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def stop_counting(self):
        self.counting = False
        for ch in self.channels:
            if ch.mode in ["signal-f", "signal-sp"]:
                ch.counts = []
        self.times = []  # Clear times array
        self.enter_idle_mode()

    def count_rate(self):
        # Get the latest timestamps and filter trailing zeros
        self.get_data()

        # Use count_channel_events to count occurrences of each channel
        counts_list = count_channel_events(self.tchannel)

        # Generate the count rates list and update channel counts
        for ch in self.channels:
            if ch.active:
                count = next((count for channel, count in counts_list if channel == ch.number), 0)
                count_rate = count * self.rate
                ch.counts.append(count_rate)
                if len(ch.counts) > self.N:
                    ch.counts.pop(0)

        current_time = datetime.now()
        self.times.append(current_time)  # Store the current time
        if len(self.times) > self.N:
            self.times.pop(0)
    
    def _counting_loop(self):
        while self.counting:
            start_time = time.time()  # Start time for the loop
            self.count_rate()

            # Calculate the remaining time to sleep to maintain the desired rate
            elapsed_time = time.time() - start_time
            sleep_time = max(0, (1 / self.rate) - elapsed_time)
            time.sleep(sleep_time)

    def get_counts(self):
        return self.times, {ch.name: ch.counts for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}

    def get_last_timestamps(self):
        self.get_data()
        return self.tstamp, self.tchannel

    def get_rate(self):
        return self.rate

    def get_N(self):
        return self.N

    def update_rate(self, new_rate):
        self.rate = new_rate
        return True

    def update_N(self, new_N):
        self.N = new_N
        return True

    def RF_correlation(self, no_runs, rate, no_bins, update_progress_callback=None):
        if self.current_mode == "experiment":
            print("RF correlation cannot be performed in experiment mode.")
            return [], [], []
        was_counting = False
        if self.current_mode == "counting":
            self.stop_counting()
            was_counting = True
        
        previous_channels = self.active_channels
        self.enter_rf_correlation_mode()
        self.update_rate(rate)

        time_diffs = []
        self.get_data()
        
        
        for run in range(no_runs):
            start_time = time.time()

            self.get_data()
            start_time2 = time.time()
            trap_drive_chan = next(ch.number for ch in self.channels if ch.mode == "trap")
            print(trap_drive_chan)
            signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f"]], dtype=np.int64)
            time_diffs_run = compute_time_diffs(self.tstamp, self.tchannel, trap_drive_chan, signal_chans)
            if time_diffs_run and len(time_diffs_run[0]) > 0:  # Check if time_diffs_run is not empty
                time_diffs.extend(time_diffs_run[0])  # Assuming single signal channel
            elapsed_time = time.time() - start_time

            sleep_time = max(0, (1 / self.rate) - elapsed_time)
            time.sleep(sleep_time)

            # Send progress update to the client
            if update_progress_callback:
                percent_complete = (run + 1) / no_runs * 100
                print(f'\rProgress: {percent_complete:.2f}%', end='', flush=True)
        print(time_diffs)
        if len(time_diffs) == 0:
            print("No time differences were computed.")
            self.active_channels = previous_channels
            self.qutau.enableChannels(self.active_channels)
            if was_counting:
                self.start_counting()
            return [], [], []

        time_diffs = np.array(time_diffs, dtype=np.float64)
        time_diffs *= self.timebase

        # Remove outliers using the IQR method
        if len(time_diffs) > 0:
            Q1 = np.percentile(time_diffs, 25)
            Q3 = np.percentile(time_diffs, 75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            filtered_time_diffs = time_diffs[(time_diffs >= lower_bound) & (time_diffs <= upper_bound)]
        else:
            filtered_time_diffs = np.array([])

        if len(filtered_time_diffs) == 0:
            print("No filtered time differences remain after outlier removal.")
            self.active_channels = previous_channels
            self.qutau.enableChannels(self.active_channels)
            if was_counting:
                self.start_counting()
            return [], [], []

        hist, bin_edges = np.histogram(filtered_time_diffs, bins=no_bins, range=(0, max(filtered_time_diffs, default=1)))

        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        def fit_sine_wave(p0):
            try:
                popt, _ = curve_fit(sine_wave, bin_centers, hist, p0=p0)
                residuals = hist - sine_wave(bin_centers, *popt)
                ss_res = np.sum(residuals**2)
                return popt, ss_res
            except Exception as e:
                print(f"Error fitting sine wave: {e}")
                return [0, 0, 0, 0], float('inf')

        p0_1 = [max(hist), 4 / ((bin_edges[-1] - bin_edges[0])), 0, 0]
        p0_2 = [max(hist), 8 / ((bin_edges[-1] - bin_edges[0])), 0, 0]

        popt_1, ss_res_1 = fit_sine_wave(p0_1)
        popt_2, ss_res_2 = fit_sine_wave(p0_2)

        if ss_res_1 < ss_res_2:
            popt = popt_1
        else:
            popt = popt_2

        amplitude, frequency, phase, offset = popt
        phase = phase % np.pi

        self.active_channels = previous_channels
        self.qutau.enableChannels(self.active_channels)

        if was_counting:
            self.start_counting()

        return popt, hist, bin_edges

    def recv_command(self, command):
        if command == "GET_COUNTING":
            return self.current_mode == "counting"
        elif command == "START_COUNTING":
            self.start_counting()
            return True
        elif command == "STOP_COUNTING":
            self.stop_counting()
            return True
        elif command == "GET_COUNTS":
            counts = self.get_counts()
            return counts
        elif command == "GET_LAST_TIMESTAMPS":
            timestamps = self.get_last_timestamps()
            return timestamps
        elif command == "GET_RATE":
            return self.get_rate()
        elif command == "GET_N":
            return self.get_N()
        elif command.startswith("SET_RATE"):
            _, new_rate = command.split()
            return self.update_rate(int(new_rate))
        elif command.startswith("SET_N"):
            _, new_N = command.split()
            return self.update_N(int(new_N))
        elif command.startswith("START_RF_CORRELATION"):
            _, no_runs, rate, no_bins, *show_plot = command.split()
            return self.RF_correlation(int(no_runs), int(rate), int(no_bins), bool(int(show_plot[0])) if show_plot else False)
        else:
            return "Unknown command"
        
    def close(self):
        if self.current_mode != "experiment":
            self.qutau.deInitialize()  # Use the deInitialize method for cleanup
            print("QuTau_Reader has been closed.")
        else:
            print("Cannot close QuTau_Reader while in experiment mode.")

class MicromotionWindow:
    def __init__(self, parent, count_reader):
        self.parent = parent
        self.count_reader = count_reader
        self.micromotion_window = tk.Toplevel(parent)
        self.micromotion_window.title("Single Micromotion Fit")
        self.micromotion_window.protocol("WM_DELETE_WINDOW", self.close_window)
        self.micromotion_thread = None
        self.ax = None  # Initialize ax to None



        # Initialize previous fit parameters
        self.prev_amplitude = None
        self.prev_frequency = None
        self.prev_phase = None
        self.prev_offset = None

        self.create_widgets()

    def create_widgets(self):
        micromotion_frame = tk.Frame(self.micromotion_window, relief=tk.RAISED, borderwidth=2)
        micromotion_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        self.label_no_runs = tk.Label(micromotion_frame, text="Number of Runs:")
        self.label_no_runs.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_no_runs = CustomIntSpinbox(micromotion_frame, from_=1, to=1000, initial_value=50)
        self.entry_no_runs.grid(row=0, column=1, padx=5, pady=5)

        self.label_rate = tk.Label(micromotion_frame, text="Rate:")
        self.label_rate.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_rate = CustomSpinbox(micromotion_frame, from_=0.1, to=20, increment=0.1, initial_value=5)
        self.entry_rate.grid(row=1, column=1, padx=5, pady=5)

        self.label_no_bins = tk.Label(micromotion_frame, text="Number of Bins:")
        self.label_no_bins.grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.entry_no_bins = CustomIntSpinbox(micromotion_frame, from_=1, to=500, initial_value=200)
        self.entry_no_bins.grid(row=2, column=1, padx=5, pady=5)

        self.start_micromotion_button = tk.Button(micromotion_frame, text="Start", command=self.start_rf_correlation_thread)
        self.start_micromotion_button.grid(row=3, column=0, columnspan=2, padx=5, pady=10)

        self.micromotion_window.configure(bg="#f0f0f0")
        micromotion_frame.configure(bg="#f0f0f0")

        # Add output boxes for fit parameters next to input fields
        self.label_amplitude = tk.Label(micromotion_frame, text="Amplitude:")
        self.label_amplitude.grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_amplitude = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_amplitude.grid(row=0, column=3, padx=5, pady=5)

        self.label_frequency = tk.Label(micromotion_frame, text="Frequency:")
        self.label_frequency.grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_frequency = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_frequency.grid(row=1, column=3, padx=5, pady=5)

        self.label_phase = tk.Label(micromotion_frame, text="Phase:")
        self.label_phase.grid(row=2, column=2, sticky="e", padx=5, pady=5)
        self.entry_phase = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_phase.grid(row=2, column=3, padx=5, pady=5)

        self.label_offset = tk.Label(micromotion_frame, text="Offset:")
        self.label_offset.grid(row=3, column=2, sticky="e", padx=5, pady=5)
        self.entry_offset = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_offset.grid(row=3, column=3, padx=5, pady=5)

        # Add previous fit parameters
        self.label_prev_amplitude = tk.Label(micromotion_frame, text="Prev Amplitude:")
        self.label_prev_amplitude.grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.entry_prev_amplitude = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_prev_amplitude.grid(row=0, column=5, padx=5, pady=5)

        self.label_prev_frequency = tk.Label(micromotion_frame, text="Prev Frequency:")
        self.label_prev_frequency.grid(row=1, column=4, sticky="e", padx=5, pady=5)
        self.entry_prev_frequency = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_prev_frequency.grid(row=1, column=5, padx=5, pady=5)

        self.label_prev_phase = tk.Label(micromotion_frame, text="Prev Phase:")
        self.label_prev_phase.grid(row=2, column=4, sticky="e", padx=5, pady=5)
        self.entry_prev_phase = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_prev_phase.grid(row=2, column=5, padx=5, pady=5)

        self.label_prev_offset = tk.Label(micromotion_frame, text="Prev Offset:")
        self.label_prev_offset.grid(row=3, column=4, sticky="e", padx=5, pady=5)
        self.entry_prev_offset = tk.Entry(micromotion_frame, state='readonly', relief=tk.SUNKEN, bg='#f0f0f0')
        self.entry_prev_offset.grid(row=3, column=5, padx=5, pady=5)

        # Add matplotlib plot
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.micromotion_window)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=4, column=0, columnspan=6, padx=5, pady=5)

    def close_window(self):
        self.micromotion_window.destroy()
        self.micromotion_window = None

    def start_rf_correlation_thread(self):
        if self.micromotion_thread and self.micromotion_thread.is_alive():
            print("Micromotion correlation already in progress.")
            return

        self.micromotion_thread = threading.Thread(target=self.start_rf_correlation)
        self.micromotion_thread.start()

    def start_rf_correlation(self):
        # Check the status of the server
        server_status = Server.status_check(self.count_reader, 1)

        if server_status == 0:
            print("Server was not running. Starting server for RF correlation.")

        try:
            no_runs = int(self.entry_no_runs.get())
            rate = float(self.entry_rate.get())
            no_bins = int(self.entry_no_bins.get())
        except ValueError:
            print("Invalid input, please enter valid numbers.")
            return

        print("sending command")
        # Send START_RF_CORRELATION command to the QuTau_Reader server
        command = f"START_RF_CORRELATION {int(no_runs)} {int(rate)} {int(no_bins)} 1"
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.count_reader.host, self.count_reader.port))
        client_socket.sendall(pickle.dumps(command))

        response = None  # Initialize response before the loop
        while True:
            response_data = client_socket.recv(4096)
            if response_data:  # Ensure data was received
                try:
                    response = pickle.loads(response_data)
                except (pickle.UnpicklingError, EOFError) as e:
                    print(f"Error: Failed to decode response - {e}")
                    client_socket.close()
                    break
                print(response)
                # Case 1: Error message in the form of a string
                if isinstance(response, str):
                    if response == "Unknown command":
                        print("Error: Unknown command received.")
                        client_socket.close()
                        break
                    else:
                        print(f"Message received: {response}")

                # Case 2: Final data response as a tuple (fit parameters, histogram, and bin edges)
                elif isinstance(response, tuple) and len(response) == 3:
                    popt, hist, bin_edges = response
                    print("Fit parameters:", popt)
                    print("Histogram data:", hist)
                    print("Bin edges:", bin_edges)
                    break

                # Case: Unhandled data type
                else:
                    print("Error: Unexpected response format received.")
                    client_socket.close()
                    break
        client_socket.close()

        # Ensure ax is initialized
        if self.ax is None:
            print("Error: ax is not initialized.")
            return

        # Clear the previous plot
        self.ax.clear()

        # Check if the response is empty
        if len(popt) == 0 and len(hist) == 0 and len(bin_edges) == 0:
            print("No data received for plotting. Filling values with NaN.")

            # Update fit parameter output boxes with NaN
            self.entry_amplitude.config(state='normal')
            self.entry_amplitude.delete(0, tk.END)
            self.entry_amplitude.insert(0, "NaN")
            self.entry_amplitude.config(state='readonly')

            self.entry_frequency.config(state='normal')
            self.entry_frequency.delete(0, tk.END)
            self.entry_frequency.insert(0, "NaN")
            self.entry_frequency.config(state='readonly')

            self.entry_phase.config(state='normal')
            self.entry_phase.delete(0, tk.END)
            self.entry_phase.insert(0, "NaN")
            self.entry_phase.config(state='readonly')

            self.entry_offset.config(state='normal')
            self.entry_offset.delete(0, tk.END)
            self.entry_offset.insert(0, "NaN")
            self.entry_offset.config(state='readonly')

            self.canvas.draw()  # Redraw the canvas to clear the plot
            return

        # Update plot
        self.ax.hist((bin_edges[:-1] + bin_edges[1:]) / 2, bins=bin_edges, weights=hist, label='Data', alpha=0.7)
        self.ax.plot((bin_edges[:-1] + bin_edges[1:]) / 2, sine_wave((bin_edges[:-1] + bin_edges[1:]) / 2, *popt), label='Fit')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Counts')
        self.ax.legend()
        self.canvas.draw()

        # Update fit parameter output boxes
        self.entry_amplitude.config(state='normal')
        self.entry_amplitude.delete(0, tk.END)
        self.entry_amplitude.insert(0, f"{popt[0]:.3f}")
        self.entry_amplitude.config(state='readonly')

        self.entry_frequency.config(state='normal')
        self.entry_frequency.delete(0, tk.END)
        frequency_mhz = popt[1] * 1e-6
        self.entry_frequency.insert(0, f"{frequency_mhz:.5g} MHz")
        self.entry_frequency.config(state='readonly')

        self.entry_phase.config(state='normal')
        self.entry_phase.delete(0, tk.END)
        self.entry_phase.insert(0, f"{popt[2]:.3f}")
        self.entry_phase.config(state='readonly')

        self.entry_offset.config(state='normal')
        self.entry_offset.delete(0, tk.END)
        self.entry_offset.insert(0, f"{popt[3]:.3f}")
        self.entry_offset.config(state='readonly')

        # Update previous fit parameter output boxes
        self.entry_prev_amplitude.config(state='normal')
        self.entry_prev_amplitude.delete(0, tk.END)
        self.entry_prev_amplitude.insert(0, f"{self.prev_amplitude:.3f}" if self.prev_amplitude is not None else "")
        self.entry_prev_amplitude.config(state='readonly')

        self.entry_prev_frequency.config(state='normal')
        self.entry_prev_frequency.delete(0, tk.END)
        self.entry_prev_frequency.insert(0, f"{self.prev_frequency:.6g} MHz" if self.prev_frequency is not None else "")
        self.entry_prev_frequency.config(state='readonly')

        self.entry_prev_phase.config(state='normal')
        self.entry_prev_phase.delete(0, tk.END)
        self.entry_prev_phase.insert(0, f"{self.prev_phase:.3f}" if self.prev_phase is not None else "")
        self.entry_prev_phase.config(state='readonly')

        self.entry_prev_offset.config(state='normal')
        self.entry_prev_offset.delete(0, tk.END)
        self.entry_prev_offset.insert(0, f"{self.prev_offset:.3f}" if self.prev_offset is not None else "")
        self.entry_prev_offset.config(state='readonly')

        # Store current fit parameters as previous fit parameters for the next run
        self.prev_amplitude = popt[0]
        self.prev_frequency = frequency_mhz
        self.prev_phase = popt[2]
        self.prev_offset = popt[3]

        # If the server was not running before, shut it down
        if server_status == 0:
            # Add code to shut down the server if needed
            pass

class LivePlotter(QWidget):
    def __init__(self, count_reader):
        super().__init__()
        self.count_reader = count_reader
        self.client = Client(count_reader)
        
        # Set up main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Plot widget setup
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')  # Dark background
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)  # White grid lines with some transparency
        self.plot_widget.setLabel('left', "Count Rate", units='Counts/s', color='w', size='20pt')
        self.plot_widget.setLabel('bottom', "Time", units='s', color='w', size='20pt')
        self.plot_widget.getAxis('left').tickFont = pg.QtGui.QFont('Arial', 14)
        self.plot_widget.getAxis('bottom').tickFont = pg.QtGui.QFont('Arial', 14)
        self.layout.addWidget(self.plot_widget)

        # Label for displaying current count rate
        self.label = QLabel("Current Count Rate: N/A")
        self.label.setStyleSheet("color: red; font-size: 16pt;")
        self.layout.addWidget(self.label)

        # Control buttons and rate spinbox layout
        self.rate_layout = QHBoxLayout()
        self.layout.addLayout(self.rate_layout)

        self.update_rate_btn = QPushButton("Update Rate")
        self.update_rate_btn.setStyleSheet("font-size: 16pt; padding: 10px 20px;")
        self.update_rate_btn.clicked.connect(self.update_rate)
        self.rate_layout.addWidget(self.update_rate_btn)

        self.rate_spinbox = QSpinBox()
        self.rate_spinbox.setRange(1, 1000)  # Set appropriate range for rate
        self.rate_spinbox.setValue(self.get_rate())  # Initialize with current rate
        self.rate_spinbox.setStyleSheet("font-size: 16pt; padding: 10px 20px;")
        self.rate_spinbox.valueChanged.connect(self.set_rate)
        self.rate_layout.addWidget(self.rate_spinbox)

        self.control_layout = QHBoxLayout()
        self.layout.addLayout(self.control_layout)

        self.count_button = QPushButton("Start Counting")
        self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        self.count_button.clicked.connect(self.toggle_counting)
        self.control_layout.addWidget(self.count_button)

        self.pause_button = QPushButton("Pause Plot")
        self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.control_layout.addWidget(self.pause_button)

        # Checkboxes for channels
        self.checkbox_layout = QHBoxLayout()
        self.checkboxes = []
        self.layout.addLayout(self.checkbox_layout)

        # Timer and plotting data
        self.update_interval = 1000 // self.get_rate()  # Initial interval in ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_interval)

        self.times = []
        self.counts = []
        self.is_paused = False
        self.is_counting = self.client.send_command("GET_COUNTING")

        # Initialize counting button state
        if self.is_counting:
            self.count_button.setText("Stop Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        else:
            self.count_button.setText("Start Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")

    def set_rate(self, new_rate):
        """Send a command to set the new rate in the PMT_Reader."""
        try:
            command = f"SET_RATE {new_rate}"
            response = self.client.send_command(command)
            if response:
                self.update_rate()  # Update the timer interval if the rate was successfully set
        except Exception as e:
            print(f"Error setting rate: {e}")

    def get_rate(self):
        """Retrieve the update rate from PMT_Reader."""
        try:
            rate = self.client.send_command("GET_RATE")
            return rate
        except Exception as e:
            print(f"Error getting rate: {e}")
            return 5  # Default rate if unable to fetch

    def update_rate(self):
        """Update the timer interval based on the PMT_Reader's rate."""
        new_rate = self.get_rate()
        self.update_interval = 1000 // new_rate
        self.timer.setInterval(self.update_interval)
        print(f"Update interval set to {self.update_interval} ms")

    def toggle_pause(self):
        """Pause or resume the plotting."""
        if self.is_paused:
            self.timer.start(self.update_interval)
            self.pause_button.setText("Pause Plot")
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        else:
            self.timer.stop()
            self.pause_button.setText("Resume Plot")
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        self.is_paused = not self.is_paused

    def start_counting(self):
        """Send a command to start counting in the PMT_Reader."""
        try:
            self.client.send_command("START_COUNTING")
            self.is_counting = True
        except Exception as e:
            print(f"Error starting counting: {e}")

    def stop_counting(self):
        """Send a command to stop counting in the PMT_Reader."""
        try:
            self.client.send_command("STOP_COUNTING")
            self.is_counting = False
        except Exception as e:
            print(f"Error stopping counting: {e}")

    def toggle_counting(self):
        """Toggle counting on or off."""
        if self.is_counting:
            self.stop_counting()
            self.count_button.setText("Start Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        else:
            self.start_counting()
            self.count_button.setText("Stop Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")

    def update_plot(self):
        """Update the plot with the latest counts."""
        try:
            data = self.client.send_command("GET_COUNTS")

            if not data:
                print("No data received from server.")
                return

            # Extract times and counts from the data
            times, counts = data
            self.times = [time.timestamp() for time in times]
            self.counts = counts

            # Update checkboxes if not already created
            if not self.checkboxes:
                for channel_name in self.counts.keys():
                    checkbox = QCheckBox(channel_name)
                    checkbox.setChecked(True)
                    checkbox.stateChanged.connect(self.update_plot)
                    self.checkboxes.append(checkbox)
                    self.checkbox_layout.addWidget(checkbox)

            # Update plot
            self.plot_widget.clear()
            colors = ['w', 'r', 'g', 'b', 'y', 'c', 'm']  # List of colors for different lines
            for i, (channel_name, count) in enumerate(self.counts.items()):
                if self.checkboxes[i].isChecked():
                    color = colors[i % len(colors)]
                    self.plot_widget.plot(self.times, count, pen=pg.mkPen(color, width=1), name=channel_name)  # Line with different colors

            if self.counts:
                current_rates = {channel: counts[-1] for channel, counts in self.counts.items()}
                current_rates_str = ", ".join(f" {rate}" for _, rate in current_rates.items())
                self.label.setText(f"Current Count Rates: {current_rates_str}")
            else:
                self.label.setText("Current Count Rates: N/A")

        except Exception as e:
            print(f"Error updating plot: {e}")