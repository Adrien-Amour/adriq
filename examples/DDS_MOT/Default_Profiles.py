import serial.tools.list_ports
from adriq.ad9910 import *
from adriq.pulse_sequencer import *
import time

def find_default_profile_pin():
    # Set pulse sequencer pin to high
    pulse = ['0'] * 16
    pulse_str = ''.join(pulse)
    pulse_out("COM5", pulse_str)
    # List available COM ports
    ports = list(serial.tools.list_ports.comports())
    print("Available COM ports:")
    for i, port in enumerate(ports):
        print(f"{i}: {port.device}")

    # Ask for COM port
    port_index = int(input("Select COM port index: "))
    port = ports[port_index].device

    # Ask for board number
    board = int(input("Enter board number: "))

    # Ask for mode
    mode = input("Enter mode (master (0)/slave (1)/standalone (2)): ").strip().lower()

    if mode == "0":
        master_board = int(input("Enter master board number: "))
        general_setting_slave(port, board)
        general_setting_master(port, master_board)
    elif mode == "1":
        general_setting_master(port, board)
    elif mode == "2":
        general_setting_standalone(port, board)
    else:
        print("Invalid mode")
        return

    # Go through profiles one by one
    default_profile = None
    for profile in range(8):
        single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=5000, Phase_Offset=0, Frequency=20, Verbose=True)
        time.sleep(1)  # Wait for the profile to take effect
        output = input(f"Does profile {profile} produce an output? (yes/no): ").strip().lower()
        if output == "no":
            single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)
        else:
            default_profile = profile
            single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)
            break

    if default_profile is not None:
        print(f"Default profile is: {default_profile}")
    else:
        print("No default profile found.")

def find_profile_with_pin_high():
    # List available COM ports
    ports = list(serial.tools.list_ports.comports())
    print("Available COM ports:")
    for i, port in enumerate(ports):
        print(f"{i}: {port.device}")

    # Ask for COM port
    port_index = int(input("Select COM port index: "))
    port = ports[port_index].device

    # Ask for board number
    board = int(input("Enter board number: "))

    # Ask for pulse sequencer pin
    pulse_sequencer_pin = int(input("Enter pulse sequencer pin (0-15): "))

    # Set pulse sequencer pin to high
    pulse = ['0'] * 16
    pulse[pulse_sequencer_pin] = '1'
    pulse_str = ''.join(pulse)
    pulse_out("COM5", pulse_str)

    # Go through profiles one by one
    default_profile = None
    for profile in range(8):
        single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=5000, Phase_Offset=0, Frequency=20, Verbose=True)
        time.sleep(2)  # Wait for the profile to take effect
        output = input(f"Does profile {profile} produce an output with pin {pulse_sequencer_pin} high? (yes/no): ").strip().lower()
        if output == "no":
            single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)
        else:
            default_profile = profile
            single_tone_profile_setting(port, board, profile, PLL_Multiplier=40, Amplitude=0, Phase_Offset=0, Frequency=20, Verbose=True)
            break

    if default_profile is not None:
        print(f"Default profile with pin {pulse_sequencer_pin} high is: {default_profile}")
    else:
        print(f"No default profile found with pin {pulse_sequencer_pin} high.")

# Example usage
find_default_profile_pin()
find_profile_with_pin_high()