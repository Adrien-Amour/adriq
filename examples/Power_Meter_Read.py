import pyvisa
from ThorlabsPM100 import ThorlabsPM100

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

# Initialize resource manager
rm = pyvisa.ResourceManager()

# Select a device from the list
resource_name = select_device(rm)
print(f"Selected device: {resource_name}")

# Connect to the selected device
try:
    pm100d = rm.open_resource(resource_name)
    power_meter = ThorlabsPM100(inst=pm100d)
    set_averaging_count(power_meter)
    
    # Example usage
    print("\nPower Meter Read (Read-Only Property):", power_meter.read)

    # Set the averaging count

except Exception as e:
    print("Failed to connect to the selected device. Error:", e)
