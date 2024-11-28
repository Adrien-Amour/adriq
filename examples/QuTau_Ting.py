# Standard library imports
import time
import threading
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
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QCheckBox, QSpinBox
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

# Local application/library-specific imports
from adriq.Custom_Tkinter import CustomSpinbox, CustomIntSpinbox
from adriq.tdc_functions import filter_trailing_zeros, compute_time_diffs
from adriq.Servers import Client, Server
from adriq.QuTau import QuTau


class QuTau_Channel:
    def __init__(self, name, number, mode="idle"):
        self.name = name
        self.number = number
        self.mode = mode
        self.active = mode != "idle"
        self.recent_time_diffs = []
        self.time_diffs = []
        self.counts = 0  # Initialize counts attribute

    def save_recent_time_diffs(self):
        """Save recent time differences by extending the time_diffs attribute."""
        self.time_diffs.extend(self.recent_time_diffs)
        for i, diff in enumerate(self.time_diffs):
            if diff > 1e-4:
                print(f"Channel {self.name} - Time diff: {diff} at index {i}/{len(self.time_diffs)}")

    def discard_recent_time_diffs(self):
        """Discard recent time differences."""
        self.recent_time_diffs = []

class QuTau_Reader:
    host = 'localhost'
    port = 8001  # Set a unique port number for QuTau_Reader
    def __init__(self, channels):
        self.channels = channels
        self.ensure_all_channels()
        self.ensure_single_trap_drive_and_ps_sync()
        self.default_modes = {ch.number: ch.mode for ch in self.channels}
        self.current_mode = "idle"
        self.counts = {ch.number: [] for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}
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
        self.counts = {ch.number: [] for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}
        self.set_active_channels(["signal-f", "signal-sp"])

    def enter_rf_correlation_mode(self):
        self.current_mode = "rf_correlation"
        self.set_active_channels(["signal-f", "trap"])

    def enter_experiment_mode(self, experiment_config):
        self.current_mode = "experiment"
        # Set channel modes based on experiment_config
        for ch in self.channels:
            if ch.number in experiment_config:
                ch.mode = experiment_config[ch.number]
                ch.active = ch.mode != "idle"
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
        signal_chans = np.array(self.active_signal_channels, dtype=np.int64)
        time_diffs = compute_time_diffs(self.tstamp, self.tchannel, trigger_chan, signal_chans, sequence_length=26E-6)
        # Store time differences in the corresponding channel objects
        for ch in self.channels:
            if ch.number in signal_chans:
                ch.recent_time_diffs = time_diffs[signal_chans.tolist().index(ch.number)]
                ch.time_diffs.extend(ch.recent_time_diffs)

    def start_counting(self):
        self.counts = {ch.number: [] for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}
        self.counting = True
        self.enter_counting_mode()
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def count_rate(self):
        self.get_data()
        counts_list = count_channel_events(self.tchannel)
        for channel, count in counts_list:
            for ch in self.channels:
                if ch.number == channel:
                    ch.counts = count
        return counts_list

    def count_rate(self):
        start_time = time.time()  # Start time for the method

        # Get the latest timestamps from qutau
        timestamps = self.qutau.getLastTimestamps(True)
        tchannel = np.array(timestamps[1], dtype=np.int64)  # List of channel identifiers
        tstamp = np.array(timestamps[0], dtype=np.float64)  # Corresponding timestamps

        # Filter out trailing zeros in the timestamp array
        tstamp, tchannel = filter_trailing_zeros(tstamp, tchannel)

        # Use count_channel_events to count occurrences of each channel
        counts_list = count_channel_events(tchannel)

        # Generate the count rates list and update channel counts
        count_rates_list = []
        for i in range(8):  # Assuming 8 channels (0 to 7)
            count = next((count for channel, count in counts_list if channel == i), 0)
            count_rate = count * self.rate
            count_rates_list.append(count_rate)
            for ch in self.channels:
                if ch.number == i:
                    ch.counts.append(count_rate)
                    if len(ch.counts) > self.N:
                        ch.counts.pop(0)

        current_time = datetime.now()

        end_time = time.time()  # End time for the method
        elapsed_time = end_time - start_time

        # Calculate the remaining time to sleep to maintain the desired rate
        sleep_time = max(0, (1 / self.rate) - elapsed_time)
        time.sleep(sleep_time)

        return count_rates_list, current_time

    def _counting_loop(self):
        while self.counting:
            self.count_rate()

    def stop_counting(self):
        self.counting = False
        for ch in self.channels:
            if ch.mode in ["signal-f", "signal-sp"]:
                ch.counts = []
        self.enter_idle_mode()


    def RF_correlation(self, no_runs, rate, no_bins, update_progress_callback=None):
        timebase = self.qutau.getTimebase()

        was_counting = self.counting
        if was_counting:
            self.stop_counting()

        previous_channels = self.active_channels
        self.enter_rf_correlation_mode()
        self.update_rate(rate)

        time_diffs = []
        timestamps = self.qutau.getLastTimestamps(True)

        for run in range(no_runs):
            start_time1 = time.time()

            timestamps = self.qutau.getLastTimestamps(True)
            elapsed_time1 = time.time() - start_time1

            tchannel = np.array(timestamps[1], dtype=np.int64)
            tstamp = np.array(timestamps[0], dtype=np.float64)  # Ensure tstamp is float64
            tstamp, tchannel = filter_trailing_zeros(tstamp, tchannel)

            start_time2 = time.time()
            trap_drive_chan = next(ch.number for ch in self.channels if ch.mode == "trap")
            signal_chans = np.array([ch.number for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]], dtype=np.int64)
            time_diffs_run = compute_time_diffs(tstamp, tchannel, trap_drive_chan, signal_chans)
            if time_diffs_run and len(time_diffs_run[0]) > 0:  # Check if time_diffs_run is not empty
                time_diffs.extend(time_diffs_run[0])  # Assuming single signal channel
            elapsed_time2 = time.time() - start_time2

            sleep_time = max(0, (1 / self.rate) - elapsed_time1 - elapsed_time2)
            time.sleep(sleep_time)

            # Send progress update to the client
            if update_progress_callback:
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
        time_diffs *= timebase

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

    def get_counts(self):
        return {ch.name: ch.counts for ch in self.channels if ch.mode in ["signal-f", "signal-sp"]}

    def get_last_timestamps(self):
        timestamps = self.qutau.getLastTimestamps(True)
        tchannel = np.array(timestamps[1], dtype=np.int64)
        tstamp = np.array(timestamps[0], dtype=np.float64)
        tstamp, tchannel = filter_trailing_zeros(tstamp, tchannel)
        return tstamp, tchannel

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

    def recv_command(self, command):
        if command == "START_COUNTING":
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
            print(no_runs, rate, no_bins)
            return self.RF_correlation(int(no_runs), int(rate), int(no_bins), bool(int(show_plot[0])) if show_plot else False)
        else:
            return "Unknown command"