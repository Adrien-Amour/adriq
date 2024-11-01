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
import pyqtgraph as pg
from PyQt5.QtCore import QTimer
from .Custom_Tkinter import CustomSpinbox, CustomIntSpinbox


# Local application/library-specific imports
from . import QuTau
from .Servers import Server

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
        return [count_rate], current_time

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
            return self.times, self.counts

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
        self.task.stop()  # Stop the task if it's running
        self.task.close()  # Explicitly release the resources
        print("NIDAQmx Task closed.")

class QuTau_Reader:
    host = 'localhost'
    port = 8001  # Set a unique port number for QuTau_Reader

    def __init__(self, rate=5, N=100, buffersize=1000000, trap_drive_chan=2, pmt_counts_chan=3, single_photon_chan=0):
        if not hasattr(self, 'initialized'):
            self.qutau = QuTau.QuTau()
            self.rate = rate
            self.N = N
            self.counts = []
            self.times = []
            self.buffersize = buffersize
            self.trap_drive_chan = trap_drive_chan
            self.pmt_counts_chan = pmt_counts_chan
            self.single_photon_chan = single_photon_chan
            self.devType = self.qutau.getDeviceType()
            self.active_channels = (self.single_photon_chan, self.pmt_counts_chan)
            self.qutau.enableChannels(self.active_channels)
            self.counting = False
            self.initialized = True

    def update_rate(self, new_rate):
        self.rate = new_rate
        return True

    def get_rate(self):
        return self.rate

    def update_N(self, new_N):
        self.N = new_N
        return True

    def get_N(self):
        return self.N

    def count_rate(self):
        start_time = time.time()  # Start time for the method

        # Get the latest timestamps from qutau
        timestamps = self.qutau.getLastTimestamps(True)
        if len(timestamps[0]) >= self.buffersize:
            warnings.warn("Buffer limit hit: number of timestamps equals buffer size.")
        tchannel = timestamps[1]  # List of channel identifiers
        tstamp = timestamps[0]    # Corresponding timestamps

        # Use Counter to count occurrences of each channel more efficiently
        channel_counts = Counter(tchannel)

        # Generate the count rates list directly using list comprehension
        count_rates_list = [
            channel_counts.get(i, 0) * self.rate
            for i in range(1, max(channel_counts.keys(), default=0) + 1)
        ]

        current_time = datetime.now()

        end_time = time.time()  # End time for the method
        elapsed_time = end_time - start_time

        # Calculate the remaining time to sleep to maintain the desired rate
        sleep_time = max(0, (1 / self.rate) - elapsed_time)
        time.sleep(sleep_time)

        return count_rates_list, current_time

    def start_counting(self):
        self.counts = []
        self.times = []
        self.counting = True
        timestamps = self.qutau.getLastTimestamps(True)  # Clear counts
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def _counting_loop(self):
        while self.counting:
            count_rate, current_time = self.count_rate()
            with threading.Lock():  # Ensure thread-safe access
                self.counts.append(count_rate)  # Store count rates
                self.times.append(current_time)
                if len(self.counts) > self.N:
                    self.counts.pop(0)
                    self.times.pop(0)

    def stop_counting(self):
        self.counting = False
        self.counts = []
        self.times = []

    def update_active_channels(self, trap_drive_chan, pmt_counts_chan):
        self.trap_drive_chan = trap_drive_chan
        self.pmt_counts_chan = pmt_counts_chan
        self.active_channels = (self.trap_drive_chan, self.pmt_counts_chan)  # Update active channels
        self.qutau.enableChannels(self.active_channels)

    def get_counts(self):
        with threading.Lock():  # Ensure thread-safe access
            return self.times, self.counts
 
    def RF_correlation(self, no_runs, rate, no_bins, update_progress_callback=None):
        print("calling rf correlation")
        timebase = self.qutau.getTimebase()
        print(f"Timebase: {timebase}")  # Debug print

        was_counting = self.counting
        if was_counting:
            self.stop_counting()

        previous_channels = self.active_channels
        self.active_channels = (self.trap_drive_chan, self.pmt_counts_chan)
        self.qutau.enableChannels(self.active_channels)
        self.update_rate(rate)

        time_diffs = []
        timestamps = self.qutau.getLastTimestamps(True)

        for run in range(no_runs):
            start_time = time.time()

            timestamps = self.qutau.getLastTimestamps(True)
            if len(timestamps[0]) >= self.buffersize:
                warnings.warn("Buffer limit hit: number of timestamps equals buffer size.")

            tchannel = timestamps[1]
            tstamp = timestamps[0]

            last_rf_time = None
            
            for i in range(len(tstamp)):
                if tchannel[i] == self.trap_drive_chan:
                    last_rf_time = tstamp[i]
                elif tchannel[i] == self.pmt_counts_chan and last_rf_time is not None:
                    time_diff = tstamp[i] - last_rf_time
                    time_diffs.append(time_diff)

            elapsed_time = time.time() - start_time
            sleep_time = max(0, (1 / self.rate) - elapsed_time)
            time.sleep(sleep_time)

            # Send progress update to the client
            # Send progress update to the client
            if update_progress_callback:
                percent_complete = (run + 1) / no_runs * 100
                print(f'\rProgress: {percent_complete:.2f}%', end='', flush=True)


        time_diffs = np.array(time_diffs, dtype=np.float64)
        time_diffs *= timebase

        # Remove outliers using the IQR method
        Q1 = np.percentile(time_diffs, 25)
        Q3 = np.percentile(time_diffs, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        filtered_time_diffs = time_diffs[(time_diffs >= lower_bound) & (time_diffs <= upper_bound)]

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
        if command == "START_COUNTING":
            self.start_counting()
            return True
        elif command == "STOP_COUNTING":
            self.stop_counting()
            return True
        elif command == "GET_COUNTS":
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
        elif command.startswith("START_RF_CORRELATION"):
            _, no_runs, rate, no_bins, *show_plot = command.split()
            print( no_runs, rate, no_bins)
            return self.RF_correlation(int(no_runs), int(rate), int(no_bins), bool(int(show_plot[0])) if show_plot else False)
        else:
            return "Unknown command"
    
    def close(self):
        # Stop counting if currently active
        if self.counting:
            self.counting = False
            print("Counting stopped.")

        # Ensure proper release of resources and DLL de-initialization
        result = self.qutau.deInitialize()
        if result == 0:
            print("QuTau DLL successfully de-initialized.")
        else:
            print("Error during QuTau DLL de-initialization.")

        # Clear instance variables
        self.counts.clear()
        self.times.clear()
        self.initialized = False
  
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

        # Update plot
        self.ax.clear()
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
            print("Shutting down the server as it was not running before.")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.count_reader.host, self.count_reader.port))
            client_socket.sendall(pickle.dumps("SHUTDOWN"))
            client_socket.close()

class Live_Plot(tk.Frame):
    def __init__(self, parent, count_manager, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.count_manager = count_manager
        self.animating = False
        self.checkboxes_initialized = False
        self.plot_thread = None
        self.plot_lock = threading.Lock()

        # Explicitly define the Matplotlib style settings
        plt.rcParams.update({
            'legend.frameon': False,
            'legend.numpoints': 1,
            'legend.scatterpoints': 1,
            'xtick.direction': 'out',
            'ytick.direction': 'out',
            'axes.axisbelow': True,
            'font.family': 'sans-serif',
            'grid.linestyle': '-',
            'lines.solid_capstyle': 'round',
            'axes.grid': True,
            'axes.edgecolor': 'white',
            'axes.linewidth': 0,
            'xtick.major.size': 0,
            'ytick.major.size': 0,
            'xtick.minor.size': 0,
            'ytick.minor.size': 0,
            'text.color': '0.9',
            'axes.labelcolor': '0.9',
            'xtick.color': '0.9',
            'ytick.color': '0.9',
            'grid.color': '2A3459',
            'font.sans-serif': ['Overpass', 'Helvetica', 'Helvetica Neue', 'Arial', 'Liberation Sans', 'DejaVu Sans', 'Bitstream Vera Sans', 'sans-serif'],
            'axes.prop_cycle': plt.cycler('color', ['#18c0c4', '#f62196', '#A267F5', '#f3907e', '#ffe46b', '#fefeff']),
            'image.cmap': 'RdPu',
            'figure.facecolor': '212946',
            'axes.facecolor': '212946',
            'savefig.facecolor': '212946'
        })

        # Define a muted color palette
        # Define a muted color palette
        self.colors = ['#FFFFFF', '#66CDAA', '#CD5C5C', '#9370DB', '#FFA07A', 
                    '#8B4513', '#FFB6C1', '#A9A9A9', '#20B2AA', '#FF69B4', '#FFC0CB']

        # Set the frame background to the default Tkinter grey
        self.configure(bg=self.cget('bg'), relief='raised', bd=2)

        # Create a matplotlib figure with reduced DPI for faster rendering
        self.fig = Figure(figsize=(5, 4), dpi=70)  # Lower DPI for faster rendering
        self.ax = self.fig.add_subplot(111)

        # Initial plot settings with a non-grey background to distinguish from the frame
        self.ax.set_title("Live Counts", fontsize=14, fontweight='bold')
        self.ax.set_xlabel("Time", fontsize=12, fontweight='bold')
        self.ax.set_ylabel("Counts", fontsize=12, fontweight='bold')
        # self.ax.set_facecolor('#ffffff')  # White background for plot area
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.xaxis.set_major_locator(plt.MaxNLocator(4))  # Limit to 4 x-ticks

        # Create a frame to hold the control widgets
        self.control_frame = tk.Frame(self, bg=self.cget('bg'), width=300)  # Increased width
        self.control_frame.grid(row=0, column=0, sticky='ns')  # Use grid layout
        self.control_frame.grid_propagate(False)  # Prevent the frame from resizing based on its content

        # Create a canvas widget to display the plot
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=1, sticky='nsew')  # Use grid layout

        # Configure grid column weights to ensure the canvas expands
        self.grid_columnconfigure(1, weight=1)

        # Initialize channel control widgets
        self.channel_controls = []

        # Create a label to display the counter in the top-left corner
        # Create a label to display the counter in the top-left corner
        self.counter_label = tk.Label(self, text="", font=("Helvetica", 60), width=30, bg=self.cget('bg'))  # Increased font size and width
        self.counter_label.grid(row=1, column=0, columnspan=2, sticky='ew')  # Place label in grid and span both columns
        # Create a frame to hold the "Start/Stop" button and rate controls horizontally
        self.control_buttons_frame = tk.Frame(self.control_frame, bg=self.cget('bg'))
        self.control_buttons_frame.grid(row=0, column=0, sticky='ew')

        # Create a frame for the rate controls within the control_buttons_frame
        rate_frame = tk.Frame(self.control_buttons_frame, bg=self.cget('bg'))
        rate_frame.grid(row=0, column=0, padx=5)

        # Create a label for the rate with black text
        self.rate_label = tk.Label(rate_frame, text="Read Rate:", font=("Helvetica", 12), bg=self.cget('bg'), fg='black')
        self.rate_label.grid(row=0, column=0)

        # Create a Spinbox for updating rate with integer values
        self.rate_spinbox = tk.Spinbox(rate_frame, from_=1, to=100, increment=1, font=("Helvetica", 12), width=5)
        self.rate_spinbox.grid(row=0, column=1)

        # Initialize Spinbox with the current rate
        self.rate_spinbox.delete(0, tk.END)
        self.rate_spinbox.insert(0, self.count_manager.rate)

        # Bind Enter key to the Spinbox
        self.rate_spinbox.bind('<Return>', self.update_rate_from_spinbox)

        # Create a frame for the N controls within the control_buttons_frame
        n_frame = tk.Frame(self.control_buttons_frame, bg=self.cget('bg'))
        n_frame.grid(row=1, column=0, padx=5)

        # Create a label for N with black text
        self.n_label = tk.Label(n_frame, text="N Points:", font=("Helvetica", 12), bg=self.cget('bg'), fg='black')
        self.n_label.grid(row=0, column=0)

        # Create a Spinbox for updating N with integer values
        self.n_spinbox = tk.Spinbox(n_frame, from_=1, to=100, increment=1, font=("Helvetica", 12), width=5)
        self.n_spinbox.grid(row=0, column=1)

        # Initialize Spinbox with the current N
        self.n_spinbox.delete(0, tk.END)
        self.n_spinbox.insert(0, self.count_manager.N)

        # Bind Enter key to the Spinbox
        self.n_spinbox.bind('<Return>', self.update_n_from_spinbox)

        # Create Start/Stop button with dark grey background
        self.start_stop_button = tk.Button(self.control_buttons_frame, text="Start", command=self.toggle_animation, font=("Helvetica", 14), height=1, bg="green", fg="white")
        self.start_stop_button.grid(row=0, column=1, rowspan=2, padx=5, pady=(10, 0))  # Align vertically with the two Spinboxes

        # Create a frame to hold the checkboxes in the control_frame
        self.checkboxes_frame = tk.Frame(self.control_frame, bg=self.cget('bg'))
        self.checkboxes_frame.grid(row=1, column=0, sticky='ns')

        # Create a label and entry for Max FPS
        self.fps_label = tk.Label(self.checkboxes_frame, text="Max FPS:", font=("Helvetica", 12), bg=self.cget('bg'), fg='black')
        self.fps_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.fps_entry = tk.Entry(self.checkboxes_frame, font=("Helvetica", 12), width=10)
        self.fps_entry.grid(row=0, column=1, padx=5, pady=2)
        self.fps_entry.insert(0, "0.00")  # Initialize with 0.00

        # Initialize channel checkbox variables and list
        self.channel_vars = []

        # Schedule the first plot update
        self.start_plot_thread()

    def update_rate_from_spinbox(self, event=None):
        try:
            new_rate = int(self.rate_spinbox.get())
            if new_rate > 0:
                self.count_manager.update_rate(new_rate)
                self.current_rate = new_rate
        except ValueError:
            pass  # Handle invalid input gracefully

    def update_n_from_spinbox(self, event=None):
        try:
            new_n = int(self.n_spinbox.get())
            if new_n > 0:
                self.count_manager.update_N(new_n)
                self.current_n = new_n
        except ValueError:
            pass  # Handle invalid input gracefully

    def initialize_checkboxes(self):
        # Wait until counts[0] has a non-zero value or until 10 seconds timeout
        start_time = time.time()  # Record the start time
        while not self.count_manager.counts or not self.count_manager.counts[0]:
            if time.time() - start_time > 10:  # 10 seconds timeout
                raise TimeoutError("Failed to initialize checkboxes: counts[0] is zero after 10 seconds.")
            self.update()  # Update the Tkinter event loop to keep the application responsive

        # Clear existing controls if any
        for widget in self.checkboxes_frame.winfo_children():
            widget.destroy()

        # Create a label and entry for Max FPS
        self.fps_label = tk.Label(self.checkboxes_frame, text="Max FPS:", font=("Helvetica", 12), bg=self.cget('bg'), fg='black')
        self.fps_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.fps_entry = tk.Entry(self.checkboxes_frame, font=("Helvetica", 12), width=10)
        self.fps_entry.grid(row=0, column=1, padx=5, pady=2)
        self.fps_entry.insert(0, "0.00")  # Initialize with 0.00

        # Create new controls based on the number of channels
        num_channels = len(self.count_manager.counts[0])
        self.channel_vars = []  # Reset the list of BooleanVar instances
        self.channel_controls = []  # Reset the list of control widgets

        for i in range(num_channels):
            var = BooleanVar(value=True)  # Default to checked

            # Create checkbox for this channel with black text
            checkbutton = tk.Checkbutton(self.checkboxes_frame, text=f"Channel {i+1}:", variable=var, font=("Helvetica", 12), bg=self.cget('bg'), fg='black')
            checkbutton.grid(row=i+1, column=0, padx=5, pady=2, sticky="w")

            # Create count box (label) for this channel with sunken relief
            count_box = tk.Label(self.checkboxes_frame, text="0", font=("Helvetica", 25), bg="white", width=8, anchor="w", relief="sunken")
            count_box.grid(row=i+1, column=1, padx=5, pady=2)

            self.channel_vars.append(var)
            self.channel_controls.append((count_box, var))

        self.checkboxes_initialized = True  # Set the flag when initialization is complete

    def toggle_animation(self):
        if self.animating:
            self.animating = False
            self.count_manager.stop_counting()
            self.start_stop_button.config(text="Start", bg="green")
        else:
            # Start counting before initializing checkboxes
            self.count_manager.start_counting()

            # Initialize checkboxes, animating is set to True after checkboxes are initialized
            try:
                self.initialize_checkboxes()
                self.animating = True  # Only set to True after checkboxes are successfully initialized
                self.start_stop_button.config(text="Stop", bg="red")
            except TimeoutError as e:
                print(e)
                self.count_manager.stop_counting()
                self.start_stop_button.config(text="Start", bg="green")

    def start_plot_thread(self):
        if self.plot_thread is None or not self.plot_thread.is_alive():
            self.plot_thread = threading.Thread(target=self.update_plot)
            self.plot_thread.daemon = True
            self.plot_thread.start()

    def update_plot(self):
        while True:
            start_time = time.time()  # Start time for FPS calculation
            if self.animating and self.checkboxes_initialized:
                with self.plot_lock:
                    self.ax.clear()

                    # Determine which channels are selected
                    selected_channels = [i for i, var in enumerate(self.channel_vars) if var.get()]
                    if self.count_manager.counting and self.count_manager.counts:
                        times = [t.strftime('%H:%M:%S') + f".{t.microsecond // 1000:03d}" for t in self.count_manager.times]

                        # Ensure the number of x points matches the number of y points
                        while len(times) > len(self.count_manager.counts):
                            times.pop()  # Remove the most recent x point
                        while len(self.count_manager.counts) > len(times):
                            self.count_manager.counts.pop()  # Remove the most recent y point
                        for i in selected_channels:
                            if all(i < len(count) for count in self.count_manager.counts):
                                color = self.colors[i % len(self.colors)]  # Use modulo to cycle through colors if there are more channels than colors
                                counts = [count[i] for count in self.count_manager.counts]  # Extract counts for this channel
                                while len(counts) > len(times):
                                    counts.pop()
                                while len(counts) < len(times):
                                    counts.append(0)  # Or some default value
                                self.ax.plot(times, counts, label=f"Channel {i + 1}", color=color)
                            else:
                                print(f"Index {i} is out of range for some counts in self.count_manager.counts")

                        self.ax.set_xlabel("Time")
                        self.ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
                        self.ax.set_ylabel("Counts")
                        self.ax.legend(loc='lower left')  # Set legend location to bottom-left

                    else:
                        # Handle the case where counting is not active or counts are empty
                        self.ax.clear()
                        self.ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
                        self.ax.set_ylabel("Counts")
                        self.ax.legend().set_visible(False)  # Hide legend if no data to plot

                    # Update the count boxes with the latest count for each channel
                    if self.count_manager.counts:
                        latest_counts = self.count_manager.counts[-1]
                        for i, (count_box, var) in enumerate(self.channel_controls):
                            if var.get():
                                if i < len(latest_counts):
                                    count_box.config(text=str(latest_counts[i]))
                                else:
                                    count_box.config(text="Index out of range")
                            else:
                                count_box.config(text="")

                    # Update the plot
                    self.canvas.draw()

            end_time = time.time()  # End time for FPS calculation
            elapsed_time = end_time - start_time
            if elapsed_time > 0:
                fps = 1 / elapsed_time
                self.fps_entry.delete(0, tk.END)
                self.fps_entry.insert(0, f"{fps:.2f}")

            # Calculate the remaining time to sleep to maintain the desired update rate
            sleep_time = max(0, (1 / self.count_manager.rate) - elapsed_time)
            time.sleep(sleep_time)

class LivePlotter(QWidget):
    def __init__(self, count_reader):
        super().__init__()
        self.count_reader = count_reader
        
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
        self.label.setStyleSheet("color: white; font-size: 16pt;")
        self.layout.addWidget(self.label)

        # Control buttons
        self.update_rate_btn = QPushButton("Update Rate")
        self.update_rate_btn.setStyleSheet("font-size: 16pt; padding: 10px 20px;")
        self.update_rate_btn.clicked.connect(self.update_rate)
        self.layout.addWidget(self.update_rate_btn)

        self.pause_button = QPushButton("Pause Plot")
        self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.layout.addWidget(self.pause_button)

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

        # Start counting in the PMT reader
        self.start_counting()

    def get_rate(self):
        """Retrieve the update rate from PMT_Reader."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.count_reader.host, self.count_reader.port))
            client.sendall(pickle.dumps("GET_RATE"))
            rate = pickle.loads(client.recv(4096))
            client.close()
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
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        else:
            self.timer.stop()
            self.pause_button.setText("Resume Plot")
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        self.is_paused = not self.is_paused

    def start_counting(self):
        """Send a command to start counting in the PMT_Reader."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.count_reader.host, self.count_reader.port))
            client.sendall(pickle.dumps("START_COUNTING"))
            client.close()
        except Exception as e:
            print(f"Error starting counting: {e}")

    def update_plot(self):
        """Update the plot with the latest counts."""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.count_reader.host, self.count_reader.port))
            client.sendall(pickle.dumps("GET_COUNTS"))
            data = client.recv(4096)
            client.close()

            if not data:
                print("No data received from server.")
                return

            times, counts = pickle.loads(data)
            self.times = [time.timestamp() for time in times]
            self.counts = counts

            # Update checkboxes if not already created
            if not self.checkboxes:
                for i in range(len(self.counts[0])):
                    checkbox = QCheckBox(f"Channel {i+1}")
                    checkbox.setChecked(True)
                    checkbox.stateChanged.connect(self.update_plot)
                    self.checkboxes.append(checkbox)
                    self.checkbox_layout.addWidget(checkbox)

            # Update plot
            self.plot_widget.clear()
            colors = ['w', 'r', 'g', 'b', 'y', 'c', 'm']  # List of colors for different lines
            for i, count in enumerate(zip(*self.counts)):
                if self.checkboxes[i].isChecked():
                    color = colors[i % len(colors)]
                    self.plot_widget.plot(self.times, count, pen=pg.mkPen(color, width=1))  # Line with different colors

            # Update label with the latest count rate
            if self.counts:
                current_rate = self.counts[-1]
                self.label.setText(f"Current Count Rate: {current_rate}")
            else:
                self.label.setText("Current Count Rate: N/A")

        except Exception as e:
            print(f"Error updating plot: {e}")
