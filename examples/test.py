from itcm.ad9910 import *
phase_locked_stack = "COM9"
general_setting_standalone(phase_locked_stack, 0)
for profile in range(7):
    single_tone_profile_setting(phase_locked_stack, 3, profile, Amplitude=1000, Phase_Offset=0, Frequency=200,Verbose=True)