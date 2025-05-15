# Standard library imports
import json
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.filedialog import asksaveasfilename, askopenfilename
# Third-party imports
import matplotlib.pyplot as plt
import numpy as np
import serial
import configparser
# Local application/library-specific imports
from .Custom_Tkinter import CustomSpinbox

def cfr1_bytes(
    RAM_Enable=False, RAM_Mode='00', Inverse_Sinc_Filter_Enable=False, Internal_Profile='0000', Sin=False,
    Manual_OSK_External_Control=False,
    Autoclear_Digital_Ramp_Accumulator=False, Autoclear_Phase_Accumulator=False,
    Clear_Digital_Ramp_Accumulator=False, Clear_Phase_Accumulator=False,
    Load_LRR_At_IO_Update=False, Load_ARR_At_IO_Update=False, OSK_Enable=False,
    REF_CLK_Input_Power_Down=False, DAC_Power_Down=False, Select_Auto_OSK = False, Digital_Power_Down=False,
    Aux_DAC_Power_Down = False, External_Power_Down_Control=False, SDIO_Input_Only=True):

    bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0

    # Setting bits based on the input parameters
    bits[31] = 1 if RAM_Enable else 0
    bits[30], bits[29] = int(RAM_Mode[1]), int(RAM_Mode[0])
    bits[23] = 1 if Manual_OSK_External_Control else 0
    bits[22] = 1 if Inverse_Sinc_Filter_Enable else 0
    bits[21] = 0 #open
    bits[17:21] = [int(Internal_Profile[3-i]) for i in range(4)]  # Bits 20-17: Internal Profile (reversed order because of numbering conventions)
    bits[16] = 1 if Sin else 0
    bits[15] = 1 if Load_LRR_At_IO_Update else 0
    bits[14] = 1 if Autoclear_Digital_Ramp_Accumulator else 0
    bits[13] = 1 if Autoclear_Phase_Accumulator else 0
    bits[12] = 1 if Clear_Digital_Ramp_Accumulator else 0
    bits[11] = 1 if Clear_Phase_Accumulator else 0
    bits[10] = 1 if Load_ARR_At_IO_Update else 0
    bits[9] = 1 if OSK_Enable else 0
    bits[8] = 1 if Select_Auto_OSK else 0
    bits[7] = 1 if Digital_Power_Down else 0
    bits[6] = 1 if DAC_Power_Down else 0
    bits[5] = 1 if REF_CLK_Input_Power_Down else 0
    bits[4] = 1 if Aux_DAC_Power_Down else 0
    bits[3] = 1 if External_Power_Down_Control else 0
    bits[2] = 0 #OPEN
    bits[1] = 1 if SDIO_Input_Only else 0
    bits[0] = 0 #always LSB last
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    # Convert the bits list to a single string of bits
    bitstring = ''.join(map(str, bitstring))
        

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)

    return [byte1, byte2, byte3, byte4]

def cfr2_bytes(
    Enable_Amplitude_Scale=False, Internal_IO_Update_Active=False, SYNC_CLK_Enable=False,
    Digital_Ramp_Destination='00', Digital_Ramp_Enable=False, Digital_Ramp_No_Dw_High=False,
    Digital_Ramp_No_Dw_Low=False, Read_Effective_FTW=False, IO_Update_Rate_Control='00',
    PDCLK_Enable=False, PDCLK_Invert=False, Tx_Enable_Invert=False, Matched_Latency_Enable=False,
    Data_Assembler_Hold_Last_Value=False, Sync_Timing_Validation_Disable=False, Parallel_Data_Port_Enable=False, FM_Gain='0000'):

    bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0

    # Setting bits based on the input parameters
    bits[25:32] = [0] * 7  # Open bits always 0
    bits[24] = 1 if Enable_Amplitude_Scale else 0  # Bit 24: Enable amplitude scale
    bits[23] = 1 if Internal_IO_Update_Active else 0  # Bit 23: Internal I/O update active
    bits[22] = 1 if SYNC_CLK_Enable else 0  # Bit 22: SYNC_CLK enable
    bits[20:22] = [int(Digital_Ramp_Destination[1-i]) for i in range(2)]  # Bits 21-20: Digital ramp destination
    bits[19] = 1 if Digital_Ramp_Enable else 0  # Bit 19: Digital ramp enable
    bits[18] = 1 if Digital_Ramp_No_Dw_High else 0  # Bit 18: Digital ramp no-dwell high
    bits[17] = 1 if Digital_Ramp_No_Dw_Low else 0  # Bit 17: Digital ramp no-dwell low
    bits[16] = 1 if Read_Effective_FTW else 0  # Bit 16: Read effective FTW
    bits[14:16] = [int(IO_Update_Rate_Control[1-i]) for i in range(2)]  # Bits 15-14: I/O update rate control
    bits[13], bits[12] = 0, 0  # Open bits always 0
    bits[11] = 1 if PDCLK_Enable else 0  # Bit 11: PDCLK enable
    bits[10] = 1 if PDCLK_Invert else 0  # Bit 10: PDCLK invert
    bits[9] = 1 if Tx_Enable_Invert else 0  # Bit 9: TxEnable invert
    bits[8] = 0  # Open bits always 0
    bits[7] = 1 if Matched_Latency_Enable else 0  # Bit 7: Matched latency enable
    bits[6] = 1 if Data_Assembler_Hold_Last_Value else 0  # Bit 6: Data assembler hold last value
    bits[5] = 1 if Sync_Timing_Validation_Disable else 0  # Bit 5: Sync timing validation disable
    bits[4] = 1 if Parallel_Data_Port_Enable else 0  # Bit 4: Parallel data Port enable
    bits[0:4] = [int(FM_Gain[3-i]) for i in range(4)]  # Bits 3-0: FM gain
    
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    # Convert the bits list to a single string of bits
    bitstring = ''.join(map(str, bitstring))
        

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)

    return [byte1, byte2, byte3, byte4]

def cfr3_bytes(
    DRV0='01', VCO_SEL='111', Icp='111', REFCLK_Input_Divider_Bypass=False,
    REFCLK_Input_Divider_ResetB=False, PFD_Reset=False, PLL_Enable=False, PLL_Multiplier=40):

    bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0

    # Convert N to a 7-bit binary string
    PLL_Multiplier_Bin = format(PLL_Multiplier, '07b')
    # PLL_Multiplier_Bin = PLL_Multiplier_Bin[::-1]
    # Setting bits based on the input parameters
    bits[30:32] = [0] * 2  # Bits 31-30: Open (set to 0)
    bits[28:30] = [int(DRV0[1]), int(DRV0[0])]  # Bits 29-28: DRV0 Because strings and bit strings have different numbering conventions i have had to
    bits[27] = 0  # Bit 27: Open (set to 0)
    bits[24:27] = [int(VCO_SEL[2-i]) for i in range(3)]  # Bits 26-24: VCO_SEL Because strings and bit strings have different numbering conventions i have had to
    bits[23], bits[22] = 0,0  # Bit 23,24: Open (set to 0)
    bits[19:22] = [int(Icp[2-i]) for i in range(3)]  # Bits 22-19: Icp Because strings and bit strings have different numbering conventions i have had to

    bits[16:19] = [0,0,0]  # Bit 16-18: Open (set to 0)
    bits[15] = 1 if REFCLK_Input_Divider_Bypass else 0  # Bit 15: REFCLK input divider bypass
    bits[14] = 1 if REFCLK_Input_Divider_ResetB else 0  # Bit 14: REFCLK input divider resetB
    bits[11:14] = [0, 0,0]  # Bits 12-11: Open (set to 0)
    bits[10] = 1 if PFD_Reset else 0  # Bit 10: PFD reset
    bits[9] = 0  # Bit 9: Open (set to 0)
    bits[8] = 1 if PLL_Enable else 0  # Bit 9: PLL enable
    bits[1:8] = [int(PLL_Multiplier_Bin[6-i]) for i in range(7)]  # Bits 7-1: phase locked loop. Because strings and bit strings have different numbering conventions i have had to
    bits[0] = 0  # Bit 0: Open (set to 0)
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    # Convert the bits list to a single string of bits

    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)
    return [byte1, byte2, byte3, byte4]

def multichip_sync_Register_bytes(
    Sync_Validation_Delay=0, Sync_Receiver_Enable=False, Sync_Generator_Enable=False,
    Sync_Generator_Polarity=False, Sync_State_Preset_Value=0,
    Output_Sync_Generator_Delay=0, Input_Sync_Receiver_Delay=0):

    # Initialize a 32-bit list with all bits set to 0
    bits = [0] * 32

    # Convert integer inputs to binary strings and pad them
    Sync_Validation_Delay_Bin = format(int(Sync_Validation_Delay), '04b')
    Sync_State_Preset_Value_Bin = format(int(Sync_State_Preset_Value), '06b')
    Output_Sync_Generator_Delay_Bin = format(int(Output_Sync_Generator_Delay), '05b')
    Input_Sync_Receiver_Delay_Bin = format(int(Input_Sync_Receiver_Delay), '05b')

    # Setting bits based on the input parameters
    # Bits 31-28: Sync Validation Delay
    bits[28:32] = [int(Sync_Validation_Delay_Bin[3-i]) for i in range(4)]
    
    # Bit 27: Sync Receiver Enable
    bits[27] = 1 if Sync_Receiver_Enable else 0
    
    # Bit 26: Sync Generator Enable
    bits[26] = 1 if Sync_Generator_Enable else 0
    
    # Bit 25: Sync Generator Polarity
    bits[25] = 1 if Sync_Generator_Polarity else 0
    
    # Bit 24: Open
    bits[24] = 0
    
    # Bits 23-18: Sync State Preset Value
    bits[18:24] = [int(Sync_State_Preset_Value_Bin[5-i]) for i in range(6)]
    
    # Bits 17-16: Open
    bits[16:18] = [0, 0]
    
    # Bits 15-11: Output Sync Generator Delay
    bits[11:16] = [int(Output_Sync_Generator_Delay_Bin[4-i]) for i in range(5)]
    
    # Bits 10-8: Open
    bits[8:11] = [0, 0, 0]
    
    # Bits 7-3: Input Sync Receiver Delay
    bits[3:8] = [int(Input_Sync_Receiver_Delay_Bin[4-i]) for i in range(5)]
    
    # Bits 2-0: Open
    bits[0:3] = [0, 0, 0]
    # Convert the bits list to a single string of bits
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    bitstring = ''.join(map(str, bitstring))
    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)

    return [byte1, byte2, byte3, byte4]

def auxiliary_dac_bytes(Code):
    bits = [0] * 32
    Code_Bin = format(Code, '08b')
    bits[30:32] = [0] * 2  # Bits 31-30: Open (set to 0)
    bits[0:8] = [int(Code_Bin[7-i]) for i in range(8)]
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    # Convert the bits list to a single string of bits
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)

    return [byte1, byte2, byte3, byte4]

def asf_bytes(PLL_Multiplier=40, Amplitude_Step_Size='00', Amplitude=0, Amplitude_Ramp_Rate_Divider=1):
    Amplitude_Ramp_Rate_Divider_Bin = format(Amplitude_Ramp_Rate_Divider, '016b') # step size in seconds
    Frequency_Sys_CLK = PLL_Multiplier * 25E6
    Amplitude_Bin = format(Amplitude, '014b')  # Assuming Amplitude is within the range that fits in 14 bits
    bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0
    bits[16:32] = [int(Amplitude_Ramp_Rate_Divider_Bin[15-i]) for i in range(16)] # Amplitude scale factor
    bits[2:16] = [int(Amplitude_Bin[13-i]) for i in range(14)] #Phase offset word
    bits[0:2] = [int(Amplitude_Step_Size[1-i]) for i in range(2)]  # Frequency tuning word

    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)
    Temporal_Step_Size = (4 / Frequency_Sys_CLK) * Amplitude_Ramp_Rate_Divider
    return [byte1, byte2, byte3, byte4], Temporal_Step_Size

def ftw_bytes(PLL_Multiplier=40, Frequency=200):
    import numpy as np
    Frequency_Sys_CLK = PLL_Multiplier * 25E6 
    FTW = round((2**32 * Frequency *1E6) / Frequency_Sys_CLK)  #working in MHz
    FTW_bin = format(FTW, '032b')             # 32-bit binary representation of FTW
    bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0

    # Convert N to a 7-bit binary string
    # Setting bits based on the input parameters
    bits[0:32] = [int(FTW_bin[31-i]) for i in range(32)]  # Frequency tuning word
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)

    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)

    true_frequency = (Frequency_Sys_CLK * FTW / 2**32) * 1E6 #working in MHz

    return [byte1, byte2, byte3, byte4], true_frequency

def pow_bytes(Phase_Offset=0):
    import numpy as np
    POW = round((2**16 * Phase_Offset) / (2 * np.pi))
    POW_Bin = format(POW, '016b')         # Assuming Phase is within the range that fits in 16 bits
    bits = [0] * 16  # Initialize a 32-bit list with all bits set to 0

    # Setting bits based on the input parameters
    bits[0:16] = [int(POW_Bin[15-i]) for i in range(16)]  # Frequency tuning word
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)

    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)

    true_phase_offset = 2 * np.pi * POW / 2**16

    return [byte1, byte2], true_phase_offset

def single_tone_profile_bytes(
    PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=200):
    import numpy as np
    Frequency_Sys_CLK = PLL_Multiplier * 25E6
    POW = round((2**16 * Phase_Offset) / (2 * np.pi))
    FTW = round((2**32 * Frequency *1E6) / Frequency_Sys_CLK)
    Amplitude_Bin = format(Amplitude, '014b')  # Assuming Amplitude is within the range that fits in 14 bits
    POW_Bin = format(POW, '016b')         # Assuming Phase is within the range that fits in 16 bits
    FTW_bin = format(FTW, '032b')             # 32-bit binary representation of FTW
    bits = [0] * 64  # Initialize a 32-bit list with all bits set to 0

    # Setting bits based on the input parameters
    bits[62:64] = [0] * 2  # Bits 62-64 are open so 0
    bits[48:62] = [int(Amplitude_Bin[13-i]) for i in range(14)] # Amplitude scale factor
    bits[32:48] = [int(POW_Bin[15-i]) for i in range(16)] #Phase offset word
    bits[0:32] = [int(FTW_bin[31-i]) for i in range(32)]  # Frequency tuning word
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)

    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)
    byte5 = int(bitstring[32:40], 2)
    byte6 = int(bitstring[40:48], 2)
    byte7 = int(bitstring[48:56], 2)
    byte8 = int(bitstring[56:64], 2)

    true_frequency = (Frequency_Sys_CLK * FTW / 2**32) * 1E6 #working in MHz
    true_phase_offset = 2 * np.pi * POW / 2**16
    
    return [byte1, byte2, byte3, byte4, byte5, byte6, byte7, byte8], true_frequency, true_phase_offset

def ram_profile_bytes(
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=0, End_Address=1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode="Direct Switch"):
    Frequency_Sys_CLK = PLL_Multiplier * 25E6
    Amplitude_Ramp_Rate_Divider_Bin = format(Amplitude_Ramp_Rate_Divider, '016b') # step size in seconds
    End_Address_Bin = format(End_Address, '010b')
    Start_Address_Bin = format(Start_Address, '010b')
    
    # Dictionary mapping mode names to control bits
    mode_control_bits = {
        "Direct Switch": "000",
        "Ramp-Up": "001",
        "Bidirectional Ramp": "010",
        "Continuous Bidirectional ramp": "011",
        "Continuous Recirculate": "100"
    }

    # Check if the provided Profile_Mode is valid
    if Profile_Mode not in mode_control_bits:
        raise ValueError(f"Invalid Profile_Mode '{Profile_Mode}'. Must be one of {list(mode_control_bits.keys())}.")
    # Get the control bits for the selected mode
    control_bits = mode_control_bits[Profile_Mode]

    bits = [0] * 64  # Initialize a 32-bit list with all bits set to 0

    # Setting bits based on the input parameters
    bits[56:64] = [0] * 8  # Bits 56-63 are open so 0
    bits[40:56] = [int(Amplitude_Ramp_Rate_Divider_Bin[15-i]) for i in range(16)]
    bits[30:40] = [int(End_Address_Bin[9-i]) for i in range(10)] # Amplitude scale factor
    bits[24:30] = [0] * 6  # Bits 24-29 are open so 0
    bits[14:24] = [int(Start_Address_Bin[9-i]) for i in range(10)] # Amplitude scale factor
    bits[6:14] = [0]*8
    bits[5] = 0 if No_Dwell_High else 1 #admittedly, i am confused by this. The datasheet says that the bit should be 0 for no dwell high, but the bit should be 1 for no dwell high, but the behaviour is the opposite
    bits[4] = 0 #open
    bits[3] = 1 if Zero_Crossing else 0
    bits[0:3] = [int(control_bits[2 - i]) for i in range(3)]
    bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)

    bitstring = ''.join(map(str, bitstring))

    # Convert the bits to four bytes
    byte1 = int(bitstring[0:8], 2)
    byte2 = int(bitstring[8:16], 2)
    byte3 = int(bitstring[16:24], 2)
    byte4 = int(bitstring[24:32], 2)
    byte5 = int(bitstring[32:40], 2)
    byte6 = int(bitstring[40:48], 2)
    byte7 = int(bitstring[48:56], 2)
    byte8 = int(bitstring[56:64], 2)
    Temporal_Step_Size = (4 / Frequency_Sys_CLK) * Amplitude_Ramp_Rate_Divider

    return [byte1, byte2, byte3, byte4, byte5, byte6, byte7, byte8], Temporal_Step_Size


def ram_word_bytes(Array, Mode="Amplitude", PLL_Multiplier=40):
    #function to obtain RAM control words for all modulation modes modulation from input array containing desired frequencies
    Array = np.round(Array).astype(int)#intify
    Array = Array[::-1] #reverse array, it will be reverse again upon writing to the DDS
    ram_bytes = []

    
    # Dictionary to map mode names to integer codes
    mode_codes = {
        "Frequency": 0,
        "Phase": 1,
        "Amplitude": 2
    }

    # Validate Mode input
    if Mode not in mode_codes:
        raise ValueError(f"Invalid Mode '{Mode}'. Must be one of {list(mode_codes.keys())}.")

    # Get the integer code for the provided Mode
    Mode_Code = mode_codes[Mode]

    if Mode_Code == 0:
        for frequency in Array:
            element_bytes, _ = ftw_bytes(PLL_Multiplier=PLL_Multiplier, Frequency=frequency)
            ram_bytes.extend(element_bytes)
    if Mode_Code == 1:
        for phase_offset in Array:
            element_bytes, _ = pow_bytes(Phase_Offset=phase_offset)
            element_bytes.extend([0,0])
            ram_bytes.extend(element_bytes)
    if Mode_Code == 2:
        for amplitude in Array:
            bits = [0] * 32  # Initialize a 32-bit list with all bits set to 0
            amplitude_bin = format(amplitude, '014b')  # Assuming Amplitude is within the range that fits in 14 bits
            bits[16:32] = [int(amplitude_bin[13-i]) for i in range(14)] #Phase offset word
            bitstring = bits[::-1] # reverse the inputs to get the desired bitstring (bit ordering convention is the opposite to string ordering)
            bitstring = ''.join(map(str, bitstring))
            byte1 = int(bitstring[0:8], 2)
            byte2 = int(bitstring[8:16], 2)
            byte3 = int(bitstring[16:24], 2)
            byte4 = int(bitstring[24:32], 2)
            ram_bytes.extend([byte1,byte2,byte3,byte4]) 
    return ram_bytes   

def send_byte_array_to_pic(Port, byte_array, Verbose):
    max_retries = 3  # Number of retries
    for attempt in range(max_retries):
        try:
            ser = serial.Serial(Port, 9600, timeout=1)  # Adjust the port and baud rate as necessary
            try:
                ser.write(byte_array)
                time.sleep(0.001)  # Adjust the sleep time if necessary
                if Verbose:
                    print("Sent=")
                    for i in range(len(byte_array)):
                        print(byte_array[i], end=',')
                    # Read the response (assuming the response is within 64 bytes)
                    response = ser.read(64)  # Adjust the number of bytes to read if necessary
                    print("\nResponse:", response)
                return  # Exit the function if successful
            finally:
                ser.close()
                time.sleep(0.001)
        except serial.SerialException as e:
            print(f"Serial communication error (attempt {attempt + 1}/{max_retries}): {e}")
        except Exception as e:
            print(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
        
        # Retry logic
        if attempt < max_retries - 1:
            print("Retrying...")
            time.sleep(0.5)  # Wait before retrying
        else:
            print("Failed after 3 attempts.")

def write_to_ad9910(Port, Register, Board, Write_Bytes, Verbose=False):
    Register_dict = {
        'CFR1': 0x00,
        'CFR2': 0x01,
        'CFR3': 0x02,
        'MCSR': 0x0A, # Multichip Sync
        'AD': 0x03, # Auxiliary DAC
        'P0': 0x0E, # these are all the same for firmware reasons, hopefully can be changed
        'P1': 0x0E,
        'P2': 0x0E,
        'P3': 0x0E,
        'P4': 0x0E,
        'P5': 0x0E,
        'P6': 0x0E,
        'P7': 0x0E,
        'RAM': 0x16,
        'FTW': 0x07,
        'ASF': 0x09,
        'POW': 0x08,
        # Add other registers as needed
    }

    if Register != 'RAM':
        instruction_byte = 0b00000000 | Register_dict.get(Register, 0x00)  # Always in write mode, so first bit is always 0
        Board_byte = Board & 0x07  # Ensure the board number is within the range 0-7
        if len(Write_Bytes) > 61:
            raise ValueError("Write_Bytes cannot be longer than 61 bytes")
        byte_array = bytearray([ord('w'), Board_byte, instruction_byte] + Write_Bytes + [0] * (64 - 3 - len(Write_Bytes)))
        send_byte_array_to_pic(Port, byte_array, Verbose)
    else:
        Packages = [Write_Bytes[i:i + 60] for i in range(0, len(Write_Bytes), 60)]
        Board_byte = Board & 0x07  # Ensure the board number is within the range 0-7
        for i, package in enumerate(Packages):
            byte_array = bytearray([ord('a'), Board_byte, 0, i] + package + [0] * (64 - 4 - len(package)))
            send_byte_array_to_pic(Port, byte_array, Verbose)

def general_setting_standalone(Port, Board):
    cfr1_wbytes = cfr1_bytes(
        RAM_Enable=False, RAM_Mode='00', Inverse_Sinc_Filter_Enable=True, Internal_Profile='0000', Sin=False,
        Manual_OSK_External_Control=False,
        Autoclear_Digital_Ramp_Accumulator=False, Autoclear_Phase_Accumulator=False,
        Clear_Digital_Ramp_Accumulator=False, Clear_Phase_Accumulator=False,
        Load_LRR_At_IO_Update=False, Load_ARR_At_IO_Update=False, OSK_Enable=False,
        REF_CLK_Input_Power_Down=False, DAC_Power_Down=False, Digital_Power_Down=False,
        External_Power_Down_Control=False, SDIO_Input_Only=True)
    write_to_ad9910(Port, 'CFR1', Board, cfr1_wbytes)
    cfr2_wbytes = cfr2_bytes(
        Enable_Amplitude_Scale=True, Internal_IO_Update_Active=False, SYNC_CLK_Enable=False,
        Digital_Ramp_Destination='00', Digital_Ramp_Enable=False, Digital_Ramp_No_Dw_High=False,
        Digital_Ramp_No_Dw_Low=False, Read_Effective_FTW=False, IO_Update_Rate_Control='00',
        PDCLK_Enable=True, PDCLK_Invert=False, Tx_Enable_Invert=False, Matched_Latency_Enable=False,
        Data_Assembler_Hold_Last_Value=False, Sync_Timing_Validation_Disable=True, Parallel_Data_Port_Enable=False, FM_Gain='0000')
    write_to_ad9910(Port, 'CFR2', Board, cfr2_wbytes)

    cfr3_wbytes = cfr3_bytes(
        DRV0='01', VCO_SEL='101', Icp='111', REFCLK_Input_Divider_Bypass=False,
        REFCLK_Input_Divider_ResetB=True, PFD_Reset=False, PLL_Enable=True, PLL_Multiplier=40) #Master General Settings

    write_to_ad9910(Port, 'CFR3', Board, cfr3_wbytes)

    ad_wbytes = auxiliary_dac_bytes(2*127)
    write_to_ad9910(Port, 'AD', Board, ad_wbytes)

def general_setting_master(Port, Board):
    # This function writes the general settings of the master Board based on Matthias' VI settings.
    # The differences between master and slave settings are as follows:
    # 1. Inverse_Sinc_Filter_Enable:
    #    - Master: False
    #    - Slave: True
    # 2. SYNC_CLK_Enable:
    #    - Master: False
    #    - Slave: True
    # 3. PDCLK_Enable:
    #    - Master: True
    #    - Slave: False
    # 4. Sync_Timing_Validation_Disable:
    #    - Master: True
    #    - Slave: False
    # 5. DRV0:
    #    - Master: '10'
    #    - Slave: '00'
    # 6. Sync_Receiver_Enable:
    #    - Master: False
    #    - Slave: True
    # 7. Sync_Generator_Enable:
    #    - Master: True
    #    - Slave: False

    cfr1_wbytes = cfr1_bytes(
    RAM_Enable=False, RAM_Mode='00', Inverse_Sinc_Filter_Enable=True, Internal_Profile='0000', Sin=False,
    Manual_OSK_External_Control=False,
    Autoclear_Digital_Ramp_Accumulator=False, Autoclear_Phase_Accumulator=False,
    Clear_Digital_Ramp_Accumulator=False, Clear_Phase_Accumulator=False,
    Load_LRR_At_IO_Update=False, Load_ARR_At_IO_Update=False, OSK_Enable=False,
    REF_CLK_Input_Power_Down=False, DAC_Power_Down=False, Digital_Power_Down=False,
    External_Power_Down_Control=False, SDIO_Input_Only=True)
    write_to_ad9910(Port, 'CFR1', Board, cfr1_wbytes)


    cfr2_wbytes = cfr2_bytes(
    Enable_Amplitude_Scale=True, Internal_IO_Update_Active=False, SYNC_CLK_Enable=False,
    Digital_Ramp_Destination='00', Digital_Ramp_Enable=False, Digital_Ramp_No_Dw_High=False,
    Digital_Ramp_No_Dw_Low=False, Read_Effective_FTW=False, IO_Update_Rate_Control='00',
    PDCLK_Enable=True, PDCLK_Invert=False, Tx_Enable_Invert=False, Matched_Latency_Enable=False,
    Data_Assembler_Hold_Last_Value=False, Sync_Timing_Validation_Disable=True, Parallel_Data_Port_Enable=False, FM_Gain='0000')
    write_to_ad9910(Port, 'CFR2', Board, cfr2_wbytes)

    cfr3_wbytes = cfr3_bytes(
    DRV0='10', VCO_SEL='101', Icp='111', REFCLK_Input_Divider_Bypass=False,
    REFCLK_Input_Divider_ResetB=True, PFD_Reset=False, PLL_Enable=True, PLL_Multiplier=40) #Master General Settings

    write_to_ad9910(Port, 'CFR3', Board, cfr3_wbytes)

    mcsr_wbytes = multichip_sync_Register_bytes(
    Sync_Validation_Delay=1, Sync_Receiver_Enable=False, Sync_Generator_Enable=True,
    Sync_Generator_Polarity=False, Sync_State_Preset_Value=7,
    Output_Sync_Generator_Delay=8, Input_Sync_Receiver_Delay=10)
    write_to_ad9910(Port, 'MCSR', Board, mcsr_wbytes)
    ad_wbytes = auxiliary_dac_bytes(2*127)
    write_to_ad9910(Port, 'AD', Board, ad_wbytes)

def general_setting_slave(Port, Board):

    cfr1_wbytes = cfr1_bytes(
        RAM_Enable=False, RAM_Mode='00', Inverse_Sinc_Filter_Enable=True, Internal_Profile='0000', Sin=False,
        Manual_OSK_External_Control=False,
        Autoclear_Digital_Ramp_Accumulator=False, Autoclear_Phase_Accumulator=False,
        Clear_Digital_Ramp_Accumulator=False, Clear_Phase_Accumulator=False,
        Load_LRR_At_IO_Update=False, Load_ARR_At_IO_Update=False, OSK_Enable=False,
        REF_CLK_Input_Power_Down=False, DAC_Power_Down=False, Digital_Power_Down=False,
        External_Power_Down_Control=False, SDIO_Input_Only=True)
    write_to_ad9910(Port, 'CFR1', Board, cfr1_wbytes)
    cfr2_wbytes = cfr2_bytes(
        Enable_Amplitude_Scale=True, Internal_IO_Update_Active=False, SYNC_CLK_Enable=True,
        Digital_Ramp_Destination='00', Digital_Ramp_Enable=False, Digital_Ramp_No_Dw_High=False,
        Digital_Ramp_No_Dw_Low=False, Read_Effective_FTW=False, IO_Update_Rate_Control='00',
        PDCLK_Enable=False, PDCLK_Invert=False, Tx_Enable_Invert=False, Matched_Latency_Enable=False,
        Data_Assembler_Hold_Last_Value=False, Sync_Timing_Validation_Disable=False, Parallel_Data_Port_Enable=False, FM_Gain='0000')
    write_to_ad9910(Port, 'CFR2', Board, cfr2_wbytes)

    cfr3_wbytes = cfr3_bytes(
        DRV0='00', VCO_SEL='101', Icp='111', REFCLK_Input_Divider_Bypass=False,
        REFCLK_Input_Divider_ResetB=True, PFD_Reset=False, PLL_Enable=True, PLL_Multiplier=40) #Master General Settings

    write_to_ad9910(Port, 'CFR3', Board, cfr3_wbytes)

    mcsr_wbytes = multichip_sync_Register_bytes(
        Sync_Validation_Delay=1, Sync_Receiver_Enable=True, Sync_Generator_Enable=False,
        Sync_Generator_Polarity=False, Sync_State_Preset_Value=7,
        Output_Sync_Generator_Delay=8, Input_Sync_Receiver_Delay=10)
    write_to_ad9910(Port, 'MCSR', Board, mcsr_wbytes)

    ad_wbytes = auxiliary_dac_bytes(2*127)
    write_to_ad9910(Port, 'AD', Board, ad_wbytes)

def single_tone_profile_setting(Port, Board, Profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=200, Verbose = False):
    # Check if Profile is an integer and within the range [0, 7]
    if isinstance(Profile, int) and 0 <= Profile <= 7:
        Profile_Register = "P" + str(Profile)
        Profile_Bytes, _, _ = single_tone_profile_bytes(PLL_Multiplier=PLL_Multiplier, Amplitude=Amplitude, Phase_Offset=Phase_Offset, Frequency=Frequency)
        Profile_Bytes = [Profile]+Profile_Bytes # Matthias' Firmware neglects the profile register and assigns a vale given by the next byte, so we set this here
        # Add the byte of Board to the front of the array
        write_to_ad9910(Port, Profile_Register, Board, Profile_Bytes, Verbose=Verbose)

    else:
        raise ValueError("Profile must be an integer between 0 and 7")

def set_ram_frequency(Port, Board, Frequency, Verbose=False):
    PLL_Multiplier = 40
    FTW_Bytes, _ = ftw_bytes(PLL_Multiplier=PLL_Multiplier, Frequency=Frequency)
    write_to_ad9910(Port, 'FTW', Board, FTW_Bytes, Verbose=Verbose)

def set_ram_phase(Port, Board, Phase, Verbose=False):
    POW_Bytes, _ = pow_bytes(Phase)
    write_to_ad9910(Port, 'POW', Board, POW_Bytes, Verbose=Verbose)

def set_ram_amplitude(Port, Board, Amplitude, Verbose=False):
    PLL_Multiplier = 40
    ASF_Bytes, _ = asf_bytes(PLL_Multiplier=PLL_Multiplier, Amplitude=Amplitude, Amplitude_Ramp_Rate_Divider=0)
    write_to_ad9910(Port, 'ASF', Board, ASF_Bytes, Verbose=Verbose)

def write_ram(Port, Board, Mode, Array, Frequency=None, Amplitude=None, Phase=None, PLL_Multiplier=40, Show_RAM=False, Verbose=False):
    # # Print all arguments except Array on one line
    # print(f"Port: {Port}, Board: {Board}, Mode: {Mode}, Frequency: {Frequency}, Amplitude: {Amplitude}, Phase: {Phase}, PLL_Multiplier: {PLL_Multiplier}, Show_RAM: {Show_RAM}, Verbose: {Verbose}")
    
    # # Print the Array on the next line
    # print("Array:", Array)
    length = len(Array)
    if length > 1020:
        raise ValueError(f"Ram is maximum of 1020 words long. Provided array is {length} long. Ram write operation aborted.")
    Array = np.round(Array).astype(int)
    if Show_RAM:
        x_values = [i  for i in range(len(Array))]
        plt.plot(x_values, Array)
        plt.title('Pulse Shape')
        plt.xlabel('Word Number')
        if Mode == 0:
            plt.ylabel('Frequency')
        if Mode == 1:
            plt.ylabel('Phase')
        if Mode == 2:
            plt.ylabel('Amplitude')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.show()
        # Validate input lengths and value
    if Frequency is not None:
        set_ram_frequency(Port, Board, Frequency, Verbose=Verbose)
    if Phase is not None:
        set_ram_phase(Port, Board, Phase, Verbose=Verbose)
    if Amplitude is not None:
        set_ram_amplitude(Port, Board, Amplitude, Verbose=Verbose)
        byte1 = (length >> 8) & 0xFF  # Most significant byte
        byte2 = length & 0xFF         # Least significant byte
    
    for profile in range(8):
            Board_byte = Board & 0x07  # Ensure the board number is within the range 0-7
            byte_array = bytearray([ord('p'), Board_byte, profile] + [byte1, byte2, 2, 0, 0, 0, 0, byte1, byte2, 0, 10, 0] + [0] *(48)) #weird firmware thing that i spent ages figuring out, don't touch until firmware is changed
            send_byte_array_to_pic(Port, byte_array, Verbose)

    RAM_Bytes = ram_word_bytes(Array, Mode=Mode, PLL_Multiplier=PLL_Multiplier)
    write_to_ad9910(Port, "RAM", Board, RAM_Bytes, Verbose=Verbose)

def ram_profile_setting(Port, Board, Profile,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=0, End_Address=1, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Direct Switch', Verbose=False):
    if isinstance(Profile, int) and 0 <= Profile <= 7:
        Profile_Register = "P" + str(Profile)
        RAM_Profile_Bytes, _ = ram_profile_bytes(PLL_Multiplier=PLL_Multiplier, Amplitude_Ramp_Rate_Divider=Amplitude_Ramp_Rate_Divider, Start_Address=Start_Address, End_Address=End_Address, No_Dwell_High=No_Dwell_High, Zero_Crossing=Zero_Crossing, Profile_Mode=Profile_Mode)
        Profile_Bytes = [Profile]+RAM_Profile_Bytes # these are the bytes to write to the pic. Matthias' Firmware neglects the profile register and assigns a value given by the next byte, so we set this here
        write_to_ad9910(Port, Profile_Register, Board, Profile_Bytes, Verbose=Verbose)
    else:
        raise ValueError("Profile must be an integer between 0 and 7")

def start_ram(Port, Board, Verbose=False):
    Board_byte = Board & 0x07  # Ensure the board number is within the range 0-7
    byte_array = bytearray([ord('s'), Board_byte, 0, 1] +  [0] *(60))
    send_byte_array_to_pic(Port, byte_array, Verbose)

def interpolate_rf_power(calibration_file, frac, output_frequency):
    if frac > 1:
        raise ValueError("RF Output too high")
    if frac < 1E-5:
        return 0,0
    else:
        # Load the calibration file
        data = np.loadtxt(calibration_file, delimiter=',', skiprows=0)
        # Extract the Max_RF_Power from the first element
        Max_RF_Power = data[0, 0]
        # Extract the columns
        frequency_col = data[1:, 0] / 2 #factor of two translates the frequency shift to DDS frequency (double pass)
        rf_power_fractions = data[0, 1:]  # Assumes the first row contains the fractions
        optical_power_data = data[1:, 1:]  # The rest of the data
        # Find the maximum optical power for each frequency
        max_optical_power_per_frequency = np.max(optical_power_data, axis=1)
        # Find the minimum value among the maximum optical powers
        Max_Optical_Power = np.min(max_optical_power_per_frequency)
        Optical_Power_Output = frac * Max_Optical_Power

        # Find the indices of the two frequencies closest to the target frequency
        freq_indices = np.searchsorted(frequency_col, output_frequency, side='left')
        low_idx = freq_indices - 1
        high_idx = freq_indices
        # Ensure the indices are within bounds
        low_idx = max(low_idx, 0)
        high_idx = min(high_idx, len(frequency_col) - 1)
        # Get the frequencies and corresponding optical power data for interpolation
        low_freq = frequency_col[low_idx]
        high_freq = frequency_col[high_idx]
        low_power_data = optical_power_data[low_idx]
        high_power_data = optical_power_data[high_idx]
        # Interpolate the RF power fraction for Optical_Power_Output at low and high frequencies
        rf_power_low = np.interp(Optical_Power_Output, low_power_data, rf_power_fractions)
        rf_power_high = np.interp(Optical_Power_Output, high_power_data, rf_power_fractions)
        # Interpolate the RF power fraction between the two frequencies
        if low_freq == high_freq:
            rf_power_frac = rf_power_low
        else:
            rf_power_frac = np.interp(output_frequency, [low_freq, high_freq], [rf_power_low, rf_power_high])

        if rf_power_frac > 1:
            raise ValueError("RF Output too high")
    return int(rf_power_frac * Max_RF_Power), Optical_Power_Output

def interpolate_rf_power_array(calibration_file, frac_array, frequency_array):
    """
    Interpolates RF power for arrays of fractional powers and frequencies.
    This function is optimized for batch processing.
    """
    # Load the calibration file once
    data = np.loadtxt(calibration_file, delimiter=',', skiprows=0)
    Max_RF_Power = data[0, 0]
    frequency_col = data[1:, 0] / 2  # Factor of two translates the frequency shift to DDS frequency (double pass)
    rf_power_fractions = data[0, 1:]  # Assumes the first row contains the fractions
    optical_power_data = data[1:, 1:]  # The rest of the data
    max_optical_power_per_frequency = np.max(optical_power_data, axis=1)
    Max_Optical_Power = np.min(max_optical_power_per_frequency)

    # Ensure inputs are arrays
    frac_array = np.asarray(frac_array)
    frequency_array = np.asarray(frequency_array)

    if frac_array.shape != frequency_array.shape:
        raise ValueError("`frac_array` and `frequency_array` must have the same shape.")

    # Calculate optical power output
    Optical_Power_Output = frac_array * Max_Optical_Power

    # Initialize results
    rf_power_output = np.zeros_like(frac_array, dtype=int)

    for i, (frac, freq) in enumerate(zip(Optical_Power_Output, frequency_array)):
        if frac < 1E-5:
            rf_power_output[i] = 0
        else:
            # Find the indices of the two frequencies closest to the target frequency
            freq_indices = np.searchsorted(frequency_col, freq, side='left')
            low_idx = max(freq_indices - 1, 0)
            high_idx = min(freq_indices, len(frequency_col) - 1)

            low_freq = frequency_col[low_idx]
            high_freq = frequency_col[high_idx]
            low_power_data = optical_power_data[low_idx]
            high_power_data = optical_power_data[high_idx]

            # Interpolate the RF power fraction
            rf_power_low = np.interp(frac, low_power_data, rf_power_fractions)
            rf_power_high = np.interp(frac, high_power_data, rf_power_fractions)

            if low_freq == high_freq:
                rf_power_frac = rf_power_low
            else:
                rf_power_frac = np.interp(freq, [low_freq, high_freq], [rf_power_low, rf_power_high])

            if rf_power_frac > 1:
                raise ValueError("RF Output too high")

            rf_power_output[i] = int(rf_power_frac * Max_RF_Power)

    return rf_power_output, Optical_Power_Output


class Laser:
    PLL_MULTIPLIER = 40
    VALID_MODES = {'master', 'slave', 'standalone'}

    def __init__(self, name: str, port: str, mode: str, board: int, calibration_file: str):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}' for laser {name}. Valid modes are: {', '.join(self.VALID_MODES)}")
        
        self.name = name
        self.port = port
        self.mode = mode
        self.board = board
        self.calibration_file = calibration_file
        data = np.loadtxt(self.calibration_file, delimiter=',', skiprows=0)
        # Extract the Max_RF_Power from the first element
        Max_RF_Power = data[0, 0]
        self.max_RF_power = Max_RF_Power
        self.amplitude = [0] * 8
        self.frequency = [200] * 8
        self.phase = [0] * 8
        self.on_state = True  # Initialize with laser ON always
        self.stored_amplitude = [0] * 8  # Store intended amplitude when laser is off
        self.optical_power = [0.0] * 8  # Store optical power for each profile
        self.stored_optical_power = [0.0] * 8  # Store intended optical power when laser is off

    def apply_general_settings(self):
        """Apply general settings based on the mode."""
        if self.mode == 'master':
            general_setting_master(self.port, self.board)
        elif self.mode == 'slave':
            general_setting_slave(self.port, self.board)
        elif self.mode == 'standalone':
            general_setting_standalone(self.port, self.board)
        else:
            raise ValueError(f"Unknown mode {self.mode} for laser {self.name}.")
 
    def update_detuning(self, detuning: float, frac: float, profile: int):
        """Update the detuning and amplitude based on the given detuning, fractional power, and profile."""
        frequency = detuning / 2 + 200
        self.frequency[profile] = frequency
        self._update_output(frac, frequency, profile)
 
    def update_optical_power(self, frac: float, profile: int):
        """Update the optical power based on the given fractional power and profile."""
        self._update_output(frac, self.frequency[profile], profile)
 
    def _update_output(self, frac: float, frequency: float, profile: int):
        """Helper method to update DDS output amplitude and frequency for a specific profile."""
        if not (0 <= frac <= 1):
            raise ValueError("Fractional output power must be between 0 and 1.")
       
        intended_amplitude, optical_power = interpolate_rf_power(self.calibration_file, frac, frequency)
        intended_amplitude = round(intended_amplitude)
        if self.on_state:
            self.amplitude[profile] = intended_amplitude
            self._apply_single_tone_profile(profile)
            self.optical_power[profile] = optical_power  # Store the optical power
        else:
            self.stored_amplitude[profile] = intended_amplitude
            self.stored_optical_power[profile] = optical_power
 
    def update_phase(self, phase: float, profile: int):
        """Update the phase offset for a specific profile."""
        self.phase[profile] = phase
        if self.on_state:
            self._apply_single_tone_profile(profile)
 
    def toggle(self, profile: int):
        """Toggle the laser on and off for a specific profile."""
        if self.on_state:  # Laser is on, turn it off
            self.stored_amplitude[profile] = self.amplitude[profile]
            self.stored_optical_power[profile] = self.optical_power[profile]
            self.amplitude[profile] = 0
            self.optical_power[profile] = 0.0
            self.on_state = False
        else:  # Laser is off, turn it on
            self.amplitude[profile] = self.stored_amplitude[profile]
            self.optical_power[profile] = self.stored_optical_power[profile]
            self.on_state = True
       
        self._apply_single_tone_profile(profile)
 
    def _apply_single_tone_profile(self, profile: int):
        """Apply the single tone profile settings for a specific profile."""
        print(self.board)
        single_tone_profile_setting(
            Port=self.port,
            Board=self.board,
            Profile=profile,
            PLL_Multiplier=self.PLL_MULTIPLIER,
            Amplitude=self.amplitude[profile],
            Phase_Offset=self.phase[profile],
            Frequency=self.frequency[profile],
            Verbose=False
        )

def create_laser_objects(config_file, include_lasers):
    """Creates laser objects based on the given configuration file and includes only specified lasers."""
    config = configparser.ConfigParser()
    config.read(config_file)
    
    lasers = []
    for section in config.sections():
        if section in include_lasers:
            name = section
            port = config[section]['port']
            board = int(config[section]['board'])
            mode = config[section]['mode']
            calibration_file = config[section]['calibration_file']
            laser = Laser(name, port, mode, board, calibration_file)
            lasers.append(laser)
    
    return lasers


class LaserControl(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.lasers = []
        self.presets = {}

        # Main frame to hold laser information and preset buttons
        self.main_frame = ttk.Frame(self, padding="10", relief="raised", borderwidth=2)
        self.main_frame.grid(column=0, row=0, columnspan=6, pady=10, sticky=(tk.W, tk.E))

        # Frame to hold laser information
        self.laser_frame = ttk.Frame(self.main_frame)
        self.laser_frame.grid(column=0, row=0, columnspan=6, pady=10, sticky=(tk.W, tk.E))

        # Configure columns in laser_frame
        for col in range(4):  # Adjusted to 4 columns
            self.laser_frame.grid_columnconfigure(col, weight=1, uniform="control")

        # Initialize header labels
        self._initialize_header()

        # Frame to hold preset buttons
        self.preset_button_frame = ttk.Frame(self.main_frame)
        self.preset_button_frame.grid(column=0, row=1, columnspan=6, pady=10, sticky=(tk.W, tk.E))

        # Add General Settings, Save, and Load Preset buttons
        self._initialize_preset_buttons()

    def _run_in_thread(self, func, *args):
        thread = threading.Thread(target=func, args=args)
        thread.start()

    def _initialize_header(self):
        ttk.Label(self.laser_frame, text="Name").grid(column=0, row=0, padx=10, pady=5, sticky="w")
        ttk.Label(self.laser_frame, text="Detuning").grid(column=1, row=0, padx=10, pady=5, sticky="w")
        ttk.Label(self.laser_frame, text="Power Fraction").grid(column=2, row=0, padx=10, pady=5, sticky="w")
        ttk.Label(self.laser_frame, text="DDS Amplitude").grid(column=3, row=0, padx=10, pady=5, sticky="w")
        ttk.Label(self.laser_frame, text="Power (mW)").grid(column=4, row=0, padx=10, pady=5, sticky="w")
        

    def _initialize_preset_buttons(self):
        general_settings_button = tk.Button(self.preset_button_frame, text="General Settings", command=self.apply_general_settings, relief="raised", borderwidth=2)
        general_settings_button.pack(side=tk.LEFT, padx=5, pady=5)

        save_button = tk.Button(self.preset_button_frame, text="Save Preset", command=self.save_preset_dialog, relief="raised", borderwidth=2)
        save_button.pack(side=tk.LEFT, padx=5, pady=5)

        load_button = tk.Button(self.preset_button_frame, text="Load Preset", command=self.load_preset_dialog, relief="raised", borderwidth=2)
        load_button.pack(side=tk.LEFT, padx=5, pady=5)

    def add_laser(self, laser):
        # Check for duplicate board-port combination
        for existing_laser in self.lasers:
            if existing_laser.board == laser.board and existing_laser.port == laser.port:
                raise ValueError(f"Laser with board {laser.board} and port {laser.port} already exists.")
        
        # Add the laser if no duplicate is found
        self.lasers.append(laser)
        self._create_control_widgets(laser)
    def _create_control_widgets(self, laser):
        row = len(self.lasers)

        # Existing label for laser name
        ttk.Label(self.laser_frame, text=laser.name).grid(column=0, row=row, padx=10, pady=5, sticky="w")

        # Existing Detuning Spinbox
        detuning_spinbox = CustomSpinbox(self.laser_frame, from_=-50.0, to=50.0, increment=0.1, width=10)
        detuning_spinbox.grid(column=1, row=row, padx=10, pady=5, sticky="ew")
        detuning_spinbox.set_callback(lambda value: self._run_in_thread(self._update_laser_detuning, laser, value, row))
        laser.detuning_spinbox = detuning_spinbox

        # Existing Optical Power Spinbox
        optical_power_spinbox = CustomSpinbox(self.laser_frame, from_=0, to=1.0, increment=0.01, width=10)
        optical_power_spinbox.grid(column=2, row=row, padx=10, pady=5, sticky="ew")
        optical_power_spinbox.set_callback(lambda value: self._run_in_thread(self._update_laser_optical_power, laser, value, row))
        laser.optical_power_spinbox = optical_power_spinbox

        # Existing RF Power label
        rf_power_label = ttk.Label(self.laser_frame, text=f"{laser.amplitude[0]}", relief="sunken", anchor="w")
        rf_power_label.grid(column=3, row=row, padx=10, pady=5, sticky="ew")
        laser.rf_power_label = rf_power_label

        optical_power_label = ttk.Label(self.laser_frame, text=f"{laser.optical_power[0]}", relief="sunken", anchor="w")
        optical_power_label.grid(column=4, row=row, padx=10, pady=5, sticky="ew")
        laser.optical_power_label = optical_power_label

        # New On/Off button, smaller size
        on_off_button = tk.Button(self.laser_frame, text="On", width=3, relief="raised", bg="lime green", fg="white")
        on_off_button.config(command=lambda: self._run_in_thread(self._toggle_laser, laser, rf_power_label, on_off_button))
        on_off_button.grid(column=5, row=row, padx=5, pady=5, sticky="ew")
        laser.on_off_button = on_off_button

        # New Plus button to show laser info
        info_button = tk.Button(self.laser_frame, text="+", width=3, relief="raised", command=lambda: self._show_info(laser))
        info_button.grid(column=6, row=row, padx=5, pady=5, sticky="ew")

    def _update_laser_detuning(self, laser, value, row):
        try:
            detuning = float(value)
            fractional_power = float(laser.optical_power_spinbox.get())
            laser.update_detuning(detuning, fractional_power, profile=0)  # Assuming profile 0 for simplicity
            self._update_output_labels(laser)
        except ValueError as e:
            print(f"Invalid detuning value: {e}")

    def _update_laser_optical_power(self, laser, value, row):
        try:
            fractional_power = float(value)
            laser.update_optical_power(fractional_power, profile=0)  # Assuming profile 0 for simplicity
            self._update_output_labels(laser)
        except ValueError as e:
            print(f"Invalid optical power value: {e}")

    def _toggle_laser(self, laser, rf_power_label, button):
        laser.toggle(profile=0)  # Assuming profile 0 for simplicity
        if laser.on_state:
            button.config(text="On", bg="lime green", relief="raised")
        else:
            button.config(text="Off", bg="dark green", relief="sunken")
        self._update_output_labels(laser)
        print(f"Laser {laser.name} {'enabled' if laser.on_state else 'disabled'}.")

    def _update_output_labels(self, laser):
        laser.rf_power_label.config(text=f"{laser.amplitude[0]}")
        laser.optical_power_label.config(text=f"{laser.optical_power[0]*1E3:.3g}")

    def save_preset_dialog(self):
        preset_name = asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if preset_name:
            self.save_preset(preset_name)

    def save_preset(self, preset_name):
        preset = {}
        for laser in self.lasers:
            preset[laser.name] = {
                'detuning': laser.detuning_spinbox.get(),
                'optical_power': laser.optical_power_spinbox.get(),
                'rf_power': laser.amplitude[0],
                'on_state': laser.on_state
            }
        with open(preset_name, 'w') as f:
            json.dump(preset, f)
        print(f"Preset saved to '{preset_name}'.")

    def load_preset_dialog(self):
        preset_name = askopenfilename(filetypes=[("JSON files", "*.json")])
        if preset_name:
            self.load_preset(preset_name)

    def load_preset(self, preset_name):
        try:
            with open(preset_name, 'r') as f:
                preset = json.load(f)
        except FileNotFoundError:
            print(f"Preset file '{preset_name}' not found.")
            return
        for laser in self.lasers:
            if laser.name in preset:
                laser_preset = preset[laser.name]
                if laser.detuning_spinbox.get() != laser_preset['detuning']:
                    laser.detuning_spinbox.set(laser_preset['detuning'])
                    self._update_laser_detuning(laser, laser_preset['detuning'], 0)
                if laser.optical_power_spinbox.get() != laser_preset['optical_power']:
                    laser.optical_power_spinbox.set(laser_preset['optical_power'])
                    self._update_laser_optical_power(laser, laser_preset['optical_power'], 0)
                if laser.amplitude[0] != laser_preset['rf_power']:
                    laser.amplitude[0] = laser_preset['rf_power']
                    self._update_output_labels(laser)
                if laser.on_state != laser_preset['on_state']:
                    self._toggle_laser(laser, laser.rf_power_label, laser.on_off_button)
        print(f"Preset loaded from '{preset_name}'.")
        
    def add_quick_preset_button(self, preset_name, filename, bg="red"):
        button = tk.Button(self.preset_button_frame, text=preset_name, bg=bg, command=lambda: self.load_preset(filename), relief="raised", borderwidth=2)
        button.pack(side=tk.LEFT, padx=5, pady=5)
        print(f"Quick preset button for '{preset_name}' added.")

    def apply_general_settings(self):
        for laser in self.lasers:
            laser.apply_general_settings()
        print("General settings applied to all lasers.")

    def _show_info(self, laser):
        info_message = (
            f"Port: {laser.port}\n"
            f"Mode: {laser.mode}\n"
            f"Board: {laser.board}\n"
            f"Calibration File: {laser.calibration_file}\n"
            f"Max Value: {laser.max_RF_power}"
        )
        messagebox.showinfo("Laser Information", info_message)

