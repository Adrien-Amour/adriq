import numpy as np
import matplotlib.pyplot as plt
from adriq.experiment import *
import numpy as np

# # Create the dictionary of DDS instances
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"

dds_dict = {
        "397c": DDS_Ram(
        port="COM9",
        board=4,
        mode="standalone",
        pulse_sequencer_pin=14,
        detuning=-18,
        calibration_file=calib_directory + r"\397c_calib.csv",
        max_rf_power=1600
    ),
        "854 SP1": DDS_Ram(
        port="COM10",
        board=2,
        mode="slave",
        pulse_sequencer_pin=11,
        detuning=0,
        calibration_file=calib_directory + r"\854_calib.csv",
        max_rf_power=15000
    ),
        "850 SP1": DDS_Ram(
        port="COM10",
        board=0,
        mode="master",
        pulse_sequencer_pin=12,
        detuning=0,
        calibration_file=calib_directory + r"\850_calib.csv",
        max_rf_power=15000
    ),

    "397a": DDS_Ram(
        port="COM9",
        board=2,
        mode="standalone",
        pulse_sequencer_pin=14,
        detuning=0,
        calibration_file=calib_directory + r"\397a_calib.csv",
        max_rf_power=2400
    ),
    "397b": DDS_Ram(
        port="COM9",
        board=0,
        mode="standalone",
        pulse_sequencer_pin=15,
        detuning=0,
        calibration_file=calib_directory + r"\397b_calib.csv",
        max_rf_power=2900
    ),
    "397c": DDS_Ram(
        port="COM9",
        board=4,
        mode="standalone",
        pulse_sequencer_pin=14,
        detuning=-18,
        calibration_file=calib_directory + r"\397c_calib.csv",
        max_rf_power=1600
    ),
    "866": DDS_Ram(
        port="COM9",
        board=6,
        mode="standalone",
        pulse_sequencer_pin=11,
        detuning=0,
        calibration_file=calib_directory + r"\866_calib.csv",
        max_rf_power=7800
    ),
    "866 OP": DDS_Ram(
        port="COM9",
        board=1,
        mode="standalone",
        pulse_sequencer_pin=15,
        detuning=30,
        calibration_file=calib_directory + r"\854_rp_calib.csv",
        max_rf_power=10700
    ),
    "850 RP": DDS_Ram(
        port="COM9",
        board=5,
        mode="standalone",
        pulse_sequencer_pin=13,
        detuning=0,
        calibration_file=calib_directory + r"\850_rp_calib.csv",
        max_rf_power=7450
    ),

    "850 SP2": DDS_Ram(
        port="COM10",
        board=1,
        mode="slave",
        pulse_sequencer_pin=12,
        detuning=0,
        calibration_file=calib_directory + r"\850_calib.csv",
        max_rf_power=15000
    ),
    "854 SP2": DDS_Ram(
        port="COM10",
        board=3,
        mode="slave",
        pulse_sequencer_pin=11,
        detuning=0,
        calibration_file=calib_directory + r"\854_calib.csv",
        max_rf_power=15000
    )
}


# Create the ExperimentalSequence object
exp_sequence = Experiment_Builder(dds_dict)

# Create the cooling section (cool for 6 useconds)
exp_sequence.create_cooling_section(length=8, amplitude_dict={"397c": 0.1, "854 SP1": 0.1, "850 SP1": 1})

# Create a Gaussian output function for DDS 397a
def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / (2 * width**2))


# Create op section 
exp_sequence.create_section(name="Optical Pumping", duration=3, dds_functions={
    "397c": lambda t: 0.5,
    "866 OP": lambda t: 0.3,
    "854 SP1": lambda t: 0.2,
}, pmt_gate_high=True)
exp_sequence.create_section(name="Allow Lasers to Switch Off", duration=2, dds_functions={
}, pmt_gate_high=True)
exp_sequence.create_section(name="Pump Out Of Middle States", duration=4, dds_functions={
    "866 OP" : lambda t: 1,
}, pmt_gate_high=True)


# exp_sequence.create_section(name="Single Photon", duration=4, dds_functions={
#     "850 SP1": gaussian(1, 0.6, 2),
# }, pmt_gate_high=False)

# exp_sequence.create_section(name="Pump Out of D5/2", duration=4, dds_functions={
#     "854 SP1": gaussian(1, 0.6, 2),
# }, pmt_gate_high=False)

exp_sequence.build_ram_arrays()

# Plot the amplitude arrays
exp_sequence.plot_amplitude_arrays()
exp_sequence.flash()


# print("starting...")
# control_pulse_sequencer("COM5", 'Start')

# try:
#     while True:
#         time.sleep(1)  # Keep the loop running
# except KeyboardInterrupt:
#     print("stopping...")
#     control_pulse_sequencer("COM5", 'Stop')




exp_runner = Experiment_Runner(
    timeout=100,
    pmt_threshold=1,
)

exp_runner.start_experiment(N=20)

exp_runner.plot_time_diffs_histogram("signal-f",cutoff=28)
# exp_runner.plot_time_diffs_histogram("signal-sp")