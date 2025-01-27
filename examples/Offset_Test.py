import numpy as np
import matplotlib.pyplot as plt
from adriq.experiment import *
import time
import csv
from adriq.tdc_functions import filter_trailing_zeros, compute_time_diffs, filter_runs
# # Create the dictionary of DDS instances
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"
start = time.time()

def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / ((width**2)/(4*np.log(2))))

dds_dict = {
    "397a": DDS_Ram(
        port="COM9",
        board=2,
        mode="standalone",
        pulse_sequencer_pin=14,
        calibration_file=calib_directory + r"\397a_calib.csv",
        max_rf_power=2400
    ),
    "866": DDS_Ram(
        port="COM9",
        board=6,
        mode="standalone",
        pulse_sequencer_pin=13,
        calibration_file=calib_directory + r"\866_calib.csv",
        max_rf_power=7800
    )
}
pulse_sequencer = Pulse_Sequencer()

# Create the ExperimentalSequence object
exp_sequence = Experiment_Builder(dds_dict, pulse_sequencer, ram_step=0.04)

exp_sequence.set_detunings(detuning_dict={"397a": -18, "866": 0})
exp_sequence.set_trapping_parameters(
    trapping_detuning_dict={"397a": -50},
    trapping_amplitude_dict={"397a": 0.5}
)
# Create the cooling section (cool for 6 useconds)
exp_sequence.create_cooling_section(length=4, amplitude_dict={"397a": 0.1})

# Create a Gaussian output function for DDS 397a


# Create op section 
exp_sequence.create_section(name="Optical Pumping", duration=8, dds_functions={
    "397a": lambda t: 0.5,
    "866": lambda t: 0.3,
}, pmt_gate_high=True) #First stage of Optical Pumping
exp_sequence.create_section(name="Pump to Ground State", duration=2, dds_functions={
    "397a" : lambda t: 0.6,
    "866": lambda t: 0.05,
}, pmt_gate_high=False) #Second stage of Optical Pumping

#Create STIRAP section
exp_sequence.create_section(name="STIRAP", duration=16, dds_functions={
    "397a": gaussian(amplitude=0.5, width=1, centre=4),
    "866": gaussian(amplitude=0.5, width=1, centre=4)
}, pmt_gate_high=False)

exp_sequence.create_section(name="break", duration=10, dds_functions={
    "397a" : lambda t: 0.1,
    "866": lambda t: 0.1,
}, pmt_gate_high=False)

# Create the single photon section
exp_sequence.create_section(name="STIRAP test", duration=2, dds_functions={
    "866" : lambda t: 0.2,
}, pmt_gate_high=True)

exp_sequence.build_ram_arrays()

# Plot the amplitude arrays
exp_sequence.plot_amplitude_arrays()
exp_sequence.flash(Continuous=True)
pulse_sequencer.start()
try:
    print("Press Ctrl+C to stop the pulse sequencer.")
    while True:
        time.sleep(1)  # Sleep for 1 second in each iteration to avoid busy-waiting
except KeyboardInterrupt:
    print("Ctrl+C detected. Stopping the pulse sequencer...")
    pulse_sequencer.stop()
    print("Pulse sequencer stopped.")