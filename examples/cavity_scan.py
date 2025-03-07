import time
import numpy as np
import matplotlib.pyplot as plt
from adriq.experiment import DDS_Singletone
from adriq.QuTau import QuTau


# Function to initialize DDS with retry logic
def initialize_dds(port, board, mode, pulse_sequencer_pin, calibration_file):
    while True:
        try:
            dds = DDS_Singletone(
                port=port,
                board=board,
                mode=mode,
                pulse_sequencer_pin=pulse_sequencer_pin,
                calibration_file=calibration_file
            )
            dds.initialise()
            return dds
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

# Initialize DDS
dds = initialize_dds(
    port="COM9",
    board=0,
    mode="standalone",
    pulse_sequencer_pin=15,
    calibration_file=r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\AOM_Calibrations\854Cav_calib.csv"
)

# Initialize QuTau
qutau = QuTau()
devType = qutau.getDeviceType()

if devType == qutau.DEVTYPE_1A:
    print("found quTAU!")
elif devType == qutau.DEVTYPE_1B:
    print("found quTAU(H)!")
elif devType == qutau.DEVTYPE_1C:
    print("found quPSI!")
elif devType == qutau.DEVTYPE_2A:
    print("found quTAG!")
else:
    print("no suitable device found - demo mode activated")

print("Device timebase:", qutau.getTimebase())


qutau.setBufferSize(1000000)
qutau.enableChannels((2, 3))

# Scan parameters
detuning_start = 9
detuning_end = 13
detuning_step = 0.02
amplitude = 100
scan_duration = 0.1  # seconds
num_readings = 20

detunings = np.arange(detuning_start, detuning_end, detuning_step)
channel2_count_rates = []
channel3_count_rates = []

# Perform scan
for detuning in detunings:
    frequency = 200 + detuning / 2
    dds.set_profile(0, frequency=frequency, amplitude=amplitude)
    dds.flash()
    
    channel2_counts_list = []
    channel3_counts_list = []
    
    for _ in range(num_readings):
        # Collect timestamps for the specified duration
        qutau.getLastTimestamps(True)  # Clear previous timestamps
        time.sleep(scan_duration)
        timestamps = qutau.getLastTimestamps(True)
        
        tstamp = timestamps[0]
        tchannel = timestamps[1]
        values = timestamps[2]
        
        channel2_counts = np.sum(tchannel == 2)
        channel3_counts = np.sum(tchannel == 3)
        
        channel2_counts_list.append(channel2_counts)
        channel3_counts_list.append(channel3_counts)
    
    # Average the counts over the readings
    avg_channel2_counts = np.mean(channel2_counts_list)
    avg_channel3_counts = np.mean(channel3_counts_list)
    
    channel2_count_rate = avg_channel2_counts / scan_duration
    channel3_count_rate = avg_channel3_counts / scan_duration
    
    channel2_count_rates.append(channel2_count_rate)
    channel3_count_rates.append(channel3_count_rate)
    
    print(f"Detuning: {detuning}, Channel 2 Count Rate: {channel2_count_rate}, Channel 3 Count Rate: {channel3_count_rate}")

# Deinitialize QuTau
qutau.deInitialize()

# Plot count rate vs. detuning for each channel on separate graphs
plt.figure()

# Plot for Channel 2
plt.subplot(2, 1, 1)
plt.plot(detunings, channel2_count_rates, marker='o', label='Channel 2')
plt.xlabel('Detuning')
plt.ylabel('Count Rate (counts/s)')
plt.title('Count Rate vs. Detuning for Channel 2')
plt.grid(True)

# Plot for Channel 3
plt.subplot(2, 1, 2)
plt.plot(detunings, channel3_count_rates, marker='x', label='Channel 3')
plt.xlabel('Detuning')
plt.ylabel('Count Rate (counts/s)')
plt.title('Count Rate vs. Detuning for Channel 3')
plt.grid(True)

plt.tight_layout()
plt.show()