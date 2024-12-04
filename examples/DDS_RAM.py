from adriq.experiment import DDS_Ram
import time
# Initialize the DDS_Ram instance
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"

dds_ram_854_sp2 = DDS_Ram(
    port="COM10",
    board=3,
    mode="slave",
    pulse_sequencer_pin=11,
    detuning=0,
    calibration_file=calib_directory + r"\854_calib.csv",
    max_rf_power=15000
)

# Initialize the DDS
dds_ram_854_sp2.initialise()

# Define a RAM array (example values)
ram_array = [5000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]

# Assign the RAM array to the DDS instance
dds_ram_854_sp2.amplitude_array = ram_array

# Flash the DDS with the RAM array
# Start the timer
start_time = time.time()

# Execute the flash method
dds_ram_854_sp2.flash(ram_step=0.004)

# Stop the timer
end_time = time.time()

# Calculate the elapsed time
elapsed_time = end_time - start_time

print(f"Time taken to flash: {elapsed_time} seconds")
time.sleep(10)
dds_ram_854_sp2.set_amplitude(2)