import tkinter as tk
from tkinter import ttk, messagebox
from adriq.pulse_sequencer import write_pulse_sequencer, control_pulse_sequencer
from adriq.Custom_Tkinter import CustomBinarySpinbox, CustomSpinbox
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

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Pulse Sequencer Control")
    app = PulseSequencerFrame(master=root)
    app.mainloop()