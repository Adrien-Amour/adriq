from adriq.ad9910 import *
from adriq.pulse_sequencer import *
import numpy as np
import time
Pulse_Sequencer = "COM5"
DDS_Boards = "COM9"
Standalone_Board = 6

# Parameters
array_size = 1000
center = 3 * array_size // 4
std_dev = 100

# Generate Gaussian array
x = np.arange(array_size - 3)
gaussian_array = np.exp(-((x - center) ** 2) / (2 * std_dev ** 2))
gaussian_array *= 6000
gaussian_array = np.round(gaussian_array).astype(int)

# Define frequency for 5 complete periods over the range
num_periods = 5
total_range = x[-1] - x[0]
frequency = num_periods / total_range * 2 * np.pi  # Adjust frequency for np.sin and np.cos

# Generate cosine array
cosine_array = 5000 * (np.cos(frequency * x) + 1)
cosine_array = np.round(cosine_array).astype(int)

# Generate square wave array
square_wave_array = np.sign(np.cos(frequency * x)) + 1
square_wave_array = 1500 * np.round(square_wave_array).astype(int) + 1

# Define another array
trig = np.array([5000, 3000])

# Concatenate arrays with trig
gaussian_array = np.concatenate((trig, gaussian_array))
cosine_array = np.concatenate((cosine_array, trig))
square_wave_array = np.concatenate((square_wave_array, trig))

print(type(gaussian_array))
print("General Setting")
general_setting_standalone(DDS_Boards, Standalone_Board)

# print("Writing Ram")
control_pulse_sequencer(Pulse_Sequencer, 'Stop')  # always stop pulse sequencer before a write operation
write_ram(DDS_Boards, Standalone_Board, "Amplitude", gaussian_array, Frequency=20, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=True)
start_ram(DDS_Boards, Standalone_Board)
time.sleep(1)
print("Profile Setting")
ram_profile_setting(DDS_Boards, Standalone_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=0, End_Address=1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Direct Switch')
ram_profile_setting(DDS_Boards, Standalone_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=2, End_Address=1000, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Ramp-Up')

Pulses = ['0100000000000000', '0000000000010000']
Pulse_Lengths = [8, 4]
# # 
control_pulse_sequencer(Pulse_Sequencer, 'Start')  # always stop pulse sequencer before a write operation
