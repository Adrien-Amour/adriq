from adriq.ad9910 import general_setting_master, general_setting_slave, general_setting_standalone, single_tone_profile_setting, interpolate_rf_power
from adriq.pulse_sequencer import control_pulse_sequencer, write_pulse_sequencer
from adriq.experiment import *
import numpy as np
from adriq.WM_SCL import *

dds_dict = load_dds_dict("singletone", r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\dds_config.cfg")
if "397a" in dds_dict:
    print("Removing 397a from dds_dict")
    del dds_dict["397a"]
# Create a Pulse_Sequencer instance
pulse_sequencer = Pulse_Sequencer(port="COM5", ps_end_pin=2, pmt_gate_pin=1, ps_sync_pin=0)

# Create an Experiment_Builder instance
experiment_builder = Experiment_Builder_Singletone(dds_dict, pulse_sequencer, N_Cycles=5E4)

# Set trapping parameters
experiment_builder.set_trapping_parameters(
    trapping_detuning_dict={"397c": -50,
                            "854 SP1": -25,
                            "850 RP": -50},
    trapping_amplitude_dict={"397c": 0.8,
                             "854 SP1": 0.1,
                             "850 RP": 0.7}
)

exp_runner = Experiment_Runner(
    dds_dict,
    pulse_sequencer,
    timeout=100,
    pmt_threshold=2500,
    expected_fluorescence=6500,
    pulse_expected_fluorescence=3000,
    sp_threshold=None,
    load_timeout=50
)

# Create sections
experiment_builder.create_section(
    name="Cool",
    duration=10,
    detunings={"397c": -18,
                "854 SP1": -50,
                "850 RP": -50},
    amplitudes={"397c": 0.1,
                "854 SP1": 0.1,
                "850 RP": 0.7},
    pmt_gate_high=True
)

experiment_builder.create_section(
    name="Probe",
    duration=3,
    detunings={"397c": 18,
                "854 SP1": -50,
                "850 RP": -50},
    amplitudes={"397c": 0.1,
                "854 SP1": 0.1,
                "850 RP": 0.7},
    pmt_gate_high=True
)


experiment_builder.flash()

shift_range = np.linspace(-0.005, 0.005, 10)
exp_runner.measure_expected_fluorescence()
import matplotlib.pyplot as plt
# Initialize lists to store results
red_fluorescence_rates = []
blue_fluorescence_rates = []
shifts = []

# Start with an initial shift of 0
current_shift = 0
step_size = 0.001  # Step size for shifting
found_zero_crossing = False

# Perform the initial measurement at shift = 0
shift_397(current_shift)
exp_runner.start_experiment(N=5)

if exp_runner.N_Valid_Pulses == 0:
    red_fluorescence_rate = 0
    blue_fluorescence_rate = 0
else:
    red_fluorescence_rate = exp_runner.get_counts_in_window("signal-f", lower_cutoff=8, upper_cutoff=10)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
    blue_fluorescence_rate = exp_runner.get_counts_in_window("signal-f", lower_cutoff=11, upper_cutoff=13)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses

# Calculate the initial difference
difference = red_fluorescence_rate - blue_fluorescence_rate
print(f"Initial Shift: {current_shift}, Difference: {difference}")

# Determine the direction of the shift
direction = -1 if difference > 0 else 1  # Negative shift if difference > 0, positive otherwise

# Adjust the shift until the zero crossing is found
while not found_zero_crossing:


    shift_397(direction*step_size)
    current_shift += direction * step_size
    exp_runner.start_experiment(N=10)

    if exp_runner.N_Valid_Pulses == 0:
        red_fluorescence_rate = 0
        blue_fluorescence_rate = 0
    else:
        red_fluorescence_rate = exp_runner.get_counts_in_window("signal-f", lower_cutoff=8, upper_cutoff=10)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
        blue_fluorescence_rate = exp_runner.get_counts_in_window("signal-f", lower_cutoff=11, upper_cutoff=13)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses

    # Calculate the new difference
    new_difference = red_fluorescence_rate - blue_fluorescence_rate
    print(f"Shift: {current_shift}, Difference: {new_difference}")

    # Check if the zero crossing has been found
    if difference * new_difference < 0:  # Sign change indicates zero crossing
        found_zero_crossing = True
        print(f"Zero crossing detected between shifts {current_shift - direction * step_size} and {current_shift}")
        break

    # Update the previous difference
    difference = new_difference

print("escaped the loop")
# Take longer readings at the two points around the zero crossing
shift_397(- direction * step_size) # go back to the previous point 
current_shift -= direction * step_size
print("taking long reading at x1")
exp_runner.start_experiment(N=25)
if exp_runner.N_Valid_Pulses == 0:
    red_fluorescence_rate_1 = 0
    blue_fluorescence_rate_1 = 0
else:
    red_fluorescence_rate_1 = exp_runner.get_counts_in_window("signal-f", lower_cutoff=8, upper_cutoff=10)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
    blue_fluorescence_rate_1 = exp_runner.get_counts_in_window("signal-f", lower_cutoff=11, upper_cutoff=13)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
difference_1 = red_fluorescence_rate_1 - blue_fluorescence_rate_1
x1 = current_shift

shift_397(direction * step_size)
current_shift += direction * step_size

print("taking long reading at x2")
exp_runner.start_experiment(N=25)
if exp_runner.N_Valid_Pulses == 0:
    red_fluorescence_rate_2 = 0
    blue_fluorescence_rate_2 = 0
else:
    red_fluorescence_rate_2 = exp_runner.get_counts_in_window("signal-f", lower_cutoff=7, upper_cutoff=10)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
    blue_fluorescence_rate_2 = exp_runner.get_counts_in_window("signal-f", lower_cutoff=11, upper_cutoff=13)['pmt_counts_chan'] / exp_runner.N_Valid_Pulses
difference_2 = red_fluorescence_rate_2 - blue_fluorescence_rate_2
x2 = current_shift

# Perform linear interpolation to find the zero crossing
zero_shift = x1 - (difference_1 * (x2 - x1) / (difference_2 - difference_1))
print(f"The shift where the difference crosses zero is: {zero_shift}")

# Apply the final shift
shift_397(zero_shift-current_shift)


import matplotlib.pyplot as plt

# Perform linear interpolation to find the zero crossing
zero_shift = x1 - (difference_1 * (x2 - x1) / (difference_2 - difference_1))
print(f"The shift where the difference crosses zero is: {zero_shift}")

# Apply the final shift
shift_397(zero_shift - current_shift)

# Plot the two points and the zero crossing
plt.figure(figsize=(8, 6))

# Plot the two points
plt.scatter([x1, x2], [difference_1, difference_2], color="red", label="Measured Points", zorder=3)

# Plot the interpolated zero crossing
plt.scatter([zero_shift], [0], color="blue", label="Zero Crossing (Interpolated)", zorder=4)

# Add a line connecting the two points
plt.plot([x1, x2], [difference_1, difference_2], color="orange", linestyle="--", label="Linear Interpolation")

# Add labels and legend
plt.axhline(0, color="black", linestyle="--", linewidth=0.8, label="y = 0 (Zero Line)")
plt.xlabel("Shift")
plt.ylabel("Difference (Red - Blue)")
plt.title("Zero Crossing Interpolation")
plt.legend()
plt.grid()

# Show the plot
plt.show()