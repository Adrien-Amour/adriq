from ad9910 import *
from pulse_sequencer import *
import numpy as np
Pulse_Sequencer = "COM5"
DDS_Boards="COM9"
PL_DDS_Boards = "COM10"
Master_Board = 0
Slave_Board = 1
Standalone_Board = 1
# # Parameters
array_size = 1000
center = 3 * array_size // 4
std_dev = 100

# Generate Gaussian array
x = np.arange(array_size-3)
gaussian_array = np.exp(-((x - center) ** 2) / (2 * std_dev ** 2))
gaussian_array *= 3000
gaussian_array = np.round(gaussian_array).astype(int)

# Define frequency for 5 complete periods over the range
num_periods = 5
total_range = x[-1] - x[0]
frequency = num_periods / total_range * 2 * np.pi  # Adjust frequency for np.sin and np.cos

# Generate cosine array
cosine_array = 1500*(np.cos(frequency * x)+1)
cosine_array = np.round(cosine_array).astype(int)


# Generate triangle wave array
square_wave_array = np.sign(np.cos(frequency * x))+1
square_wave_array = (1500*np.round(square_wave_array).astype(int)+1)

# Define another array
trig = np.array([5000,3000])
start = np.array([0]) # Jumps to start address if no dwell high, we want this to be 0
#Gaussian array for PL master board
gaussian_array = np.concatenate((gaussian_array, trig))
cosine_array = np.concatenate((cosine_array, trig))
square_wave_array = np.concatenate((square_wave_array, trig))





print("General Setting")
general_setting_master(PL_DDS_Boards,Master_Board)
general_setting_slave(PL_DDS_Boards,Slave_Board)
general_setting_standalone(DDS_Boards,Standalone_Board)
print("Writing Ram")
write_ram(DDS_Boards, Standalone_Board, 2, gaussian_array, Frequency=200, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=False)
start_ram(DDS_Boards,Standalone_Board)
control_pulse_sequencer(Pulse_Sequencer, 'stop') # always stop pulse sequencer before a write operation
write_ram(PL_DDS_Boards, Slave_Board, 2, square_wave_array, Frequency=200, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=False)
start_ram(PL_DDS_Boards,Slave_Board)
write_ram(PL_DDS_Boards, Master_Board, 2, cosine_array, Frequency=200, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=False)
start_ram(PL_DDS_Boards,Master_Board)
print("Profile Setting")

ram_profile_setting(DDS_Boards, Standalone_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=1, End_Address=array_size-2, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='001')
ram_profile_setting(PL_DDS_Boards, Slave_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=1, End_Address=array_size-2, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='001')
ram_profile_setting(PL_DDS_Boards, Master_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=1, End_Address=array_size-2, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='001')

ram_profile_setting(DDS_Boards, Standalone_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=array_size+1, End_Address=array_size+1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='000')
ram_profile_setting(PL_DDS_Boards, Slave_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=500, End_Address=500, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='000')
ram_profile_setting(PL_DDS_Boards, Master_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=500, End_Address=500, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='000')


Pulses = ['1000000000000000','0000000001111000']
Pulse_Lengths = [8,2]
write_pulse_sequencer(Pulse_Sequencer, Pulses, Pulse_Lengths, Continuous = True, Verbose=True)

control_pulse_sequencer(Pulse_Sequencer, 'start')
time.sleep(100)
control_pulse_sequencer(Pulse_Sequencer, 'stop')
