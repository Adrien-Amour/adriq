import numpy as np
import matplotlib.pyplot as plt
from .ad9910 import *
from .pulse_sequencer import *
from .Counters import *
from .tdc_functions import filter_trailing_zeros, compute_time_diffs
from .Servers import Server
from .RedLabs_Dac import Redlabs_DAC
import nidaqmx
import time
import keyboard
from tqdm import tqdm



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
    def __init__(self, port, board, mode, pulse_sequencer_pin, calibration_file: str, max_rf_power: int):
        # Initialization as previously defined.
        self.port = port
        self.board = board
        self.mode = mode
        self.pulse_sequencer_pin = pulse_sequencer_pin
        self.calibration_file = calibration_file
        self.max_rf_power = max_rf_power
        self.frequency = 200
        self.trapping_frequency = None
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

        start_ram(self.port, self.board) # because of firmware we have to start ram to actually flash the DDS
        # Set profile 0 to direct switch mode (start = 0, stop = 1)
        ram_profile_setting(self.port, self.board, 0, Start_Address=2, End_Address=2, Profile_Mode="Direct Switch")
        # Set profile 1 to playback mode (start = 1, stop = 1000)
        ram_profile_setting(self.port, self.board, 1, Amplitude_Ramp_Rate_Divider=int(ramp_rate_divider), Start_Address=3, End_Address=len(self.amplitude_array)-1, Profile_Mode="Ramp-Up", No_Dwell_High=True)
    
        self.flashed = True  # Mark as flashed after successfully setting profiles and uploading RAM

    def set_frequency(self, frequency):
        set_ram_frequency(self.port, self.board, frequency)
    

    def enter_trapping_mode(self):
        if self.trapping_frequency:
            if self.frequency != self.trapping_frequency:
                self.set_frequency(self.trapping_frequency)
        ram_profile_setting(self.port, self.board, 0, Start_Address=1, End_Address=1, Profile_Mode="Direct Switch")

    def exit_trapping_mode(self): 
        if self.trapping_frequency:
            if self.frequency != self.trapping_frequency:
                self.set_frequency(self.frequency)
        
        ram_profile_setting(self.port, self.board, 0, Start_Address=2, End_Address=2, Profile_Mode="Direct Switch")
        


class Experiment_Builder:
    def __init__(self, dds_dictionary, ram_step=0.02, pulse_sequencer_port="COM5", N_Cycles=1E5, ps_end_pin=2, pmt_gate_pin=1, ps_sync_pin=0):
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

    def set_detunings(self, detuning_dict):
        for key in detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        detunings = {key: detuning_dict.get(key, 0) for key in self.DDS_Dictionary}
        for key, detuning in detunings.items():
            self.DDS_Dictionary[key].frequency = 200 + detuning / 2  # Assuming the same conversion as for detuning

            
    def set_trapping_parameters(self, trapping_detuning_dict, trapping_amplitude_dict):
        for key in trapping_detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        trapping_detunings = {key: trapping_detuning_dict.get(key, None) for key in self.DDS_Dictionary}
        trapping_amplitudes = {key: trapping_amplitude_dict.get(key, None) for key in self.DDS_Dictionary}
        
        self.trapping_parameters = {'detunings': trapping_detunings, 'amplitudes': trapping_amplitudes}
        for key, trapping_detuning in trapping_detunings.items():
            if trapping_detuning is not None:
                self.DDS_Dictionary[key].trapping_frequency = 200 + trapping_detuning / 2  # Assuming the same conversion as for detuning

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
            cooling_amplitude, _ = interpolate_rf_power(dds.calibration_file, dds.max_rf_power, self.cooling_section['amplitudes'][key], dds.frequency)
            if self.trapping_parameters['amplitudes'][key] is not None:
                trapping_amplitude, _ = interpolate_rf_power(dds.calibration_file, dds.max_rf_power, self.trapping_parameters['amplitudes'][key], dds.trapping_frequency)
            else:
                trapping_amplitude = cooling_amplitude  # Use cooling amplitude if trapping amplitude is not specified
            dds.amplitude_array = [trapping_amplitude, trapping_amplitude, cooling_amplitude]  # Initialize with trapping and cooling amplitudes

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
                amplitude_array = [dds.amplitude_array[2]] + dds.amplitude_array[2:]
                # Normalize the amplitude array to 1
                max_value = max(amplitude_array)
                if max_value != 0:
                    normalized_array = [value / max_value for value in amplitude_array]
                else:
                    normalized_array = amplitude_array  # If max_value is 0, keep the array as is
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

    def flash(self, Continuous=False):
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
        pulse_out(self.pulse_sequencer_port, self.end_pulse)
        control_pulse_sequencer(self.pulse_sequencer_port, 'Stop')  # always stop pulse sequencer before a write operation

        # Initialize each DDS instance before flashing
        dds_list = list(self.DDS_Dictionary.items())
        with tqdm(total=len(dds_list), desc="Flashing DDS", unit="DDS") as pbar:
            for dds_name, dds in dds_list:
                pbar.set_description(f"Flashing {dds_name}")
                dds.initialise()  # Ensure the DDS is initialized
                dds.flash(self.ram_step)  # Then flash the DDS
                pbar.update(1)

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
            Continuous=Continuous,
            N_Cycles=self.N_Cycles,
            End_Pulse=self.end_pulse
        )
                
        # print("allowing ion to resettle...")
        # input("Press Enter when the ion has resettled.")

class Experiment_Runner:
    def __init__(self, dds_dictionary, timeout=10, pmt_threshold=None, sp_threshold=None, expected_fluorescence=None, catch_timeout=10, load_timeout=100):
        # Initialize QuTau_Reader with channels
        self.qutau_reader = Server.master(QuTau_Reader, max_que=5)
        # Initialize clients for PMT_Reader and RedlabsDAC
        self.pmt_reader_client = Client(PMT_Reader)
        self.redlabs_dac_client = Client(Redlabs_DAC)
        self.dds_dictionary = dds_dictionary
        # Optional thresholds
        self.pmt_threshold = pmt_threshold
        self.sp_threshold = sp_threshold
        self.expected_fluorescence = expected_fluorescence

        self.pmt_counts = 0
    
        # Initialize other parts of the experiment as before
        self.task = nidaqmx.Task()
        self.channel_name = '/Dev1/PFI9'  # Replace with actual DAQ input channel
        self.task.di_channels.add_di_chan(self.channel_name)

        #Flags
        self.running = False  # Flag for running status
        self.loading = False  # Flag for loading status
        self.single_ion = False # Flag for single ion detection

        # Timeouts
        self.timeout = timeout  # Timeout for the experiment
        self.catch_timeout = catch_timeout
        self.load_timeout = load_timeout

    def pause_experiment(self):
        self.running = False
        self.qutau_reader.exit_experiment_mode()
        print("Experiment paused. Press P to resume.")
        while True:
            if keyboard.is_pressed('p'):
                print("Resuming the experiment...")
                self.resume_experiment()
                break
            time.sleep(0.1)

    def resume_experiment(self):
        self.running = True
        trapped = self.single_ion_check()
        if not trapped:
            trapped = self.load_loop()
            if trapped:
                self.start_pulse_sequencer()

            if not trapped:
                self.pause_experiment()
                return
        else:
            self.start_pulse_sequencer()
        pass

    def catch(self):
        for dds in self.dds_dictionary.values():
            dds.enter_trapping_mode()
        start_time = time.time()
        rate = self.pmt_reader_client.get_rate()
        trapped = False
        self.catching = True
        try:
            while self.catching and (time.time() - start_time < self.catch_timeout):
                # Get counts from the PMT_Reader
                counts = self.pmt_reader_client.get_counts()
                if counts:
                    # Check the average of recent counts
                    counts = counts[1]['PMT']
                    recent_counts = counts[-3:]  # Assuming counts is a list of values
                    avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
                    lower_bound = self.expected_fluorescence * 0.8
                    upper_bound = self.expected_fluorescence * 1.2
                    print(avg_counts)
                    if lower_bound <= avg_counts <= upper_bound:
                        print(f"Recent PMT counts ({avg_counts}) within 20% of expected fluorescence ({self.expected_fluorescence}).")
                        print("Caught ion.")
                        trapped = True
                        break
                    else:
                        print(f"Recent PMT counts ({avg_counts}) not within 20% of expected fluorescence ({self.expected_fluorescence}). Retrying...")
                
                # Sleep based on PMT_Reader's rate
                time.sleep(1 / rate)
        finally:
            self.stop_catch()
        return trapped
    
    def stop_catch(self):
        # Reset the DAC pins
        self.catching = False

    def load_loop(self, N_attempts=5):
        loop = 0
        ion_status = False  # Initialize ion_status before using it in the loop condition
        while not ion_status and loop < N_attempts:
            loop += 1
            ion_status = self.load()
            if ion_status:
                print("Ion loading succeeded.")
                return True
        print("Ion loading failed after maximum attempts. Pausing experiment.")
        return False

    def load(self):
        """
        this method will attempt to load ions into the trap, for some time load_timeout.
        If it succeeds in loading something it will check that this is a single ion. If it is not it will discard the ions and return false.
        If it doesnt succeed it will return false.
        """
        for dds in self.dds_dictionary.values():
            dds.enter_trapping_mode()
        counting = self.pmt_reader_client.get_counting()
        if not counting:
            self.pmt_reader_client.start_counting()
        try:
            self.redlabs_dac_client.start_oven()
            self.redlabs_dac_client.open_pi_shutter()
        except Exception as e:
            print(f"Failed to initialize digital pins: {e}")
            return
        self.redlabs_dac_client.set_trap_depth(0.8)
        self.loading = True
        rate = self.pmt_reader_client.get_rate()
        trapped = False
        start_time = time.time()
        try:
            while self.loading and (time.time() - start_time < self.load_timeout):
                # Get counts from the PMT_Reader
                counts = self.pmt_reader_client.get_counts()
                if counts:
                    # Check the average of recent counts
                    counts = counts[1]['PMT']
                    recent_counts = counts[-3:]  # Assuming counts is a list of values
                    avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
                    if avg_counts > self.pmt_threshold:
                        print(avg_counts)
                        print(self.pmt_threshold)
                        trapped = self.single_ion_check()
                        self.redlabs_dac_client.set_trap_depth(1.2)
                        break

                # Sleep based on PMT_Reader's rate
                time.sleep(1 / rate)
        finally:
            self.stop_load()

        return trapped
    

    def single_ion_check(self):
        """
        Checks if there is a single ion in the trap by checking the pmt counts are in an acceptable range
        """
        if not self.expected_fluorescence:
            return True
        else:
            for attempt in range(5):
                counts = self.pmt_reader_client.get_counts()
                counts = counts[1]['PMT']
                recent_counts = counts[-3:]
                avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
                lower_bound = self.expected_fluorescence * 0.8
                upper_bound = self.expected_fluorescence * 1.2
                print(avg_counts)
                if lower_bound <= avg_counts <= upper_bound:
                    print(f"Recent PMT counts ({avg_counts}) within 20% of expected fluorescence ({self.expected_fluorescence}).")
                    return True
                else:
                    print(f"Recent PMT counts ({avg_counts}) not within 20% of expected fluorescence ({self.expected_fluorescence}). Retrying ({attempt + 1}/5)...")
                    time.sleep(1)
            print(f"Failed to get PMT counts within 20% of expected fluorescence after 5 attempts.")
            self.redlabs_dac_client.set_trap_depth(0)
            time.sleep(1)
            self.redlabs_dac_client.set_trap_depth(0.8)
            return False
    
    def stop_load(self):
        # Reset the DAC pins
        for dds in self.dds_dictionary.values():
            dds.exit_trapping_mode()
        self.loading = False
        try:
            self.redlabs_dac_client.reset_pins()
        except Exception as e:
            print(f"Failed to reset DAC pins: {e}")

    def start_experiment(self, N=None):
        for dds in self.dds_dictionary.values():
            dds.exit_trapping_mode()
        self.running = True
        iteration = 0
        self.qutau_reader.enter_experiment_mode()
        # Calibrate run time on the first run
        self.calibrate_run_time()
        iteration += 1 # Increment iteration after calibration run
        try:
            while self.running:
                if N is not None and iteration >= N: #stop after N runs
                    print("Reached the maximum number of iterations. Stopping experiment.")
                    self.qutau_reader.exit_experiment_mode()
                    break

                self.start_pulse_sequencer()
                iteration += 1 # Increment iteration after each run

                if keyboard.is_pressed('q'):
                    print("Manual exit requested. Stopping experiment.")
                    self.running = False
                    self.qutau_reader.exit_experiment_mode()
                    break

                if keyboard.is_pressed('p'):
                    print("Pause requested. Pausing experiment.")
                    self.running = False
                    self.pause_experiment()
                    break
        except KeyboardInterrupt:
            print("Experiment interrupted. Exiting experiment mode.")
            self.qutau_reader.exit_experiment_mode()
            self.running = False
    
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
            
            time.sleep(0.0001)

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
                trapped = self.load_loop()
                if trapped:
                    return
                if not trapped:
                    self.pause_experiment()
                    return
            
    def check_ion(self):
        if self.pmt_threshold is not None:
            # Calculate pmt_counts as the sum of the lengths of recent_time_diffs for all channels in mode "signal-f"
            counts = self.pmt_reader_client.get_counts()
            counts = counts[1]['PMT']
            recent_counts = counts[-3:]  # Assuming counts is a list of values
            avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
            if avg_counts < self.pmt_threshold:
                print(f"Recent PMT counts ({avg_counts}) below threshold ({self.pmt_threshold}).")
                return False
        return True
    
    def check_cavity(self):
        if self.sp_threshold is not None:
            # Calculate sp_counts as the sum of the lengths of recent_time_diffs for all channels in mode "signal-sp"
            sp_counts = sum(len(ch.recent_time_diffs) for ch in self.qutau_reader.channels if ch.mode == "signal-sp")
            print(f"Single photon counts: {sp_counts}")
            if sp_counts < self.sp_threshold:
                print(f"Single photon counts ({sp_counts}) below threshold ({self.sp_threshold}).")
                return False

        print("Ion check passed.")

    def check_lasers(self):
        return True

    def save_data(self):
        self.qutau_reader.save_recent_time_diffs()

    def discard_data(self):
        self.qutau_reader.discard_recent_time_diffs()
    
        
    def clear_channels(self):
        self.qutau_reader.clear_channels()

    def plot_time_diffs_histogram(self, mode, lower_cutoff=None, upper_cutoff=None):
        """
        Plot histograms of the time_diffs attribute for all channels with the specified mode.
        
        Parameters:
        mode (str): The mode of the channels to plot.
        lower_cutoff (float, optional): The minimum time difference to include in the plot (in microseconds).
        upper_cutoff (float, optional): The maximum time difference to include in the plot (in microseconds).
        """
        # Find all channels with the specified mode
        channels = [ch for ch in self.qutau_reader.channels if ch.mode == mode]
        if not channels:
            print(f"No channels found with mode {mode}.")
            return

        # Plot histograms for each channel
        for channel in channels:
            time_diffs_us = np.array(channel.time_diffs) * 1E6  # Convert to NumPy array and multiply by 1E6
            
            # Apply lower cutoff if specified
            if lower_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us >= lower_cutoff]
            
            # Apply upper cutoff if specified
            if upper_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us <= upper_cutoff]
            
            plt.figure(figsize=(10, 6))
            plt.hist(time_diffs_us, bins=50, edgecolor='black')
            plt.title(f'Histogram of Time Differences for Channel {channel.name}')
            plt.xlabel('Time Difference (μs)')
            plt.ylabel('Frequency')
            plt.grid(True)
            plt.show()

    def get_counts_in_window(self, mode, lower_cutoff=None, upper_cutoff=None):
        """
        Get the total number of counts within the specified window for all channels with the specified mode.
        
        Parameters:
        mode (str): The mode of the channels to get counts for.
        lower_cutoff (float, optional): The minimum time difference to include in the counts (in microseconds).
        upper_cutoff (float, optional): The maximum time difference to include in the counts (in microseconds).
        
        Returns:
        dict: A dictionary with channel names as keys and the total number of counts within the window as values.
        """
        # Find all channels with the specified mode
        channels = [ch for ch in self.qutau_reader.channels if ch.mode == mode]
        if not channels:
            print(f"No channels found with mode {mode}.")
            return {}

        counts_in_window = {}

        # Get counts for each channel
        for channel in channels:
            time_diffs_us = np.array(channel.time_diffs) * 1E6  # Convert to NumPy array and multiply by 1E6
            
            # Apply lower cutoff if specified
            if lower_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us >= lower_cutoff]
            
            # Apply upper cutoff if specified
            if upper_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us <= upper_cutoff]
            
            # Calculate the total number of counts within the window
            counts_in_window[channel.name] = len(time_diffs_us)
        
        return counts_in_window

