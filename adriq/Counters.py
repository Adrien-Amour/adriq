# Standard library imports
import time
import threading
import csv
from datetime import datetime
from collections import Counter
import configparser
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
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QCheckBox, QHBoxLayout, QScrollArea, QFileDialog
from PyQt5.QtWidgets import QSpinBox
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from .Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
from .tdc_functions import filter_trailing_zeros, compute_time_diffs, count_channel_events, filter_runs

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
    
    def get_counting(self): # Return the current counting status
        return self.counting

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
        return True

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
        return True

    def get_counts(self):
        with self.lock:  # Ensure thread-safe access
            return self.times, {"PMT": self.counts}

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

def load_channels_from_ini(ini_file):
    """Load channel configurations from an .ini file."""
    config = configparser.ConfigParser()
    config.read(ini_file)

    if not config.sections():
        raise ValueError(f"No valid sections found in the .ini file: {ini_file}")
    channels = []
    for section in config.sections():
        name = config[section].get('name', f'Channel{section}')
        number = int(config[section].get('number', -1))
        mode = config[section].get('mode', 'idle')
        if number == -1:
            raise ValueError(f"Invalid or missing 'number' for channel '{section}' in {ini_file}")
        channels.append(QuTau_Channel(name, number, mode=mode))
    return channels

class QuTau_Reader:
    host = 'localhost'
    port = 8001  # Set a unique port number for QuTau_Reader
 
    def __init__(self, ini_file='C:\\Users\\probe\\OneDrive - University of Sussex\\Desktop\\Experiment_Config\\qutau_config.cfg'):
        # Load channels from the specified .ini file
        self.channels = load_channels_from_ini(ini_file)
        self.qutau = QuTau.QuTau()  # Initialize QuTau object
        self.timebase = self.qutau.getTimebase()
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
        print("Idle mode entered.")
        self.current_mode = "idle"
        self.set_active_channels([])  # No active channels in idle mode

    def enter_counting_mode(self):
        self.current_mode = "counting"
        self.times = []  # Clear times array
        self.set_active_channels(["signal-sp", "signal-f"]) #(["43-f", "signal-sp"])
        print("Counting mode entered.")

    def enter_rf_correlation_mode(self):
        print("RF correlation mode entered.")
        self.current_mode = "rf_correlation"
        self.set_active_channels(["signal-f", "trap"])
    
    def exit_rf_correlation_mode(self):
        print("RF correlation mode exited.")
        self.current_mode = "idle"
        self.set_active_channels([])
    
    def enter_experiment_mode(self, experiment_config=None):
        print("Experiment mode entered.")
        self.current_mode = "experiment"
        
        # Standard experiment configuration
        standard_experiment_config = {
            0: "signal-sp",  # single_photon_chan1
            1: "signal-sp",  # single_photon_chan2
            2: "signal-sp",  # single_photon_chan3
            3: "signal-sp",  # single_photon_chan4
            4: "trigger-ram",       # Inactive-4
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
        print("Experiment mode exited.")
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

    def filter_runs_for_fluorescence(self, expected_fluorescence, pulse_window_time, bin_size=10000):
        """
        expected_fluorescence: Expected fluorescence rate while the pulse sequence is running
        """
        # Find the signal channel counting fluoresence
        signal_chans = np.array(
            [ch.number for ch in self.channels if ch.mode in ["signal-f"]],
            dtype=np.int64
        )
        
        # Check if any signal channel is found
        if signal_chans.size == 0:
            raise ValueError("No signal channels found with mode 'signal-f'.")
        
        # Assuming we use the first signal channel found
        signal_chan = signal_chans[0]
        trigger_chan = next(ch.number for ch in self.channels if ch.mode == "trigger")
        
        # Call the filter_runs function with self.tstamp and self.tchannel
        self.tstamp, self.tchannel, valid_pulse_count, total_pulses = filter_runs(
            tstamp=self.tstamp,
            tchannel=self.tchannel,
            trig_chan=trigger_chan,
            signal_chan=signal_chan,
            expected_count_rate=expected_fluorescence,
            pulse_window_time=pulse_window_time,
            bin_size=bin_size
        )

        return valid_pulse_count, total_pulses

    def compute_time_diff(self, pulse_window_time=50E-6, trigger_mode="normal"):

        if trigger_mode == "normal":

            trigger_chan = next(ch.number for ch in self.channels if ch.mode == "trigger")
            
            signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]], dtype=np.int64)

            time_diffs = compute_time_diffs(self.tstamp, self.tchannel, trigger_chan, signal_chans, pulse_window_time)
            # Store time differences in the corresponding channel objects
            for ch in self.channels:
                if ch.number in signal_chans:
                    ch.recent_time_diffs = time_diffs[signal_chans.tolist().index(ch.number)]

        elif trigger_mode == "ram":
            trigger_chan = next(ch.number for ch in self.channels if ch.mode == "trigger-ram")

            
            signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]], dtype=np.int64)

            time_diffs = compute_time_diffs(self.tstamp, self.tchannel, trigger_chan, signal_chans, pulse_window_time)
            # Store time differences in the corresponding channel objects
            for ch in self.channels:
                if ch.number in signal_chans:
                    ch.recent_time_diffs = time_diffs[signal_chans.tolist().index(ch.number)]



    def start_counting(self):
        if self.current_mode == "idle":
            print(self.current_mode)
            print ("Counting started.")
            if self.current_mode in ["experiment", "rf_correlation"]:
                print("Cannot start counting in experiment or RF correlation mode.")
                return

            self.counts = {ch.number: [] for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}
            self.enter_counting_mode()
            threading.Thread(target=self._counting_loop, daemon=True).start()
            return True
        else:
            return False

    def stop_counting(self):
        if self.current_mode == "counting":
            print("Counting stopped.")
            for ch in self.channels:
                if ch.mode in ["signal-f", "signal-sp"]:
                    ch.counts = []
            self.times = []  # Clear times array
            self.enter_idle_mode()
            return True
        else:
            return False

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
        while self.current_mode=="counting":
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
    
    def get_counting(self): # Return the current counting status
        if self.current_mode == "counting":
            return True
        else:
            return False

    def get_N(self):
        return self.N

    def update_rate(self, new_rate):
        self.rate = new_rate
        return True

    def update_N(self, new_N):
        self.N = new_N
        return True

    def RF_correlation(self, no_runs, rate, no_bins):
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
            valid_pulse_count, total_pulses = self.filter_runs_for_fluorescence(expected_fluorescence=8000, pulse_window_time=0.5E-6, bin_size=10000)
            print(f"Run {run + 1}/{no_runs}: Valid pulses: {valid_pulse_count}, Total pulses: {total_pulses}")
            start_time2 = time.time()
            trap_drive_chan = next(ch.number for ch in self.channels if ch.mode == "trap")
            signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f"]], dtype=np.int64)
            time_diffs_run = compute_time_diffs(self.tstamp, self.tchannel, trap_drive_chan, signal_chans)
            if time_diffs_run and len(time_diffs_run[0]) > 0:  # Check if time_diffs_run is not empty
                time_diffs.extend(time_diffs_run[0])  # Assuming single signal channel
            elapsed_time = time.time() - start_time
            sleep_time = max(0, (1 / self.rate) - elapsed_time)
            time.sleep(sleep_time)
            percent_complete = (run + 1) / no_runs * 100
            print(f'\rProgress: {percent_complete:.2f}%', end='', flush=True)
        if len(time_diffs) == 0:
            print("No time differences were computed.")
            self.active_channels = previous_channels
            self.qutau.enableChannels(self.active_channels)
            if was_counting:
                self.start_counting()
            return [], [], []

        time_diffs = np.array(time_diffs, dtype=np.float64)

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
        self.exit_rf_correlation_mode()
        self.enter_idle_mode()
        if was_counting:
            self.start_counting()
        

        return popt, hist, bin_edges

    def clear_channels(self):
        for ch in self.channels:
            ch.clear_time_diffs()

    def save_recent_time_diffs(self):
        for ch in self.channels:
            ch.save_recent_time_diffs()
    
    def discard_recent_time_diffs(self):
        for ch in self.channels:
            ch.discard_recent_time_diffs()
        
    def close(self):
        if self.current_mode != "experiment":
            self.qutau.deInitialize()  # Use the deInitialize method for cleanup
            print("QuTau_Reader has been closed.")
        else:
            print("Cannot close QuTau_Reader while in experiment mode.")
    

class MicromotionWindow:
    def __init__(self, parent, count_reader_client):
        self.parent = parent
        self.count_reader_client = count_reader_client
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
        try:
            no_runs = int(self.entry_no_runs.get())
            rate = float(self.entry_rate.get())
            no_bins = int(self.entry_no_bins.get())
        except ValueError:
            print("Invalid input, please enter valid numbers.")
            return
        
        popt, hist, bin_edges = self.count_reader_client.RF_correlation(no_runs, rate, no_bins)

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

class LivePlotter(QWidget):
    def __init__(self, count_reader):
        super().__init__()
        self.count_reader_client = Client(count_reader)
 
        # Set up main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
 
        # Plot widget setup
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')  # Dark background
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)  # White grid lines with transparency
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
 
        # New 'Start Log' button
        self.start_log_button = QPushButton("Start Log")
        self.start_log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: blue; color: white;")
        self.start_log_button.clicked.connect(self.start_log)
        self.control_layout.addWidget(self.start_log_button)
 
        # Timer and plotting data
        self.update_interval = 1000 // self.get_rate()  # Initial interval in ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_interval)
 
        self.times = []
        self.counts = []
        self.is_paused = False
        self.is_counting = self.count_reader_client.get_counting()
        self.colors = ['w', 'r', 'g', 'b', 'y', 'c', 'm']  # List of colors to cycle through
        self.is_logging = False  # To track if logging is active
        self.log_file = None  # To store log file reference
        self.log_writer = None  # To store the CSV writer
 
        # Initialize counting button state
        self.update_count_button_state()
 
        # Create checkboxes for each channel in a scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.checkbox_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_widget)
        self.scroll_area.setWidget(self.checkbox_widget)
        self.layout.addWidget(self.scroll_area)
        self.channel_checkboxes = {}
        self.create_channel_checkboxes()
 
    def start_log(self):
        """Start logging count rates to a file."""
        if self.is_logging:
            self.stop_log()
            return

        # Ask the user for a filename to save the log
        filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "CSV Files (*.csv)")

        if filename:
            self.is_logging = True
            self.log_file = open(filename, 'w', newline='')
            log_writer = csv.writer(self.log_file)
            log_writer.writerow(["Time"] + list(self.channel_checkboxes.keys()))  # Write header
            print(f"Logging started. Data will be saved to {filename}")

            # Save the writer for future use
            self.log_writer = log_writer

            # Update button appearance
            self.start_log_button.setText("Stop Log")
            self.start_log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: purple; color: white;")

 
    def stop_log(self):
        """Stop logging and close the file."""
        if self.is_logging:
            self.is_logging = False
            if self.log_file:
                self.log_file.close()
            self.log_writer = None
            self.log_file = None
            print("Logging stopped.")

            # Update button appearance
            self.start_log_button.setText("Start Log")
            self.start_log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: blue; color: white;")


    def create_channel_checkboxes(self):
        """Create checkboxes for each channel."""
        _, counts = self.count_reader_client.get_counts()
        for i, label in enumerate(counts.keys()):
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.checkbox_layout.addWidget(checkbox)
            self.channel_checkboxes[label] = checkbox

    def set_rate(self, new_rate):
        """Send a command to set the new rate in the PMT_Reader."""
        self.count_reader_client.update_rate(new_rate)

    def get_rate(self):
        """Retrieve the update rate from PMT_Reader."""
        try:
            rate = self.count_reader_client.get_rate()
            return rate
        except Exception as e:
            print(f"Error getting rate: {e}")
            return 10  # Default rate if unable to fetch

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

    def toggle_counting(self):
        """Toggle counting on or off."""
        if self.is_counting:
            toggle = self.count_reader_client.stop_counting()
        else:
            toggle = self.count_reader_client.start_counting()

        if toggle:
            self.is_counting = not self.is_counting
            self.update_count_button_state()

    def update_plot(self):
        """Update the plot with the latest counts."""
        try:
            counting = self.count_reader_client.get_counting()
            if counting != self.is_counting:
                self.is_counting = counting
                self.update_count_button_state()
            
            if self.is_counting and not self.is_paused:
                data = self.count_reader_client.get_counts()
                


                if not data:
                    print("No data received from server.")
                    return

                times, counts = data

                self.times = [time.timestamp() for time in times]

                # Update plot
                self.plot_widget.clear()
                for i, (label, count_values) in enumerate(counts.items()):
                    if self.channel_checkboxes[label].isChecked():
                        color = self.colors[i % len(self.colors)]  # Cycle through colors
                        self.plot_widget.plot(self.times, count_values, pen=pg.mkPen(color, width=2), name=label)

                # Update the current count rate label
                if counts and any(counts.values()):
                    current_rate = [count_values[-1] for count_values in counts.values()]
                    self.label.setText(f"Current Count Rate: {current_rate} counts/s")
                else:
                    self.label.setText("Current Count Rate: N/A")

                # Log the data if logging is active
                if self.is_logging:
                    log_data = [times[-1].timestamp()] + [counts[channel][-1] for channel in self.channel_checkboxes.keys()]
                    self.log_writer.writerow(log_data)
                
    
        except Exception as e:
            print(f"Error updating plot: {e}")
 
    def update_count_button_state(self):
        """Update the state of the counting button based on the server's counting status."""
        if self.is_counting:
            self.count_button.setText("Stop Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        else:
            self.count_button.setText("Start Counting")
            self.count_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")