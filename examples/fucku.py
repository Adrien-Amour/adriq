from adriq.ad9910 import *
from adriq.pulse_sequencer import * 
import time
port = "COM9"
master_board = 0
slave_board = 2
control_pulse_sequencer("COM5", 'Stop')
general_setting_master(port, master_board)
general_setting_standalone(port, slave_board)
time.sleep(0)
# single_tone_profile_setting(port, master_board, 0, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)
single_tone_profile_setting(port, slave_board, 0, PLL_Multiplier=40, Amplitude=5000, Phase_Offset=0, Frequency=20, Verbose=True)
# port = "COM9"
# board = 6
# # general_setting_standalone(port, board)
# single_tone_profile_setting(port, board, 0, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)