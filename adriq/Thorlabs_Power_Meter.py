import numpy as np
import csv
from time import sleep
from .ad9910 import general_setting_standalone, single_tone_profile_setting
from ThorlabsPM100 import ThorlabsPM100
import pyvisa
from tqdm import tqdm
from scipy.special import erf, erfinv
import serial.tools.list_ports

def select_device(rm):
    while True:
        # List all available devices
        devices = rm.list_resources()
        print("\nAvailable Devices:")
        for idx, device in enumerate(devices):
            print(f"{idx}: {device}")

        # Prompt user for selection
        choice = input("\nEnter the number of the device to connect to, or 'r' to refresh the list: ").strip().lower()

        if choice == 'r':
            # Refresh the resource list
            print("Refreshing device list...\n")
            continue

        if choice.isdigit():
            choice = int(choice)
            if 0 <= choice < len(devices):
                return devices[choice]
            else:
                print("Invalid choice. Please select a valid device number.\n")
        else:
            print("Invalid input. Enter a number or 'r'.\n")

def set_averaging_count(power_meter):
    while True:
        try:
            # Prompt user to enter the averaging count
            count = int(input("\nEnter the number of counts to average over: ").strip())
            power_meter.sense.average.count = count  # Set the property
            print(f"Averaging count successfully set to: {power_meter.sense.average.count}")
            break
        except ValueError:
            print("Invalid input. Please enter a valid integer.\n")
        except Exception as e:
            print(f"Failed to set averaging count. Error: {e}\n")
            break

def generate_rf_points(max_rf_power, num_rf_points):
    # Create a normalized space from -1 to 1
    x_normalized = np.linspace(-1.5, 1.5, num_rf_points)

    # Transform with the inverse error function
    x_transformed = erf(x_normalized)
    print(x_transformed)
    # Normalize the transformed values back to the desired range [1, max_rf_power]
    rf_points = (x_transformed - x_transformed.min()) / (x_transformed.max() - x_transformed.min())
    rf_points = 1 + rf_points * (max_rf_power - 1)
    print(rf_points)
    # Convert to integers
    rf_points = np.round(rf_points).astype(int)
    print(rf_points)
    
    return rf_points

def calibrate_dds(port, board, profile, calibration_file, frequency_range, max_rf_power, power_meter, num_rf_points=200):
    """
    Calibrate the DDS by sweeping the frequency and RF power, and measuring the optical power.

    Parameters:
        port: Communication port for DDS
        board: DDS board identifier
        profile: DDS profile to use
        calibration_file: File to save the calibration results
        frequency_range: Iterable of frequencies to sweep (in MHz). This is the double pass frequency. I.e the frequency in the AOM is half this.
        max_rf_power: Maximum integer AD9910 RF power amplitude the AOM can take
        power_meter: Initialized ThorlabsPM100 power meter instance
        num_rf_points: Number of RF power points to sweep (default is 120)
    """
    general_setting_standalone(port, board)  # Set DDS to standalone mode
    results = []
    rf_power_points = generate_rf_points(max_rf_power, num_rf_points)
    print(rf_power_points)
    
    try:
        # Prepare data header with Max_RF_Power in the (0,0) element
        header = [['Max_RF_Power'] + [f'RF_Frac_{i}' for i in range(1, num_rf_points + 1)]]
        for freq in tqdm(frequency_range, desc="Frequency Sweep"):
            row = [freq]  # Start row with the frequency
            sleep(0.2)
            for rf_power in tqdm(rf_power_points, desc="RF Power Sweep", leave=False):
                # Retry mechanism for setting DDS parameters
                while True:
                    try:
                        single_tone_profile_setting(port, board, profile, Amplitude=int(rf_power), Frequency=int(freq)/2, Verbose=False)
                        break
                    except serial.SerialException as e:
                        if "PermissionError" in str(e):
                            print("Serial communication error: could not open port. Retrying...")
                            sleep(0.1)
                        else:
                            raise e
                # Fixed sleep to ensure stabilization
                sleep(0.02)
                # Measure the optical power
                N = 20
                total_power = 0
                for i in range(N):
                    while True:
                        try:
                            total_power += power_meter.read
                            break
                        except Exception as e:
                            if "VI_ERROR_IO" in str(e):
                                print("I/O error encountered. Retrying...")
                                sleep(0.1)
                            else:
                                raise e
                average_power = total_power / N
                row.append(average_power)  # Append average power measurement to row
            results.append(row)
        # Write results to a CSV file
        with open(calibration_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header with Max_RF_Power at (0,0)
            writer.writerow([max_rf_power] + [f'{rf_power/max_rf_power}' for rf_power in rf_power_points])
            writer.writerows(results)
        print(f"Calibration results saved to {calibration_file}")
    except Exception as e:
        print(f"Error during calibration: {e}")
    finally:
        # Set DDS to amplitude 0 and frequency 200 MHz
        single_tone_profile_setting(port, board, profile, Amplitude=0, Frequency=200, Verbose=False)
        print("DDS set to amplitude 0 and frequency 200 MHz")