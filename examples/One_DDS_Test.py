import numpy as np
import matplotlib.pyplot as plt
from adriq.experiment import *
import numpy as np

# # Create the dictionary of DDS instances
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"


def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / (2 * width**2))

l854_SP2 = DDS_Ram(
    port="COM10",
    board=3,
    mode="slave",
    pulse_sequencer_pin=11,
    calibration_file=calib_directory + r"\854_calib.csv",
    max_rf_power=15000
)
dds_dict = {
    "854 SP2" : l854_SP2
}

# Create the ExperimentalSequence object
exp_sequence = Experiment_Builder(dds_dict)
exp_sequence.set_detunings(detuning_dict={"854 SP2": 10})

exp_sequence.set_trapping_parameters(
    trapping_detuning_dict={},
    trapping_amplitude_dict={}
)
# Create the cooling section (cool for 6 useconds)
exp_sequence.create_cooling_section(length=8, amplitude_dict={"854 SP2": 0.2})

# Create op section 
exp_sequence.create_section(name="Optical Pumping", duration=4, dds_functions={
    "854 SP2": lambda t: 0.5,
}, pmt_gate_high=True)

exp_sequence.build_ram_arrays()
print(l854_SP2.amplitude_array)
exp_sequence.plot_amplitude_arrays()

# Plot the amplitude arrays
# exp_sequence.plot_amplitude_arrays()
exp_sequence.flash()

while True:
    # Enter trapping mode
    l854_SP2.enter_trapping_mode()
    print("Entered trapping mode")
    time.sleep(5)  # Wait for 5 seconds

    # Enter cooling mode
    exp_sequence.create_cooling_section(length=8, amplitude_dict={"854 SP2": 0.2})
    exp_sequence.build_ram_arrays()
    exp_sequence.flash()
    print("Entered cooling mode")
    time.sleep(10)  # Wait for 5 seconds