import nidaqmx
import time
from adriq.pulse_sequencer import control_pulse_sequencer

def wait_for_high_input(channel_name, timeout):
    # Start the pulse sequencer
    control_pulse_sequencer(Port="COM5", Action="Start")

    # Create a task
    task = nidaqmx.Task()

    try:
        # Add a digital input channel
        task.di_channels.add_di_chan(channel_name)

        print(f"Waiting for input to go HIGH on {channel_name} for up to {timeout} seconds...")

        # Record the start time for timeout management
        start_time = time.time()

        # Main loop to wait for the input signal
        while True:
            # Read the state of the digital input
            input_state = task.read()
            print(input_state)
            # Check if the input signal is high
            if input_state:
                elapsed_time = time.time() - start_time
                print(f"Input high detected after {elapsed_time:.6f} seconds. Breaking out of loop.")
                break

            # Check if the timeout has been reached
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                print("Timeout reached. The input never went HIGH.")
                break

            # Optional: Sleep briefly to avoid busy-waiting and reduce CPU usage
            time.sleep(0.001)

    finally:
        # Stop and clear the task
        task.stop()
        task.close()

# Example usage
channel_name = '/Dev1/PFI9'  # Replace with actual DAQ input channel
timeout = 100  # Timeout in seconds
wait_for_high_input(channel_name, timeout)