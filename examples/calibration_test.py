from adriq.Thorlabs_Power_Meter import *


# List available COM ports
ports = list(serial.tools.list_ports.comports())
print("\nAvailable COM Ports:")
for port in ports:
    print(f"{port.device}: {port.description}")

# Prompt user for COM port, board number, and filename
port = input("\nEnter the COM port to use (e.g., COM9): ").strip()
board = int(input("Enter the DDS board number: ").strip())
calibration_file = input("Enter the filename to save the calibration results: ").strip()

rm = pyvisa.ResourceManager()
# Select a device from the list
resource_name = select_device(rm)
print(f"Selected device: {resource_name}")
pm100d = rm.open_resource(resource_name)
power_meter = ThorlabsPM100(pm100d)

# Define the parameters
profile = 0  # Assuming profile 0 is used
frequency_range = np.arange(410.5, 411, 0.5) # 
max_rf_power = int(input("\nEnter the max RF power the AOM can take: ").strip())

# Run the calibration
calibrate_dds(port, board, profile, calibration_file, frequency_range, max_rf_power, power_meter)