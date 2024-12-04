import numpy as np
import matplotlib.pyplot as plt
from adriq.experiment import *
import numpy as np

# # Create the dictionary of DDS instances
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"


def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / (2 * width**2))

"""
Cooling beams at the start of the dictionary allows us to flash the cooling beams first,
so that the ion remains cooling during the flashing process.
"""
dds_dict = {
    "397c": DDS_Ram(
    port="COM9",
    board=4,
    mode="standalone",
    pulse_sequencer_pin=14,
    calibration_file=calib_directory + r"\397c_calib.csv",
    max_rf_power=1600
),
    "854 SP1": DDS_Ram(
    port="COM10",
    board=2,
    mode="slave",
    pulse_sequencer_pin=11,
    calibration_file=calib_directory + r"\854_calib.csv",
    max_rf_power=15000
),
    "850 SP1": DDS_Ram(
    port="COM10",
    board=0,
    mode="master",
    pulse_sequencer_pin=12,
    calibration_file=calib_directory + r"\850_calib.csv",
    max_rf_power=15000
),
"397a": DDS_Ram(
    port="COM9",
    board=2,
    mode="standalone",
    pulse_sequencer_pin=14,
    calibration_file=calib_directory + r"\397a_calib.csv",
    max_rf_power=2400
),
"397b": DDS_Ram(
    port="COM9",
    board=0,
    mode="standalone",
    pulse_sequencer_pin=15,
    calibration_file=calib_directory + r"\397b_calib.csv",
    max_rf_power=2900
),
"866": DDS_Ram(
    port="COM9",
    board=6,
    mode="standalone",
    pulse_sequencer_pin=11,
    calibration_file=calib_directory + r"\866_calib.csv",
    max_rf_power=7800
),
"866 OP": DDS_Ram(
    port="COM9",
    board=1,
    mode="standalone",
    pulse_sequencer_pin=15,
    calibration_file=calib_directory + r"\854_rp_calib.csv",
    max_rf_power=10700
),
"850 RP": DDS_Ram(
    port="COM9",
    board=5,
    mode="standalone",
    pulse_sequencer_pin=13,
    calibration_file=calib_directory + r"\850_rp_calib.csv",
    max_rf_power=7450
),

"850 SP2": DDS_Ram(
    port="COM10",
    board=1,
    mode="slave",
    pulse_sequencer_pin=12,
    calibration_file=calib_directory + r"\850_calib.csv",
    max_rf_power=15000
),
"854 SP2": DDS_Ram(
    port="COM10",
    board=3,
    mode="slave",
    pulse_sequencer_pin=11,
    calibration_file=calib_directory + r"\854_calib.csv",
    max_rf_power=15000
)
}

# Create the ExperimentalSequence object
exp_sequence = Experiment_Builder(dds_dict)
exp_sequence.set_detunings(detuning_dict={"850 SP1": 10, "850 SP2": 10, "854 SP1": 0, "854 SP2": 0, "397a": -18, "397b": -18, "397c": -18, "866": -22, "866 OP": 30, "850 RP": 0})

exp_sequence.set_trapping_parameters(
    trapping_detuning_dict={"397c": -50},
    trapping_amplitude_dict={"397c": 0.5}
)

# Create the cooling section (cool for 6 useconds)
exp_sequence.create_cooling_section(length=8, amplitude_dict={"397c": 0.1, "854 SP1": 0.1, "850 SP1": 1})

# Create a Gaussian output function for DDS 397a


# Create op section 
exp_sequence.create_section(name="Optical Pumping", duration=8, dds_functions={
    "397c": lambda t: 0.5,
    "866 OP": lambda t: 0.3,
    "854 SP1": lambda t: 0.2,
}, pmt_gate_high=True)
exp_sequence.create_section(name="Pump Out Of Middle States", duration=2, dds_functions={
    "866 OP" : lambda t: 1,
}, pmt_gate_high=True)


exp_sequence.create_section(name="Single Photon", duration=8, dds_functions={
    "850 SP2": gaussian(amplitude=1, width=1,centre=4)
}, pmt_gate_high=False)

# exp_sequence.create_section(name="Pump Out of D5/2", duration=4, dds_functions={
#     "854 SP1": gaussian(1, 0.6, 2),
# }, pmt_gate_high=False)

exp_sequence.build_ram_arrays()

# Plot the amplitude arrays
# exp_sequence.plot_amplitude_arrays()
#exp_sequence.flash()


exp_runner = Experiment_Runner(
    dds_dict,
    timeout=100,
    pmt_threshold=2000,
    expected_fluorescence=7500,
    sp_threshold=None,
    load_timeout = 50
)

while True:
    try:
        result = exp_runner.load()
        print(result)
        if result:
            print("Load succeeded.")
            break
        else:
            print("Load failed. Press Enter to retry.")
            input()
    except Exception as e:
        print(f"An error occurred: {e}. Press Enter to retry.")
        input()