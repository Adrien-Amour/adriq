import numpy as np
import matplotlib.pyplot as plt
from adriq.ad9910 import *
from adriq.pulse_sequencer import *
from adriq.Counters import *
import adriq.QuTau as QuTau
import numpy as np
from adriq.tdc_functions import filter_trailing_zeros, compute_time_diffs
from adriq.Servers import Server
import nidaqmx
import time
import keyboard



class DDS_Ram:
    """
    Represents a Direct Digital Synthesizer (DDS) used to modulate a laser beam through the use of an Acousto-Optic Modulator (AOM).
    
    In experiments utilizing this class, DDS will be operated in two modes: cooling and playback. 
    Whilst cooling, the DDS will use profile 0, which is the direct switch mode. 
    In this mode, the outputted frequency, phase, and amplitude remain constant. 
    This is achieved by setting all profile pins' inputs to 0.

    During playback, the DDS will switch to profile 1, also in direct switch mode, where the output frequency 
    and phase remain constant while the amplitude is modulated. 
    Switching between profiles is facilitated by a pulse sequencer connected to profile pin 1.
    
    The output from the associated pulse sequencer is stored in the `pulse_sequencer_pin` property of the class.
    The methods for initializing each DDS and flashing each one with its corresponding RAM array are defined within this class. 
    These RAM arrays should be constructed using methods from the Experiment class.

    Parameters:
    port (str): The COM port used to program the DDS.
    board (int): The board number of the DDS on the specified COM port.
    mode (str): The operational mode of the DDS (e.g., standalone, master, or slave).
    pulse_sequencer_pin (int): The pin on the pulse sequencer used to switch between DDS profiles.
    frequency (float): The output frequency of the DDS.
    """
    PLL_Multiplier = 40  # Default PLL multiplier value
    def __init__(self, port, board, mode, pulse_sequencer_pin, detuning, calibration_file: str, max_rf_power: int):
        # Initialization as previously defined.
        self.port = port
        self.board = board
        self.mode = mode
        self.pulse_sequencer_pin = pulse_sequencer_pin
        self.calibration_file = calibration_file
        self.max_rf_power = max_rf_power
        self.frequency = (200 - detuning / 2)  ##convert detuning (in MHz) to DDS output (in MHz). All ad9910 functions are in MHz
        self.phase = 0
        self.amplitude_array = None #array containing the fractional optical power values for ram playback
        self.flashed = False

    def initialise(self):
        """
        Initializes the DDS by calling the appropriate general setting function based on the mode.
        """
        if self.mode == 'standalone':
            general_setting_standalone(self.port, self.board)
        elif self.mode == 'master':
            general_setting_master(self.port, self.board)
        elif self.mode == 'slave':
            general_setting_slave(self.port, self.board)
        else:
            raise ValueError("Invalid mode. Mode must be 'standalone', 'master', or 'slave'.")

        self.initialised = True  # Mark as initialized after successful configuration

    def flash(self, ram_step):
        """
        Flashes the DDS with a RAM array using the write_ram function and sets profile configurations.
        
        Parameters:
        ram_array (list): The RAM data array to be flashed to the DDS.
        frequency (float, optional): Frequency modulation setting.
        amplitude (float, optional): Amplitude modulation setting.
        phase (float, optional): Phase modulation setting.
        pll_multiplier (int, optional): The PLL multiplier (default is 40).
        show_ram (bool, optional): Flag to show RAM contents (default is False).
        verbose (bool, optional): Flag for verbose output (default is False).
        """
        if not self.initialised:
            raise RuntimeError("DDS must be initialised before flashing.")
        ramp_rate_divider = ram_step / 0.004
        if not ramp_rate_divider.is_integer():
            raise ValueError("ramp_rate / 0.004 must result in an integer.")
        # Flash the RAM with the provided settings

        self.amplitude_array = np.array(self.amplitude_array, dtype=np.int64)
        # Flash the RAM with the provided settings
        write_ram(
            self.port,
            self.board,
            "Amplitude",
            self.amplitude_array,  # Pass the array of integer values
            Frequency=self.frequency,
            Amplitude=1,
            Phase=self.phase,
            Show_RAM=False
        )
        print(type(self.amplitude_array), type(self.amplitude_array[0]))
        start_ram(self.port, self.board) # because of firmware we have to start ram to actually flash the DDS
        # Set profile 0 to direct switch mode (start = 0, stop = 1)
        time.sleep(3)
        ram_profile_setting(self.port, self.board, 0, Start_Address=1, End_Address=1, Profile_Mode="Direct Switch")
        time.sleep(3)
        # Set profile 1 to playback mode (start = 1, stop = 1000)
        ram_profile_setting(self.port, self.board, 1, Amplitude_Ramp_Rate_Divider=int(ramp_rate_divider), Start_Address=2, End_Address=len(self.amplitude_array)-1, Profile_Mode="Ramp-Up", No_Dwell_High=True)
    
        self.flashed = True  # Mark as flashed after successfully setting profiles and uploading RAM

class Experiment_Runner:
    def __init__(self, timeout=10, pmt_threshold=None, sp_threshold=None):
        # Initialize QuTau_Reader with channels
        self.qutau_reader = Server.master(QuTau_Reader, max_que=5)
        

        # Optional thresholds
        self.pmt_threshold = pmt_threshold
        self.sp_threshold = sp_threshold

        self.pmt_counts = 0
        
        # Initialize other parts of the experiment as before
        self.task = nidaqmx.Task()
        self.channel_name = '/Dev1/PFI9'  # Replace with actual DAQ input channel
        self.task.di_channels.add_di_chan(self.channel_name)
        self.running = False  # Flag for running status
        self.timeout = timeout  # Timeout for the experiment

    def pause_experiment(self):
        self.qutau_reader.exit_experiment_mode()
        print("Experiment paused. Press P to resume.")
        while True:
            if keyboard.is_pressed('p'):
                print("Resuming the experiment...")
                self.running = True
                self.resume_experiment()
                break
            time.sleep(0.1)

    def resume_experiment(self):
        self.start_pulse_sequencer()
        pass

    def catch(self):
        return False

    def load(self):
        return False

    def start_experiment(self, N=None):
        self.running = True
        iteration = 0
        self.qutau_reader.enter_experiment_mode()
        
        # Calibrate run time on the first run
        self.calibrate_run_time()
        
        while self.running:
            if N is not None and iteration >= N:
                print("Reached the maximum number of iterations. Stopping experiment.")
                break

            self.start_pulse_sequencer()
            iteration += 1

            if keyboard.is_pressed('q'):
                print("Manual exit requested. Stopping experiment.")
                self.running = False
                break

            if keyboard.is_pressed('p'):
                print("Pause requested. Pausing experiment.")
                self.running = False
                self.pause_experiment()
                break

    def calibrate_run_time(self):
        print(f"Calibrating run time for input to go HIGH on {self.channel_name} for up to {self.timeout} seconds...")
        control_pulse_sequencer("COM5", "Start")
        start_time = time.time()

        while True:
            input_state = self.task.read()
            if input_state:
                self.run_time = time.time() - start_time
                print(f"Calibration complete. Run time: {self.run_time:.6f} seconds.")
                break

            elapsed_time = time.time() - start_time
            if elapsed_time >= self.timeout:
                print("Timeout reached during calibration. The input never went HIGH.")
                self.running = False
                break
            
            time.sleep(0.001)

    def start_pulse_sequencer(self):
        print(f"Waiting for input to go HIGH on {self.channel_name} for up to {self.timeout} seconds...")
        control_pulse_sequencer("COM5", "Start")
        
        # Sleep for the calibrated run time
        if self.run_time is not None:
            time.sleep(self.run_time)

        start_time = time.time()

        while True:
            input_state = self.task.read()
            if input_state:
                print("Input high detected. Breaking out of loop and running diagnostics...")
                break

            elapsed_time = time.time() - start_time
            if elapsed_time >= self.timeout:
                print("Timeout reached. The input never went HIGH. Pausing experiment.")
                self.running = False
                break
            
            time.sleep(0.001)

        self.qutau_reader.get_data()
        if self.running:
            self.run_diagnostics()
            if self.running:
                print("Diagnostics successful. Restarting pulse sequencer...")
            else:
                print("Diagnostics failed. Pausing experiment.")
                self.pause_experiment()
        else:
            self.pause_experiment()

    def run_diagnostics(self):
        laser_status = self.check_lasers()
        if not laser_status:
            print("Laser check failed. Pausing experiment.")
            self.running = False
            self.pause_experiment()
            self.discard_data()
            return
        
        self.qutau_reader.compute_time_diff()
        ion_status = self.check_ion()

        if ion_status:
            self.save_data()

        if not ion_status:
            self.discard_data()
            ion_status = self.catch()
            if not ion_status:
                ion_status = self.load()
                if not ion_status:
                    print("Ion check failed. Pausing experiment.")
                    self.running = False
                    self.pause_experiment()
                    return

        if ion_status:
            self.running = True

    def check_ion(self):
        if self.pmt_threshold is not None:
            # Calculate pmt_counts as the sum of the lengths of recent_time_diffs for all channels in mode "signal-f"
            pmt_counts = sum(len(ch.recent_time_diffs) for ch in self.qutau_reader.channels if ch.mode == "signal-f")
            print(f"PMT counts: {pmt_counts}")
            if pmt_counts < self.pmt_threshold:
                print(f"PMT counts ({pmt_counts}) below threshold ({self.pmt_threshold}).")
                return False

        if self.sp_threshold is not None:
            # Calculate sp_counts as the sum of the lengths of recent_time_diffs for all channels in mode "signal-sp"
            sp_counts = sum(len(ch.recent_time_diffs) for ch in self.qutau_reader.channels if ch.mode == "signal-sp")
            print(f"Single photon counts: {sp_counts}")
            if sp_counts < self.sp_threshold:
                print(f"Single photon counts ({sp_counts}) below threshold ({self.sp_threshold}).")
                return False

        print("Ion check passed.")
        return True

    def check_lasers(self):
        return True

    def save_data(self):
        """Save time differences for all active signal channels."""
        for ch in self.qutau_reader.channels:
            if ch.active and ch.mode in ["signal-f", "signal-sp"]:
                ch.save_recent_time_diffs()

    def discard_data(self):
        """Discard recent time differences for all active signal channels."""
        for ch in self.qutau_reader.channels:
            if ch.active and ch.mode in ["signal-f", "signal-sp"]:
                ch.discard_recent_time_diffs()

class Experiment_Builder:
    def __init__(self, dds_dictionary, ram_step=0.02, pulse_sequencer_port="COM5", N_Cycles=1E6, ps_end_pin=2, pmt_gate_pin=1, ps_sync_pin=0):
        if ram_step % 0.004 != 0:
            raise ValueError("ram_step must be a multiple of 0.004.")

        self.DDS_Dictionary = dds_dictionary
        self.cooling_section = None
        self.playback_sections = []
        self.ram_step = ram_step
        self.pulse_sequencer_port = pulse_sequencer_port
        # Store pulse sequencer properties
        self.pmt_gate_pin = pmt_gate_pin
        self.ps_sync_pin = ps_sync_pin
        self.ps_end_pin = ps_end_pin
        self.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called
        # Generate cooling pulse
        self.cooling_pulse = self._generate_pulse(state='cooling')

        # Check for pin conflicts
        dds_pins = {dds.pulse_sequencer_pin for dds in dds_dictionary.values()}
        if pmt_gate_pin in dds_pins:
            print("Warning: pmt_gate_pin overlaps with a DDS's pulse sequencer pin.")
        if ps_sync_pin in dds_pins:
            print("Warning: ps_sync_pin overlaps with a DDS's pulse sequencer pin.")
        if ps_end_pin in dds_pins:
            raise ValueError("ps_end_pin must not overlap with any DDS's pulse sequencer pin.")

        # Generate end pulse
        self.end_pulse = self._generate_pulse(state='end')
        
    def _generate_pulse(self, state, pmt_gate_high=False):
        """
        Generates a 16-bit string for the pulse sequencer output based on the state.
        
        Parameters:
        state (str): The state of the pulse ('cooling', 'playback', or 'end').

        Returns:
        str: A 16-bit binary string representing the pulse.
        """
        pulse = ['0'] * 16  # Start with all bits low
        
        if state == 'cooling':
            pulse[self.pmt_gate_pin] = '1'  # gate pmt during cooling
            pulse[self.ps_sync_pin] = '1'  # Set ps_sync_pin high for cooling to identify run start
        
        elif state == 'playback' and self.pmt_gate_pin is not None and pmt_gate_high:
            pulse[self.pmt_gate_pin] = '1'

        elif state == 'end':
            pulse[self.pmt_gate_pin] = '1'  # gate pmt at end of sequence
            pulse[self.ps_end_pin] = '1'

        for dds in self.DDS_Dictionary.values():
            if state == 'cooling':
                pulse[dds.pulse_sequencer_pin] = '0'  # Set DDS pins low for cooling
                pulse[self.pmt_gate_pin] = '1'  # gate pmt during cooling
                pulse[self.ps_sync_pin] = '1'  # Set ps_sync_pin high for cooling to identify run start
    
            elif state == 'playback':
                pulse[dds.pulse_sequencer_pin] = '1'  # Set DDS pins high for playback
        
            elif state == 'end':
                pulse[dds.pulse_sequencer_pin] = '0'  # Same as cooling, but with ps_end_pin high
                pulse[self.pmt_gate_pin] = '1'  # gate pmt at end of sequence
                pulse[self.ps_end_pin] = '1'

        return ''.join(pulse)

    def create_cooling_section(self, length, amplitude_dict):
        for key in amplitude_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        cooling_amplitudes = {key: amplitude_dict.get(key, 0) for key in self.DDS_Dictionary}
        self.cooling_section = {'length': length, 'amplitudes': cooling_amplitudes}

    def create_section(self, name, duration, dds_functions, pmt_gate_high=False):
        for key in dds_functions:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")

            # Check if pmt_gate_pin and ps_sync_pin are the same
            # we cannot switch between high and more than once, 
            # as we use each high signal from the sync to identify the run no. 
            if self.pmt_gate_pin == self.ps_sync_pin:
                # Check this is not the first playback section
                if self.playback_sections:
                    # Check the previous section's pmt_gate_high value
                    previous_section = self.playback_sections[-1]
                    if pmt_gate_high and not previous_section['pmt_gate_high']:
                        raise ValueError("pmt_gate_pin and ps_sync_pin are the same. pmt_gate_pin cannot go from HIGH to LOW back to HIGH within playback sections.")
                    #if the sync value already dropped 

        section_functions = {key: dds_functions.get(key, lambda t: 0) for key in self.DDS_Dictionary}
        self.playback_sections.append({
            'name': name,
            'duration': duration,
            'functions': section_functions,
            'pmt_gate_high': pmt_gate_high
        })

    def build_ram_arrays(self):
        """
        This method uses the functions associated to each DDS in each playback section to build the amplitude arrays for each DDS.
        """
        total_playback_length = sum(section['duration'] for section in self.playback_sections)
        # Print desired total playback length
        print(f"Intended Playback Length: {total_playback_length:.6f} µs")
        self.N_tot = 0

        for key, dds in self.DDS_Dictionary.items():
            # Initialize amplitude array for this DDS
            cooling_amplitude,_ = interpolate_rf_power(dds.calibration_file, dds.max_rf_power, self.cooling_section['amplitudes'][key], dds.frequency)
            dds.amplitude_array = [cooling_amplitude, cooling_amplitude]  #some boards only work with direct switch on ram word 1, also i added the zero as a safety net feature, in case no dwell high fails

        for section in self.playback_sections:
            name = section['name']
            duration = section['duration']
            
            # Calculate number of points based on the fixed ram_step
            num_points = int(duration / self.ram_step)
            self.N_tot += num_points
            # Calculate the effective playback length for this section
            effective_playback_length = num_points * self.ram_step
            
            # Print section details with name
            print(f"Section: {name}, Intended Duration: {duration:.6f} µs, Number of Points: {num_points}, Actual Duration: {effective_playback_length:.6f} µs")
            
            current_time = 0
            time_array = [current_time + i * self.ram_step for i in range(num_points)]
            
            # Collect amplitude values for this section
            for key, dds in self.DDS_Dictionary.items():
                fractional_power_array = [
                    section['functions'][key](t - current_time) for t in time_array
                ]
                amplitude_values = [
                    interpolate_rf_power(dds.calibration_file, dds.max_rf_power, f, dds.frequency)[0]
                    for f in fractional_power_array
                ]
            
                dds.amplitude_array.extend(amplitude_values)

            # Update current time to the end of this section
            current_time += effective_playback_length

    def plot_amplitude_arrays(self):
        plt.figure(figsize=(14, 7))
        
        # Calculate total playback length
        total_playback_length = sum(section['duration'] for section in self.playback_sections)
        
        # Create a time axis for the cooling period followed by the playback period
        cooling_length = self.cooling_section['length']
        num_playback_points = self.N_tot
        
        # Construct time axis starting from cooling_length and incrementing by ram_step
        time_axis = np.concatenate((
            np.array([0, cooling_length]),  # Start with the cooling points
            np.array([cooling_length + i * self.ram_step for i in range(num_playback_points)])  # Playback time axis
        ))

        # Add colored dashed lines to denote the start of each playback section, plotting first
        current_time = cooling_length
        line_colors = ['orange', 'green', 'purple', 'cyan']  # Array of colors for dashed lines
        color_index = 0

        for section in self.playback_sections:
            plt.axvline(x=current_time, color=line_colors[color_index % len(line_colors)], linestyle='--', linewidth=1.5, label=f"Start of {section['name']}")
            current_time += section['duration']
            color_index += 1

        # Add shaded areas for the cooling and playback pulses with reduced opacity
        plt.axvspan(0, cooling_length, color='lightblue', alpha=0.15, label='Cooling Pulse')
        plt.axvspan(cooling_length, cooling_length + total_playback_length, color='lightpink', alpha=0.15, label='Playback Pulse')

        # Plot each DDS's amplitude array
        for key, dds in self.DDS_Dictionary.items():
            # Check if amplitude_array is not all zeros
            if any(dds.amplitude_array):
                # Normalize the amplitude array to 1
                max_value = max(dds.amplitude_array)
                if max_value != 0:
                    normalized_array = [value / max_value for value in dds.amplitude_array]
                else:
                    normalized_array = dds.amplitude_array  # If max_value is 0, keep the array as is

                plt.plot(time_axis, normalized_array, label=f"{key} DDS")
            

        # Remove duplicate labels for the dashed lines in the legend
        handles, labels = plt.gca().get_legend_handles_labels()
        unique_handles_labels = dict(zip(labels, handles))
        plt.legend(unique_handles_labels.values(), unique_handles_labels.keys())

        # Plot styling
        plt.title('Amplitude Arrays of Each DDS')
        plt.xlabel('Time (µs)')
        plt.ylabel('Relative Amplitude')
        plt.grid(True)
        plt.show()

    def flash(self):
        """
        Calls the flash method of all DDS instances and writes to the pulse sequencer.
        Initializes each DDS before calling their flash method.
        """
        if self.pmt_gate_pin == self.ps_sync_pin and self.playback_sections:
            # Check if the last section's pmt_gate_high is True
            # This cant be the case if they share a pulse sequencer pin
            # we need it to go from LOW to HIGH at the start of each run, so that the QuTau
            # Can identify the start as a detection event.
            if self.playback_sections[-1]['pmt_gate_high']:
                raise ValueError("pmt_gate_pin and ps_sync_pin are the same. pmt_gate_pin cannot be HIGH in the last playback section.")

        control_pulse_sequencer(self.pulse_sequencer_port, 'Stop')  # always stop pulse sequencer before a write operation
        # Initialize each DDS instance before flashing
        for dds in self.DDS_Dictionary.values():
            dds.initialise()  # Ensure the DDS is initialized
            dds.flash(self.ram_step)  # Then flash the DDS

        # Construct the pulses and lengths for the pulse sequencer
        pulses = [self.cooling_pulse]
        pulse_lengths = [self.cooling_section['length']]

        for section in self.playback_sections:
            pulse = self._generate_pulse(
                state='playback',
                pmt_gate_high=section['pmt_gate_high']
            )
            pulses.append(pulse)
            pulse_lengths.append(section['duration'])


        # Debug prints for verification
        print(f"Pulses: {pulses}, End Pulse: {self.end_pulse}")
        print(f"Pulse Lengths: {pulse_lengths}")

        # Write to the pulse sequencer
        write_pulse_sequencer(
            Port=self.pulse_sequencer_port,  
            Pulses=pulses,
            Pulse_Lengths=pulse_lengths,
            Continuous=False,
            N_Cycles=self.N_Cycles,
            End_Pulse=self.end_pulse
        )
control_pulse_sequencer("COM5", 'Stop')
# # Create the dictionary of DDS instances
calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"

dds_dict = {
    # "master": DDS_Ram(
    #     port="COM9",
    #     board=0,
    #     mode="master",
    #     pulse_sequencer_pin=11,
    #     detuning=0,
    #     calibration_file=calib_directory + r"\866_calib.csv",
    #     max_rf_power=7800
    # ),
    "test": DDS_Ram(
        port="COM9",
        board=6,
        mode="standalone",
        pulse_sequencer_pin=11,
        detuning=0,
        calibration_file=calib_directory + r"\866_calib.csv",
        max_rf_power=7800
    )
}
# Create the ExperimentalSequence object
exp_sequence = Experiment_Builder(dds_dict)

# Create the cooling section (cool for 6 useconds)
# exp_sequence.create_cooling_section(length=6, amplitude_dict={"397c": 0.2, "854 SP1": 0.1, "850 SP1": 0.2})
exp_sequence.create_cooling_section(length=6, amplitude_dict={"test": 0.2})


# Create a Gaussian output function for DDS 397a
def gaussian(amplitude, width, centre):
    return lambda t: amplitude * np.exp(-((t - centre)**2) / (2 * width**2))


# Create op section 
exp_sequence.create_section(name="Optical Pumping", duration=8, dds_functions={
    # "test": lambda t: 0,
}, pmt_gate_high=True)

exp_sequence.create_section(name="Pump out of D3/2", duration=2, dds_functions={
    # "test": lambda t: 1,
}, pmt_gate_high=True)

exp_sequence.create_section(name="Single Photon", duration=10, dds_functions={
    # "test": gaussian(0.1, 0.6, 5),
}, pmt_gate_high=True)

exp_sequence.build_ram_arrays()

# Plot the amplitude arrays
exp_sequence.plot_amplitude_arrays()
exp_sequence.flash()


time.sleep(2)
print("starting...")
control_pulse_sequencer("COM5", 'Start')
time.sleep(20)
control_pulse_sequencer("COM5", 'Stop')



# # #needs some code to initialise 

# exp_runner = Experiment_Runner(
#     timeout=100,
#     pmt_threshold=1,
#     sp_threshold=None
# )

# exp_runner.start_experiment(N=10)


