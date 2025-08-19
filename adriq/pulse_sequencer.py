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
    
def write_pulse_sequencer(Port, Pulses, Pulse_Lengths, Continuous=False, N_Cycles=10000, End_Pulse='0000000000000001',
                           Measurement_Window=1, ThresholdLow=-1, ThresholdHigh=-1, Clock_Frequency=80, Initial_Delay=76,
                           Delay=115, Final_Delay=260, Verbose=False):

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
    
    if not isinstance(ThresholdLow, int):
        raise TypeError(f"ThresholdLow must be an integer, got {type(ThresholdLow).__name__}")
    if ThresholdLow < -32768 or ThresholdLow > 32767:
        raise ValueError("ThresholdLow must be a 16-bit signed integer (-32768 <= ThresholdLow <= 32767).")
    
    if not isinstance(ThresholdHigh, int):
        raise TypeError(f"ThresholdHigh must be an integer, got {type(ThresholdHigh).__name__}")
    if ThresholdHigh < -32768 or ThresholdHigh > 32767:
        raise ValueError("ThresholdHigh must be a 16-bit signed integer (-32768 <= ThresholdHigh <= 32767).")
    
    
    N_Cycles_Bin = format(N_Cycles, '032b')
    Measurement_Window_Bin = format(Measurement_Window,'08b')
    Length_Bin = format(len(Pulses), '08b')
    Length_Bin_2 = format(int(len(Pulses) // 10) + ((len(Pulses) / 10 ) % 1 > 0), '08b') #Weird thing from Matthias'firmware, don't know why its needed but don't question it
    ThresholdLow_Bin = format(ThresholdLow & 0xFFFF, '016b')  # Convert to unsigned 16-bit
    ThresholdHigh_Bin = format(ThresholdHigh & 0xFFFF, '016b')  # Convert to unsigned 16-bit
    
    settings_string = [0] * 88
    settings_string[0:8] = '00000000' if Continuous else '00000001'
    settings_string[8:16] = Length_Bin
    settings_string[16:48] = N_Cycles_Bin
    settings_string[48:64] = End_Pulse
    settings_string[64:72] = Measurement_Window_Bin
    settings_string[72:88] = ThresholdLow_Bin  # 16 bits
    settings_string[88:104] = ThresholdHigh_Bin  # 16 bits
    settings_string[104:112] = Length_Bin_2

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
    byte12 = int(''.join(map(str, settings_string[88:96])), 2)
    byte13 = int(''.join(map(str, settings_string[96:104])), 2)
    byte14 = int(''.join(map(str, settings_string[104:112])), 2)

    Settings_Bytes = [ord('w'), byte1, byte2, byte3, byte4, byte5, byte6, byte7, byte8, byte9, byte10, byte11, byte12, byte13, byte14]
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


def write_optional_pulses(Port, OptionalPulses, OptionalPulseLengths, Clock_Frequency=80,  Initial_Delay=119,
                           Delay=127, Final_Delay=273, Verbose=False):
    """Send optional pulse sequence to the device using 'o' command"""
    
    if len(OptionalPulses) != len(OptionalPulseLengths):
        raise ValueError("OptionalPulses and OptionalPulseLengths must have the same length.")
    
    if len(OptionalPulses) > 10:
        raise ValueError("Maximum 10 optional pulses allowed.")
    
    # Validate pulses
    for pulse in OptionalPulses:
        if not isinstance(pulse, str) or len(pulse) != 16 or not all(bit in '01' for bit in pulse):
            raise ValueError("Each optional pulse must be a 16-bit binary string.")
    
    # Validate lengths
    for length in OptionalPulseLengths:
        if not isinstance(length, int) or length < 0 or length > 0xFFFFFFFF:
            raise ValueError("Each optional pulse length must be a 32-bit unsigned integer.")
    
    Pulse_Lengths_Corrected = [(length * Clock_Frequency) - Delay for length in OptionalPulseLengths]
    Pulse_Lengths_Corrected[0] -= Initial_Delay
    Pulse_Lengths_Corrected = []
    
    # Correct pulse lengths
    OptionalPulseLengths_Corrected = []
    for i, length in enumerate(OptionalPulseLengths):
        corrected_length = (length * Clock_Frequency)
        if i == 0 and i < len(OptionalPulseLengths) - 1:
            corrected_length -= Initial_Delay
        elif i > 0 and i == len(OptionalPulseLengths) - 1:
            corrected_length -= Final_Delay
        elif i == 0 and len(OptionalPulseLengths) == 1:
            corrected_length -= 271
        else:
            corrected_length -= Delay
        if corrected_length < 0:
            print(f"Pulse {i} length is too short after correction: {corrected_length}")
            corrected_length = 10
        OptionalPulseLengths_Corrected.append(corrected_length)

    # Build command
    Optional_Bytes = [ord('o')]

    for i in range(len(OptionalPulses)):
        # Convert pulse pattern to 2 bytes
        pulse_value = int(OptionalPulses[i], 2)
        Optional_Bytes.extend([pulse_value >> 8, pulse_value & 0xFF])

        # Convert corrected length to 4 bytes
        length = OptionalPulseLengths_Corrected[i]
        Optional_Bytes.extend([
            (length >> 24) & 0xFF,
            (length >> 16) & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF
        ])

    # Pad to 64 bytes, but put count in last byte
    Optional_Bytes.extend([0] * (61 - len(Optional_Bytes)))
    Optional_Bytes.append(len(OptionalPulses))  # Count in last byte
    print(Optional_Bytes[61])

    ser = serial.Serial(Port, 9600, timeout=1)
    try:
        ser.write(Optional_Bytes)
        time.sleep(0.1)
        
        if Verbose:
            print("Optional pulses sent:", end=" ")
            for byte in Optional_Bytes:
                print(byte, end=', ')
            print()
            
            response = ser.read(64)
            print("Response:", response)
    finally:
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



def read_pulse_sequencer_results(Port, Verbose=False):
    """
    Read measurement results from the pulse sequencer.
    
    Returns:
        dict: Dictionary containing:
            - 'cycle_number': Current cycle number (32-bit)
            - 'state_readout_results': Number of times state readout was triggered (32-bit)
            - 't1_counter': Total T1 counts accumulated over all cycles (32-bit)
            - 't2_counter': Total T2 counts accumulated over all cycles (32-bit) 
            - 't3_counter': Total T3 counts accumulated over all cycles (32-bit)
            - 'optional_pulses': Number of times optional triggers were fired (32-bit)
    """
    import serial
    import time
    
    # Send 'r' command to read results
    byte_array = bytearray([ord('r')] + [0] * 63)  # 'r' command padded to 64 bytes
    
    ser = serial.Serial(Port, 9600, timeout=1)
    
    try:
        # Send the read command
        ser.write(byte_array)
        time.sleep(0.1)  # Give device time to respond
        
        # Read the response
        response = ser.read(64)
        
        if len(response) < 25:
            raise ValueError("Incomplete response from device")
        
        # Parse the response according to firmware structure
        # bufIN[0] = 'R' (confirmation)
        # bufIN[1-4] = CycleNumber (32-bit, big-endian)
        # bufIN[5-8] = StateReadOutResults (32-bit, big-endian) 
        # bufIN[9-12] = T1Counter (32-bit, big-endian)
        # bufIN[13-16] = T2Counter (32-bit, big-endian)
        # bufIN[17-20] = T3Counter (32-bit, big-endian)
        # bufIN[21-24] = OptionalTriggers (32-bit, big-endian)
        
        if response[0] != ord('R'):
            raise ValueError(f"Unexpected response header: {response[0]} (expected {ord('R')})")
        
        cycle_number = (response[1] << 24) | (response[2] << 16) | (response[3] << 8) | response[4]
        state_readout_results = (response[5] << 24) | (response[6] << 16) | (response[7] << 8) | response[8]
        t1_counter = (response[9] << 24) | (response[10] << 16) | (response[11] << 8) | response[12]
        t2_counter = (response[13] << 24) | (response[14] << 16) | (response[15] << 8) | response[16]
        t3_counter = (response[17] << 24) | (response[18] << 16) | (response[19] << 8) | response[20]
        optional_pulses = (response[21] << 24) | (response[22] << 16) | (response[23] << 8) | response[24]
        windows = (response[25] << 24) | (response[26] << 16) | (response[27] << 8) | response[28]

        results = {
            'cycle_number': cycle_number,
            'state_readout_results': state_readout_results,
            't1_counter': t1_counter,
            't2_counter': t2_counter,
            't3_counter': t3_counter,
            'optional_pulses': optional_pulses
        }
        
        
        print(f"Cycle Number: {cycle_number}")
        print(f"State Readout Results: {state_readout_results}")
        print(f"T1 Counter: {t1_counter}")
        print(f"T2 Counter: {t2_counter}")
        print(f"T3 Counter: {t3_counter}")
        print(f"Optional Pulses Triggered: {optional_pulses}")
        # print("Raw response:", [hex(b) for b in response[:25]])
        print(f"Measurement Windows: {windows}")
        return results
        
    except Exception as e:
        if Verbose:
            print(f"Error reading results: {e}")
        raise
        
    finally:
        ser.close()
        time.sleep(0.01)

def count_edges(com_port='COM5', channel=1, duration_ms=100):
    """
    Send a 'c' command to the device to count edges on TMR1/2/3 for a specified time.
 
    :param com_port: Serial port (e.g., 'COM5')
    :param channel: Timer channel (1, 2, or 3)
    :param duration_ms: Duration in milliseconds to count edges
    :return: Number of edges counted, or None on error
    """
    if channel not in (1, 2, 3):
        raise ValueError("Channel must be 1, 2, or 3")
 
    try:
        with serial.Serial(com_port, 9600, timeout=20) as ser:
            # Prepare message: 'c' + channel + 4-byte duration (big endian)
            msg = struct.pack('>cB I', b'c', channel, duration_ms)
            ser.write(msg)
 
            # Expecting 5-byte reply: 'C' + 4-byte result
            reply = ser.read(5)
            if len(reply) != 5 or reply[0:1] != b'C':
                print("Invalid reply:", reply)
                return None
 
            count = struct.unpack('>I', reply[1:])[0]
            return count
 
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return None