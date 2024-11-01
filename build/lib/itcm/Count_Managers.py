# Standard library imports
import time
import threading
import random
import warnings
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
from .Custom_Tkinter import CustomSpinbox, CustomIntSpinbox


# Local application/library-specific imports
from . import QuTau

class PMT_Manager:
    _instance = None  # Singleton instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PMT_Manager, cls).__new__(cls)
        return cls._instance

    def __init__(self, rate=5, N=100):
        if not hasattr(self, 'initialized'):
            self.rate = rate
            self.N = N
            self.counting = False
            self.counts = []
            self.times = []
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

    def count_rate(self):
        start_time = time.time()  # Record the start time
        self.task.start()
        time.sleep(1 / self.rate)
        read_data = self.task.read(number_of_samples_per_channel=1)
        count1, end_time = (read_data if isinstance(read_data, int) else read_data[0] if len(read_data) > 0 else 0), time.time()
        elapsed_time = end_time - start_time  # Calculate the elapsed time
        count_rate = int(count1 / elapsed_time)  # Use the elapsed time to calculate the count rate
        self.task.stop()
        current_time = datetime.now()
        return [count_rate], current_time

    def start_counting(self):
        self.counts = []
        self.times = []
        self.counting = True
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def _counting_loop(self):
        while self.counting:
            count_rate, current_time = self.count_rate()
            self.counts.append(count_rate)
            self.times.append(current_time)
            if len(self.counts) > self.N:
                self.counts.pop(0)
                self.times.pop(0)

    def stop_counting(self):
        self.counting = False
        self.counts = []
        self.times = []

def sine_wave(x, amplitude, frequency, phase, offset):
    return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset

class QuTau_Manager:
    _instance = None  # Singleton instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(QuTau_Manager, cls).__new__(cls)
        return cls._instance

    def __init__(self, rate=5, N=100, buffersize=1000000, single_photons_chan=1, trap_drive_chan=2, pmt_counts_chan=3):
        if not hasattr(self, 'initialized'):
            self.qutau = QuTau.QuTau()
            self.rate = rate
            self.N = N
            self.counts = []
            self.buffersize = buffersize
            self.trap_drive_chan = trap_drive_chan
            self.pmt_counts_chan = pmt_counts_chan
            self.single_photons_chan = single_photons_chan
            self.devType = self.qutau.getDeviceType()
            self.active_channels = (self.single_photons_chan, self.pmt_counts_chan)
            self.qutau.enableChannels(self.active_channels)
            # self.qutau.setBufferSize(self.buffersize)  # Set the initial buffer size
            self.counting = False
            self.lock = threading.Lock()  # Initialize a lock
            self.initialized = True

    @property
    def buffersize(self):
        return self._buffersize

    @buffersize.setter
    def buffersize(self, size):
        self._buffersize = size
        # self.qutau.setBufferSize(size)  # Update buffer size in qutau

    @property
    def active_channels(self):
        return self._active_channels

    @active_channels.setter
    def active_channels(self, channels):
        self._active_channels = channels
        self.qutau.enableChannels(self._active_channels)

    def update_rate(self, new_rate):
        self.rate = new_rate
        expTime = int(round(1 / self.rate))  # Convert rate (Hz) to exposure time (ms)
        ans = self.qutau.setExposureTime(expTime)
        if ans != 0:
            print("Error in setExposureTime: " + dict_err.get(ans, "Unknown error"))

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
        with self.lock:
            self.counts = []
            self.times = []
            self.counting = True
        timestamps = self.qutau.getLastTimestamps(True)  # Clear counts
        threading.Thread(target=self._counting_loop, daemon=True).start()

    def _counting_loop(self):
        while self.counting:
            count_rate, current_time = self.count_rate()
            with self.lock:
                if count_rate:  # Only append if count_rate is not empty
                    self.counts.append(count_rate)
                    self.times.append(current_time)
                    if len(self.counts) > self.N:
                        self.counts.pop(0)
                        self.times.pop(0)

    def stop_counting(self):
        with self.lock:
            self.counting = False
            self.counts = []
            self.times = []

    def update_active_channels(self, channels):
        # Validate the input channels
        if not all(isinstance(chan, int) and 1 <= chan <= 8 for chan in channels):
            raise ValueError("All channels must be integers between 1 and 8.")

        if len(channels) != len(set(channels)):
            raise ValueError("Channels list contains duplicate values.")

        self.active_channels = channels
        self.qutau.enableChannels(channels)

    def RF_correlation(self, no_runs, rate, no_bins, update_progress_callback=None):
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

            # Update progress bar if callback is provided
            if update_progress_callback:
                update_progress_callback(run + 1)

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

        if was_counting:
            self.start_counting()

        return popt, hist, bin_edges
    
class MicromotionWindow:
    def __init__(self, parent, count_manager):
        self.parent = parent
        self.count_manager = count_manager
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

        # Add progress bar
        self.progress_bar = ttk.Progressbar(micromotion_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=5, column=0, columnspan=6, padx=5, pady=10)

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

        # Initialize progress bar
        self.progress_bar["maximum"] = no_runs
        self.progress_bar["value"] = 0

        popt, hist, bin_edges = self.count_manager.RF_correlation(no_runs, rate, no_bins, self.update_progress_bar)

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

    def update_progress_bar(self, value):
        self.progress_bar["value"] = value
        self.micromotion_window.update_idletasks()

def get_pmt_manager():
    """Function to get the singleton instance of PMT_Manager."""
    return PMT_Manager()

def get_mock_pmt_manager():
    """Function to get the singleton instance of PMT_Manager."""
    return Mock_PMT_Manager()
    
def get_qutau_manager():
    return QuTau_Manager()

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