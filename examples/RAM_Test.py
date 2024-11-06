from adriq.ad9910 import *
from adriq.pulse_sequencer import *
import numpy as np
Pulse_Sequencer = "COM5"
DDS_Boards="COM9"
PL_DDS_Boards = "COM10"
Master_Board = 0
Slave_Board = 1
Standalone_Board = 1
# # Parameters
array_size = 750
center = 3 * array_size // 4
std_dev = 100

# Generate Gaussian array
x = np.arange(array_size-3)
gaussian_array = np.exp(-((x - center) ** 2) / (2 * std_dev ** 2))
gaussian_array *= 6000
gaussian_array = np.round(gaussian_array).astype(int)

# Define frequency for 5 complete periods over the range
num_periods = 5
total_range = x[-1] - x[0]
frequency = num_periods / total_range * 2 * np.pi  # Adjust frequency for np.sin and np.cos

# Generate cosine array
cosine_array = 5000*(np.cos(frequency * x)+1)
cosine_array = np.round(cosine_array).astype(int)


# Generate triangle wave array
square_wave_array = np.sign(np.cos(frequency * x))+1
square_wave_array = (1500*np.round(square_wave_array).astype(int)+1)
print(type(square_wave_array))
# Define another array
trig = np.array([5000,3000])
start = np.array([0]) # Jumps to start address if no dwell high, we want this to be 0
#Gaussian array for PL master board
gaussian_array = np.concatenate((gaussian_array, trig))
cosine_array = np.concatenate((cosine_array, trig))
square_wave_array = np.concatenate((square_wave_array, trig))

gaussian_array = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 7, 8, 10, 11, 12, 14, 15, 17, 19, 21, 24, 26, 30, 33, 37, 41, 45, 50, 55, 61, 67, 74, 82, 90, 99, 109, 120, 131, 144, 157, 172, 187, 204, 222, 242, 263, 285, 309, 334, 362, 391, 421, 454, 489, 526, 565, 606, 650, 696, 744, 795, 849, 905, 963, 1024, 1088, 1155, 1224, 1297, 1371, 1449, 1529, 1612, 1698, 1786, 1876, 1969, 2064, 2162, 2261, 2363, 2466, 2571, 2677, 2785, 2894, 3003, 3114, 3225, 3336, 3447, 3558, 3668, 3778, 3887, 3994, 4099, 4203, 4305, 4404, 4501, 4594, 4684, 4771, 4854, 4933, 5007, 5077, 5142, 5203, 5258, 5308, 5352, 5391, 5424, 5451, 5473, 5488, 5497, 5500, 5497, 5488, 5473, 5451, 5424, 5391, 5352, 5308, 5258, 5203, 5142, 5077, 5007, 4933, 4854, 4771, 4684, 4594, 4501, 4404, 4305, 4203, 4099, 3994, 3887, 3778, 3668, 3558, 3447, 3336, 3225, 3114, 3003, 2894, 2785, 2677, 2571, 2466, 2363, 2261, 2162, 2064, 1969, 1876, 1786, 1698, 1612, 1529, 1449, 1371, 1297, 1224, 1155, 1088, 1024, 963, 905, 849, 795, 744, 696, 650, 606, 565, 526, 489, 454, 421, 391, 362, 334, 309, 285, 263, 242, 222, 204, 187, 172, 157, 144, 131, 120, 109, 99, 90, 82, 74, 67, 61, 55, 50, 45, 41, 37, 33, 30, 26, 24, 21, 19, 17, 15, 14, 12, 11, 10, 8, 7, 7, 6, 5, 5, 4, 4, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 9, 10, 12, 15, 17, 21, 25, 29, 35, 41, 48, 56, 66, 76, 89, 103, 119, 138, 159, 182, 209, 239, 272, 310, 351, 398, 449, 506, 568, 636, 711, 793, 882, 978, 1083, 1195, 1316, 1445, 1583, 1730, 1886, 2051, 2224, 2407, 2597, 2796, 3002, 3216, 3436, 3663, 3894, 4130, 4369, 4610, 4852, 5095, 5336, 5574, 5809, 6039, 6262, 6477, 6682, 6877, 7060, 7230, 7385, 7525, 7648, 7754, 7842, 7911, 7960, 7990, 8000, 7990, 7960, 7911, 7842, 7754, 7648, 7525, 7385, 7230, 7060, 6877, 6682, 6477, 6262, 6039, 5809, 5574, 5336, 5095, 4852, 4610, 4369, 4130, 3894, 3663, 3436, 3216, 3002, 2796, 2597, 2407, 2224, 2051, 1886, 1730, 1583, 1445, 1316, 1195, 1083, 978, 882, 793, 711, 636, 568, 506, 449, 398, 351, 310, 272, 239, 209, 182, 159, 138, 119, 103, 89, 76, 66, 56, 48, 41, 35, 29, 25, 21, 17, 15, 12, 10, 9, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

print(type(gaussian_array))
print("General Setting")
general_setting_master(PL_DDS_Boards,Master_Board)
general_setting_slave(PL_DDS_Boards,Slave_Board)
print("Writing Ram")
control_pulse_sequencer(Pulse_Sequencer, 'Stop') # always stop pulse sequencer before a write operation
write_ram(PL_DDS_Boards, Slave_Board, "Amplitude", gaussian_array, Frequency=20, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=True)
start_ram(PL_DDS_Boards,Slave_Board)
write_ram(PL_DDS_Boards, Master_Board, "Amplitude", cosine_array, Frequency=20, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=True)
start_ram(PL_DDS_Boards,Master_Board)
print("Profile Setting")


ram_profile_setting(PL_DDS_Boards, Slave_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=5, Start_Address=0, End_Address=1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Direct Switch')
ram_profile_setting(PL_DDS_Boards, Master_Board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=5, Start_Address=0, End_Address=1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Direct Switch')
ram_profile_setting(PL_DDS_Boards, Slave_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=5, Start_Address=2, End_Address=array_size-2, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Ramp-Up')
ram_profile_setting(PL_DDS_Boards, Master_Board, 1,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=5, Start_Address=2, End_Address=array_size-2, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Ramp-Up')


Pulses = ['1000000000000000','0000000001111000']
Pulse_Lengths = [4,15]
write_pulse_sequencer(Pulse_Sequencer, Pulses, Pulse_Lengths, Continuous = True, Verbose=True)

control_pulse_sequencer(Pulse_Sequencer, 'Start')
time.sleep(100)
control_pulse_sequencer(Pulse_Sequencer, 'Stop')
