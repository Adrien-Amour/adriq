import serial 
import time
def pulse_out(Port, Bitstring, Verbose = False):
    byte1 = int(Bitstring[0:8], 2)
    byte2 = int(Bitstring[8:16], 2)
    byte_array = bytearray([ord('u'), byte1, byte2] + [0] * (61))
    ser = serial.Serial(Port, 9600, timeout=1)  # Adjust the Port and baud rate as necessary
    try:
        # Send the byte array
        ser.write(byte_array)

        # Give the device some time to respond
        time.sleep(0.1)  # Adjust the sleep time if necessary
        if Verbose:
            print("Sent=")
            for i in range(len(Write_Bytes)+3):
                print(byte_array[i], end=',')
            # Read the response (assuming the response is within 64 bytes)
            response = ser.read(64)  # Adjust the number of bytes to read if necessary
            # Print the response (you might need to deCode it or process it based on the device's protocol)
            print("\n Response:", response)
    finally:
        # Close the serial Port
        ser.close()
        time.sleep(0.01)
    
def write_pulse_sequencer(Port, Pulses, Pulse_Lengths, Continuous=False, N_Cycles=10000, End_Pulse='0000000000000001', Measurement_Window=1, Threshold_Counts=4, Clock_Frequency=80, Initial_Delay=80, Delay = 115, Final_Delay=185, Verbose = False):
    # Check that Pulses is a list of 16-bit bit strings
    for pulse in Pulses:
        if not isinstance(pulse, str):
            raise ValueError("Each pulse must be a string.")
        if len(pulse) != 16:
            raise ValueError("Each pulse must be 16 bits long.")
        if not all(bit in '01' for bit in pulse):
            raise ValueError("Each pulse must contain only '0's and '1's.")
    
    for i, length in enumerate(Pulse_Lengths):
        if not isinstance(length, int):
            raise ValueError("Each pulse length must be an integer.")
        if length < 0 or length > 0xFFFFFFFF:
            raise ValueError(f"Pulse {i} too long: Each pulse length must be a 32-bit integer (0 <= length <= 2^32 - 1).")
        if length < Delay / Clock_Frequency:
            raise ValueError(f"Pulse {i} too short: Each pulse length must be longer than {Delay / Clock_Frequency}.")

    
    # Check that both lists have the same length
    if len(Pulses) != len(Pulse_Lengths):
        raise ValueError("The length of Pulses and Pulse_Lengths must be the same.")
    if len(Pulses) > 10:
        raise ValueError("The maximum number of pulses is 10.")
    
    # Check that Measurement_Window is an 8-bit unsigned integer
    if not isinstance(Measurement_Window, int):
        raise TypeError(f"Measurement_Window must be an integer, got {type(Measurement_Window).__name__}")
    if Measurement_Window < 0 or Measurement_Window > 0xFF:
        raise ValueError("Measurement_Window must be an 8-bit unsigned integer (0 <= Measurement_Window <= 255).")
    
    # Check that Threshold_Counts is an 8-bit unsigned integer
    if not isinstance(Threshold_Counts, int):
        raise TypeError(f"Threshold_Counts must be an integer, got {type(Threshold_Counts).__name__}")
    if Threshold_Counts < 0 or Threshold_Counts > 0xFF:
        raise ValueError("Threshold_Counts must be an 8-bit unsigned integer (0 <= Threshold_Counts <= 255).")
    
    N_Cycles_Bin = format(N_Cycles, '032b')
    Measurement_Window_Bin = format(Measurement_Window,'08b')
    Threshold_Counts_Bin = format(Threshold_Counts,'08b')
    Length_Bin = format(len(Pulses), '08b')
    Length_Bin_2 = format(int(len(Pulses) // 10) + ((len(Pulses) / 10 ) % 1 > 0), '08b') #Weird thing from Matthias'firmware, don't know why its needed but don't question it
    settings_string = [0] * 88
    settings_string[0:8] = '00000000' if Continuous else '00000001'
    settings_string[8:16] = Length_Bin
    settings_string[16:48] = N_Cycles_Bin
    settings_string[48:64] = End_Pulse
    settings_string[64:72] = Measurement_Window_Bin
    settings_string[72:80] = Threshold_Counts_Bin
    settings_string[80:88] = Length_Bin_2
    byte1 = int(''.join(map(str, settings_string[0:8])), 2)
    byte2 = int(''.join(map(str, settings_string[8:16])), 2)
    byte3 = int(''.join(map(str, settings_string[16:24])), 2)
    byte4 = int(''.join(map(str, settings_string[24:32])), 2)
    byte5 = int(''.join(map(str, settings_string[32:40])), 2)
    byte6 = int(''.join(map(str, settings_string[40:48])), 2)
    byte7 = int(''.join(map(str, settings_string[48:56])), 2)
    byte8 = int(''.join(map(str, settings_string[56:64])), 2)
    byte9 = int(''.join(map(str, settings_string[64:72])), 2)
    byte10 = int(''.join(map(str, settings_string[72:80])), 2)
    byte11 = int(''.join(map(str, settings_string[80:88])), 2)

    Settings_Bytes = [ord('w'), byte1, byte2, byte3, byte4, byte5, byte6, byte7, byte8, byte9, byte10, byte11]
    Settings_Bytes.extend(bytearray(64 - len(Settings_Bytes)))
    ser = serial.Serial(Port, 9600, timeout=1)  # Adjust the Port and baud rate as necessary

    try:
        # Send the byte array
        ser.write(Settings_Bytes)

        # Give the device some time to respond
        time.sleep(0.1)  # Adjust the sleep time if necessary       
        if Verbose:
            print("Sent:", end=" ")
            for byte in Settings_Bytes:
                print(byte, end=', ')
            print()
            
            # Read the response (assuming the response is within 64 bytes)
            response = ser.read(64)  # Adjust the number of bytes to read if necessary
            
            # Print the response (you might need to decode it or process it based on the device's protocol)
            print("Response:", response)
    finally:
        # Close the serial Port
        ser.close()
        time.sleep(0.01)

    # #now we load the pulses    
    Pulse_Lengths_Corrected = [(length * Clock_Frequency) - Delay for length in Pulse_Lengths]
    Pulse_Lengths_Corrected[0] -= Initial_Delay
    Pulse_Lengths_Corrected = []
    for i, length in enumerate(Pulse_Lengths):
        corrected_length = (length * Clock_Frequency)
        if i == 0:
            corrected_length -= Initial_Delay
        elif i == len(Pulse_Lengths) - 1:
            corrected_length -= Final_Delay
        else:
            corrected_length -= Delay
        Pulse_Lengths_Corrected.append(corrected_length)

    # Convert Pulse_Lengths_Corrected to 32-bit binary strings
    Pulse_Lengths_Corrected_Bin = [format(length, '032b') for length in Pulse_Lengths_Corrected]
    Pulse_Bytes = [ord('p'), 1, 0]  

    for i in range(len(Pulse_Lengths)):
        pulsestring = [0]*48
        pulsestring[16:48] = list(Pulse_Lengths_Corrected_Bin[i])
        pulsestring[0:16] = list(Pulses[i])
        # Convert the bitstring to bytes
        byte1 = int(''.join(map(str, pulsestring[0:8])), 2)
        byte2 = int(''.join(map(str, pulsestring[8:16])), 2)
        byte3 = int(''.join(map(str, pulsestring[16:24])), 2)
        byte4 = int(''.join(map(str, pulsestring[24:32])), 2)
        byte5 = int(''.join(map(str, pulsestring[32:40])), 2)
        byte6 = int(''.join(map(str, pulsestring[40:48])), 2)
        Pulse_Bytes.extend([byte1, byte2, byte3, byte4, byte5, byte6])
    Pulse_Bytes.extend(bytearray(64 - len(Pulse_Bytes)))
    
    ser = serial.Serial(Port, 9600, timeout=1)  # Adjust the Port and baud rate as necessary

    try:
        # Send the byte array
        ser.write(Pulse_Bytes)

        # Give the device some time to respond
        time.sleep(0.1)  # Adjust the sleep time if necessary
                
        if Verbose:
            print("Sent:", end=" ")
            for byte in Pulse_Bytes:
                print(byte, end=', ')
            print()
            
            # Read the response (assuming the response is within 64 bytes)
            response = ser.read(64)  # Adjust the number of bytes to read if necessary
            
            # Print the response (you might need to decode it or process it based on the device's protocol)
            print("Response:", response)
    finally:
        # Close the serial Port
        ser.close()
        time.sleep(0.01)

def control_pulse_sequencer(Port, Action: str, Verbose=False):
    if Action == 'Start':
        # Bytes to start the pulse sequencer
        byte_array = bytearray([ord('s'), 1, 0, 0, 0])
    elif Action == 'Stop':
        # Bytes to stop the pulse sequencer
        byte_array = bytearray([ord('s'), 0, 0, 0, 0])
    else:
        raise ValueError("Invalid action. Use 'Start' or 'Stop'.")

    # Extend the byte_array to 64 bytes with zero padding
    byte_array.extend(bytearray(64 - len(byte_array)))

    ser = serial.Serial(Port, 9600, timeout=1)  # Adjust the Port and baud rate as necessary

    try:
        # Send the byte array
        ser.write(byte_array)

        # Give the device some time to respond
        time.sleep(0.1)  # Adjust the sleep time if necessary
        
        if Verbose:
            print("Sent:", end=" ")
            for byte in byte_array:
                print(byte, end=', ')
            print()
            
            # Read the response (assuming the response is within 64 bytes)
            response = ser.read(64)  # Adjust the number of bytes to read if necessary
            
            # Print the response (you might need to decode it or process it based on the device's protocol)
            print("Response:", response)
    finally:
        # Close the serial port
        ser.close()
        time.sleep(0.01)

import tkinter as tk
from tkinter import ttk
from .Custom_Tkinter import CustomBinarySpinbox

class PulseSequencerFrame(tk.Frame):
    def __init__(self, master=None, defaultbitstring="0100000000000000", pulse_sequencer_port="COM5"):
        super().__init__(master)
        self.grid(padx=10, pady=10)
        self.pulse_sequencer_port = pulse_sequencer_port
        self.create_widgets(defaultbitstring)

    def create_widgets(self, defaultbitstring):
        static_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2)
        static_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        self.label = tk.Label(static_frame, text="Pulse Out:")
        self.label.grid(row=0, column=0, padx=5, pady=5)
        self.spinbox = CustomBinarySpinbox(static_frame, from_=0, to=65535, initial_value=defaultbitstring)
        self.spinbox.grid(row=0, column=1, padx=5, pady=5)
        self.spinbox.set_callback(self.Pulse_Out)
        
        defaultbitstring = int(defaultbitstring, 2)
        self.Pulse_Out(defaultbitstring)

    def Pulse_Out(self, value):
        
        Bitstring = format(value, '016b')
        print(f"Pulse Sequencer Output:{Bitstring}")
        pulse_out(self.pulse_sequencer_port, Bitstring)

