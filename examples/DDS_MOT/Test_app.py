import tkinter as tk
from tkinter import ttk, messagebox
from adriq.ad9910 import *
from adriq.pulse_sequencer import write_pulse_sequencer, control_pulse_sequencer
from adriq.Custom_Tkinter import CustomBinarySpinbox, CustomSpinbox
import time
import serial.tools.list_ports
import threading

class PulseSequencerFrame(tk.Frame):
    def __init__(self, master=None, pulse_sequencer_port="COM5"):
        super().__init__(master)
        self.grid(padx=10, pady=10)
        self.pulse_sequencer_port = pulse_sequencer_port
        self.create_widgets()

    def create_widgets(self):
        self.pulses = []
        self.pulse_lengths = []

        # Frame for pulses and lengths
        self.pulse_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        self.pulse_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # Labels for pulses and lengths
        self.pulse_label = tk.Label(self.pulse_frame, text="Pulses")
        self.pulse_label.grid(row=0, column=0, padx=5, pady=5)
        self.length_label = tk.Label(self.pulse_frame, text="Time")
        self.length_label.grid(row=0, column=1, padx=5, pady=5)

        # Add initial pulse input row
        self.add_pulse_row()

        # Frame for other options
        self.options_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        self.options_frame.grid(row=1, column=0, padx=10, pady=10, sticky="n")

        self.continuous_var = tk.BooleanVar()
        self.continuous_check = tk.Checkbutton(self.options_frame, text="Continuous", variable=self.continuous_var)
        self.continuous_check.grid(row=0, column=0, padx=5, pady=5)

        self.n_cycles_label = tk.Label(self.options_frame, text="N Cycles:")
        self.n_cycles_label.grid(row=1, column=0, padx=5, pady=5)
        self.n_cycles_entry = CustomSpinbox(self.options_frame, from_=0, to=100000, initial_value=10000)
        self.n_cycles_entry.grid(row=1, column=1, padx=5, pady=5)

        self.end_pulse_label = tk.Label(self.options_frame, text="End Pulse:")
        self.end_pulse_label.grid(row=2, column=0, padx=5, pady=5)
        self.end_pulse_entry = CustomBinarySpinbox(self.options_frame, from_=0, to=65535, initial_value="0000000000000000")
        self.end_pulse_entry.grid(row=2, column=1, padx=5, pady=5)

        self.measurement_window_label = tk.Label(self.options_frame, text="Measurement Window:")
        self.measurement_window_label.grid(row=3, column=0, padx=5, pady=5)
        self.measurement_window_entry = CustomSpinbox(self.options_frame, from_=0, to=255, initial_value=1)
        self.measurement_window_entry.grid(row=3, column=1, padx=5, pady=5)

        self.threshold_counts_label = tk.Label(self.options_frame, text="Threshold Counts:")
        self.threshold_counts_label.grid(row=4, column=0, padx=5, pady=5)
        self.threshold_counts_entry = CustomSpinbox(self.options_frame, from_=0, to=255, initial_value=4)
        self.threshold_counts_entry.grid(row=4, column=1, padx=5, pady=5)

        self.clock_frequency_label = tk.Label(self.options_frame, text="Clock Frequency:")
        self.clock_frequency_label.grid(row=5, column=0, padx=5, pady=5)
        self.clock_frequency_entry = CustomSpinbox(self.options_frame, from_=0, to=1000, initial_value=80)
        self.clock_frequency_entry.grid(row=5, column=1, padx=5, pady=5)

        self.initial_delay_label = tk.Label(self.options_frame, text="Initial Delay:")
        self.initial_delay_label.grid(row=6, column=0, padx=5, pady=5)
        self.initial_delay_entry = CustomSpinbox(self.options_frame, from_=-1000, to=1000, initial_value=-33)
        self.initial_delay_entry.grid(row=6, column=1, padx=5, pady=5)

        self.delay_label = tk.Label(self.options_frame, text="Delay:")
        self.delay_label.grid(row=7, column=0, padx=5, pady=5)
        self.delay_entry = CustomSpinbox(self.options_frame, from_=0, to=1000, initial_value=111)
        self.delay_entry.grid(row=7, column=1, padx=5, pady=5)

        # Add Pulse button
        self.add_pulse_button = tk.Button(self.options_frame, text="Add Pulse", command=self.add_pulse_row)
        self.add_pulse_button.grid(row=8, column=0, columnspan=2, padx=5, pady=5)

        # Frame for control buttons
        self.control_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        self.control_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="n")

        self.start_button = tk.Button(self.control_frame, text="Start", command=self.start_pulse_sequencer_thread)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(self.control_frame, text="Stop", command=self.stop_pulse_sequencer_thread)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

    def add_pulse_row(self):
        row = len(self.pulses) + 1

        pulse_spinbox = CustomBinarySpinbox(self.pulse_frame, from_=0, to=65535, initial_value="0000000000000000")
        pulse_spinbox.grid(row=row, column=0, padx=5, pady=5)

        length_spinbox = CustomSpinbox(self.pulse_frame, from_=0, to=100000, initial_value=1000)
        length_spinbox.grid(row=row, column=1, padx=5, pady=5)

        delete_button = tk.Button(self.pulse_frame, text="Delete Pulse", command=lambda: self.delete_pulse(pulse_spinbox, length_spinbox, delete_button))
        delete_button.grid(row=row, column=2, padx=5, pady=5)

        self.pulses.append(pulse_spinbox)
        self.pulse_lengths.append(length_spinbox)

    def delete_pulse(self, pulse_spinbox, length_spinbox, delete_button):
        row = pulse_spinbox.grid_info()['row']

        pulse_spinbox.grid_forget()
        length_spinbox.grid_forget()
        delete_button.grid_forget()

        self.pulses.remove(pulse_spinbox)
        self.pulse_lengths.remove(length_spinbox)

        for widget in self.pulse_frame.grid_slaves():
            if widget.grid_info()['row'] > row:
                widget.grid_configure(row=widget.grid_info()['row'] - 1)

    def start_pulse_sequencer_thread(self):
        threading.Thread(target=self.start_pulse_sequencer).start()

    def start_pulse_sequencer(self):
        try:
            pulses = [spinbox.get() for spinbox in self.pulses]
            pulse_lengths = [int(spinbox.get()) for spinbox in self.pulse_lengths]

            write_pulse_sequencer(
                self.pulse_sequencer_port,
                pulses,
                pulse_lengths,
                Continuous=self.continuous_var.get(),
                N_Cycles=int(self.n_cycles_entry.get()),
                End_Pulse=self.end_pulse_entry.get(),
                Measurement_Window=int(self.measurement_window_entry.get()),
                Threshold_Counts=int(self.threshold_counts_entry.get()),
                Clock_Frequency=int(self.clock_frequency_entry.get()),
                Initial_Delay=int(self.initial_delay_entry.get()),
                Delay=int(self.delay_entry.get()),
                Verbose=True
            )
            control_pulse_sequencer(self.pulse_sequencer_port, 'Start', Verbose=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_pulse_sequencer_thread(self):
        threading.Thread(target=self.stop_pulse_sequencer).start()

    def stop_pulse_sequencer(self):
        try:
            control_pulse_sequencer(self.pulse_sequencer_port, 'Stop', Verbose=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))

class AD9910ProfileSettingsFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.grid(padx=10, pady=10)
        self.create_widgets()

    def create_widgets(self):
        # COM port selection
        tk.Label(self, text="COM Port").pack()
        self.com_port_var = tk.StringVar()
        self.com_port_menu = ttk.Combobox(self, textvariable=self.com_port_var)
        self.com_port_menu['values'] = self.get_com_ports()
        self.com_port_menu.current(0)  # Default to the first available COM port
        self.com_port_menu.pack()
        self.com_port_menu.bind("<<ComboboxSelected>>", self.reset_upper_limit)

        # Amplitude slider
        tk.Label(self, text="Amplitude").pack()
        self.amplitude_slider = tk.Scale(self, from_=0, to=5000, orient=tk.HORIZONTAL, length=400)
        self.amplitude_slider.set(1500)
        self.amplitude_slider.pack()
        self.amplitude_slider.bind("<ButtonRelease-1>", self.apply_settings)

        # Frequency slider
        tk.Label(self, text="Frequency").pack()
        self.frequency_slider = tk.Scale(self, from_=0, to=1000, orient=tk.HORIZONTAL, length=400)
        self.frequency_slider.set(200)
        self.frequency_slider.pack()
        self.frequency_slider.bind("<ButtonRelease-1>", self.apply_settings)

        # Upper limit spinbox
        tk.Label(self, text="Amplitude Upper Limit").pack()
        self.upper_limit_spinbox = CustomSpinbox(self, from_=0, to=2**14-1, increment=100) #14 bit ASF
        self.upper_limit_spinbox.set(5000)
        self.upper_limit_spinbox.pack()
        self.upper_limit_spinbox.bind("<ButtonRelease-1>", lambda event: self.amplitude_slider.config(to=int(self.upper_limit_spinbox.get())))

        # Board selection
        tk.Label(self, text="Board").pack()
        self.board_var = tk.StringVar()
        self.board_menu = ttk.Combobox(self, textvariable=self.board_var)
        self.board_menu['values'] = [str(i) for i in range(8)]
        self.board_menu.current(3)  # Default to Board 3
        self.board_menu.pack()
        self.board_menu.bind("<<ComboboxSelected>>", self.reset_upper_limit)

        # Profile selection
        tk.Label(self, text="Profile").pack()
        self.profile_var = tk.StringVar()
        self.profile_menu = ttk.Combobox(self, textvariable=self.profile_var)
        self.profile_menu['values'] = [str(i) for i in range(8)]
        self.profile_menu.current(7)  # Default to Profile 7
        self.profile_menu.pack()

        # Frequency scan settings
        tk.Label(self, text="Frequency Start (Hz)").pack()
        self.frequency_start_entry = tk.Entry(self)
        self.frequency_start_entry.pack()

        tk.Label(self, text="Frequency End (Hz)").pack()
        self.frequency_end_entry = tk.Entry(self)
        self.frequency_end_entry.pack()

        tk.Label(self, text="Number of Points").pack()
        self.points_entry = tk.Entry(self)
        self.points_entry.pack()

        tk.Label(self, text="Timestep (s)").pack()
        self.timestep_entry = tk.Entry(self)
        self.timestep_entry.pack()

        # Apply General Settings button
        self.general_settings_button = tk.Button(self, text="Apply General Settings", command=self.apply_general_settings)
        self.general_settings_button.pack()

        # Frequency Scan button
        self.scan_button = tk.Button(self, text="Scan Frequency", command=self.start_scan_thread)
        self.scan_button.pack()

        # Stop Scan button
        self.stop_button = tk.Button(self, text="Stop Scan", command=self.stop_scanning)
        self.stop_button.pack()

    def apply_settings(self, event=None):
        Standalone_Boards = self.com_port_var.get()
        Board = int(self.board_var.get())
        profile = int(self.profile_var.get())
        A = self.amplitude_slider.get()
        f = self.frequency_slider.get()
        p = 0  # Assuming phase is fixed at 0

        print("Profile Setting profile:", profile, "of Board:", Board, "on COM port:", Standalone_Boards, "Amplitude:", A, "Frequency:", f, "Phase:", p)
        single_tone_profile_setting(Standalone_Boards, Board, profile, PLL_Multiplier=40, Amplitude=A, Phase_Offset=p, Frequency=f, Verbose=False)

    def apply_general_settings(self):
        Standalone_Boards = self.com_port_var.get()
        Board = int(self.board_var.get())
        print("General Setting Board:", Board, "on COM port:", Standalone_Boards)
        general_setting_standalone(Standalone_Boards, Board)

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def reset_upper_limit(self, event=None):
        self.upper_limit_spinbox.set(5000)
        self.amplitude_slider.config(to=5000)

    def scan_frequency(self):
        global scanning
        scanning = True
        Standalone_Boards = self.com_port_var.get()
        Board = int(self.board_var.get())
        profile = int(self.profile_var.get())
        A = self.amplitude_slider.get()
        f_start = float(self.frequency_start_entry.get())
        f_end = float(self.frequency_end_entry.get())
        points = int(self.points_entry.get())
        timestep = float(self.timestep_entry.get())

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

    def start_scan_thread(self):
        global scan_thread
        if scan_thread is None or not scan_thread.is_alive():
            scan_thread = threading.Thread(target=self.scan_frequency)
            scan_thread.start()

    def stop_scanning(self):
        global scanning
        scanning = False
        if scan_thread is not None:
            scan_thread.join()

class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control Application")
        self.geometry("800x600")

        self.tab_control = ttk.Notebook(self)

        self.pulse_sequencer_frame = PulseSequencerFrame(self.tab_control)
        self.tab_control.add(self.pulse_sequencer_frame, text="Pulse Sequencer")

        self.ad9910_profile_settings_frame = AD9910ProfileSettingsFrame(self.tab_control)
        self.tab_control.add(self.ad9910_profile_settings_frame, text="AD9910 Profile Settings")

        self.tab_control.pack(expand=1, fill="both")

if __name__ == "__main__":
    app = ControlApp()
    app.mainloop()