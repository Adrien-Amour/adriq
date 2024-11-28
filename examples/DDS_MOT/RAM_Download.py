import serial.tools.list_ports
from adriq.ad9910 import *
from adriq.pulse_sequencer import *
import time

def test_ram():
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

    
    # Parameters
    array_size = 1000
    center =  array_size // 2
    std_dev = 100

    # Generate Gaussian array
    x = np.arange(array_size - 3)
    gaussian_array = np.exp(-((x - center) ** 2) / (2 * std_dev ** 2))
    gaussian_array *= 6000
    gaussian_array = np.round(gaussian_array).astype(int)

    trig = np.array([5000, 5000, 5000, 5000, 5000])

    # Concatenate arrays with trig
    gaussian_array = np.concatenate((trig, gaussian_array))

    control_pulse_sequencer("COM5", 'Stop')  # always stop pulse sequencer before a write operation]
    write_ram(port, board, "Amplitude", gaussian_array, Frequency=20, Amplitude=1, Phase=0, PLL_Multiplier=40, Show_RAM=True)
    start_ram(port, board)
    time.sleep(1)
    ram_profile_setting(port, board, 0,
    PLL_Multiplier=40, Amplitude_Ramp_Rate_Divider=1, Start_Address=0, End_Address=1000, No_Dwell_High=True, Zero_Crossing=False, Profile_Mode='Continuous Recirculate')



test_ram()