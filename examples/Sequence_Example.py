
import matplotlib.pyplot as plt
import numpy as np
from adriq.pulse_sequencer import *
from adriq.ad9910 import *
from adriq.experiment import *
import time


# Create the dictionary of DDS instances
dds_dict = {
    "397a": DDS_Ram(port="COM10", board=0, mode="master", pulse_sequencer_pin=11, frequency=20E6),
    # "866 (OP)": DDS_Ram(port="COM10", board=1, mode="slave", pulse_sequencer_pin=11, frequency=20)
}

# Create the ExperimentalSequence object
exp_sequence = ExperimentalSequence(dds_dict)

# Create the cooling section (cool for 4 seconds)
exp_sequence.create_cooling_section(length=4, amplitude_dict={"397a": 5000})

# Create a Gaussian output function for DDS 397
def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / (2 * width**2))


# Create the playback sectionsc
# Create playback sections with names
exp_sequence.create_section(name="STIRAP", duration=7, dds_functions={
    "397a": gaussian(5000, 0.4, 2),  # Now returns a function
    # "866 (OP)": gaussian(5500, 0.4, 3),  # Now returns a function
})

exp_sequence.create_section(name="Photon Generation", duration=8, dds_functions={
    "397a": lambda t: 0,
    # "866 (OP)": gaussian(8000, 0.4, 3)  # Now returns a function
})

# Build the RAM arrays
exp_sequence.build_ram_arrays()

# Plot the amplitude arrays
exp_sequence.plot_amplitude_arrays()
exp_sequence.flash()

time.sleep(2)

control_pulse_sequencer("COM5", 'Start')
time.sleep(100)
control_pulse_sequencer("COM5", 'Stop')

