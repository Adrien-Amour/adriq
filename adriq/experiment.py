import numpy as np
import matplotlib.pyplot as plt
import sys
from .ad9910 import *
from .pulse_sequencer import *
from .Counters import *
from .tdc_functions import filter_trailing_zeros, compute_time_diffs, filter_runs
from .Servers import Server
from .RedLabs_Dac import Redlabs_DAC
import nidaqmx
import time
import keyboard
from tqdm import tqdm

import configparser
import os


class DDS_Singletone:
    PLL_MULTIPLIER = 40
    VALID_MODES = {'master', 'slave', 'standalone'}

    def __init__(self, port: str, board: int, mode: str, pulse_sequencer_pin: int, calibration_file: str):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}' for laser {name}. Valid modes are: {', '.join(self.VALID_MODES)}")
        
        self.port = port
        self.mode = mode
        self.board = board
        self.pulse_sequencer_pin = pulse_sequencer_pin
        self.calibration_file = calibration_file
        self._profiles = []  # Initialize as an empty list
        self._new_profiles = []  # Initialize as an empty list for new profiles
        self.trapping_profile = None  # Initialize trapping profile

    def initialise(self):
        """Apply general settings based on the mode."""
        if self.mode == 'master':
            general_setting_master(self.port, self.board)
        elif self.mode == 'slave':
            general_setting_slave(self.port, self.board)
        elif self.mode == 'standalone':
            general_setting_standalone(self.port, self.board)
        else:
            raise ValueError(f"Unknown mode {self.mode} for laser {self.name}.")

    def set_profile(self, profile: int, frequency=200, amplitude=0, phase=0):
        if profile not in [0, 1]:
            raise ValueError("Profile must be 0 or 1.")
        if not (0 <= frequency <= 400):
            raise ValueError("Frequency must be between 0 and 400.")
        if not isinstance(amplitude, int):
            print(amplitude)
            raise ValueError("Amplitude must be an integer.")
        if not isinstance(phase, int):
            raise ValueError("Phase must be an integer.")
        
        # Ensure the list has enough space for the profile
        while len(self._new_profiles) <= profile:
            self._new_profiles.append({'frequency': 200, 'amplitude': 0, 'phase': 0})

        self._new_profiles[profile] = {
            'frequency': frequency,
            'amplitude': amplitude,
            'phase': phase
        }

    def flash(self):
        """Apply the single tone profile settings for all profiles that have changed."""
        for profile, new_settings in enumerate(self._new_profiles):
            if profile < len(self._profiles):
                old_settings = self._profiles[profile]
            else:
                old_settings = None

            if old_settings != new_settings:
                single_tone_profile_setting(
                    Port=self.port,
                    Board=self.board,
                    Profile=profile,
                    PLL_Multiplier=self.PLL_MULTIPLIER,
                    Amplitude=new_settings['amplitude'],
                    Phase_Offset=new_settings['phase'],
                    Frequency=new_settings['frequency'],
                    Verbose=False
                )

        # Replace the old profiles with the new profiles
        self._profiles = self._new_profiles.copy()
        # Clear the new profiles dictionary
        self._new_profiles = []

    def clear_profiles(self):
        """Clear all profiles."""
        self._profiles = []
        self._new_profiles = []

    def set_trapping_profile(self, frequency, amplitude):
        """Set the trapping profile."""
        self.trapping_frequency = frequency
        self.trapping_amplitude = amplitude
        self.trapping_profile = {
            'frequency': frequency,
            'amplitude': amplitude,
            'phase': 0  # Assuming phase is 0 for trapping profile
        }

    def enter_trapping_mode(self):
        """Enter trapping mode using the trapping profile."""
        if self.trapping_profile is not None:
            profile_0 = self._profiles[0]
            if (
                profile_0['frequency'] != self.trapping_profile['frequency']
                or profile_0['amplitude'] != self.trapping_profile['amplitude']
            ):
                single_tone_profile_setting(
                    Port=self.port,
                    Board=self.board,
                    Profile=0,
                    PLL_Multiplier=self.PLL_MULTIPLIER,
                    Amplitude=self.trapping_profile['amplitude'],
                    Phase_Offset=self.trapping_profile['phase'],
                    Frequency=self.trapping_profile['frequency'],
                    Verbose=False
                )

    def exit_trapping_mode(self):
        """Exit trapping mode and restore the original profile 0 settings."""
        if self.trapping_profile is not None:
            original_profile = self._profiles[0]
            if (
                original_profile['frequency'] != self.trapping_profile['frequency']
                or original_profile['amplitude'] != self.trapping_profile['amplitude']
            ):
                single_tone_profile_setting(
                    Port=self.port,
                    Board=self.board,
                    Profile=0,
                    PLL_Multiplier=self.PLL_MULTIPLIER,
                    Amplitude=original_profile['amplitude'],
                    Phase_Offset=original_profile['phase'],
                    Frequency=original_profile['frequency'],
                    Verbose=False
                )

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
    
    the object also stores trapping frequency and amplitude values, which can be set using the set_trapping_parameters method.

    Parameters:
    port (str): The COM port used to program the DDS.
    board (int): The board number of the DDS on the specified COM port.
    mode (str): The operational mode of the DDS (e.g., standalone, master, or slave).
    pulse_sequencer_pin (int): The pin on the pulse sequencer used to switch between DDS profiles.
    frequency (float): The output frequency of the DDS.
    """
    PLL_Multiplier = 40  # Default PLL multiplier value
    def __init__(self, port, board, mode, pulse_sequencer_pin, calibration_file: str):
        # Initialization as previously defined.
        self.port = port
        self.board = board
        self.mode = mode
        self.pulse_sequencer_pin = pulse_sequencer_pin
        self.calibration_file = calibration_file
        data = np.loadtxt(self.calibration_file, delimiter=',', skiprows=0)
        # Extract the Max_RF_Power from the first element

        self.frequency = 200
        self.trapping_frequency = None
        self.phase = 0
        self.amplitude_array = None #array containing the fractional optical power values for ram playback
        self.flashed = False
        self.edited = True 

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
        if self.edited:
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
            self.edited = False  # Reset the edited flag after flashing

    def set_frequency(self, frequency):
        set_ram_frequency(self.port, self.board, frequency)
    
    def set_phase(self, phase):
        set_ram_phase(self.port, self.board, phase)

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

def load_dds_dict(mode: str, dds_config: str):
    # Initialize the configuration dictionary based on the mode
    dds_dict = {}
 
    # Load the configuration file
    config = configparser.ConfigParser()
    if not os.path.exists(dds_config):
        raise FileNotFoundError(f"Config file not found: {dds_config}")
    config.read(dds_config)
    
    # Check that the mode is either 'ram' or 'singletone'
    if mode not in ['ram', 'singletone']:
        raise ValueError("Mode must be either 'ram' or 'singletone'")
    
    # Iterate through the sections of the config file to populate the DDS dictionary
    for section in config.sections():
        port = config[section].get("port")
        board = int(config[section].get("board"))
        config_mode = config[section].get("mode")  # Use a different variable name
        pulse_sequencer_pin = int(config[section].get("pulse_sequencer_pin"))
        # Directly retrieve the calibration file path (it's fully specified now)
        calibration_file = config[section].get("calibration_file")
        
        if mode == 'singletone':
            dds_dict[section] = DDS_Singletone(
                port=port,
                board=board,
                mode=config_mode,  # Use the mode from the config file
                pulse_sequencer_pin=pulse_sequencer_pin,
                calibration_file=calibration_file
            )
        elif mode == 'ram':  # Default to DDS_Ram
            dds_dict[section] = DDS_Ram(
                port=port,
                board=board,
                mode=config_mode,  # Use the mode from the config file
                pulse_sequencer_pin=pulse_sequencer_pin,
                calibration_file=calibration_file
            )
    return dds_dict

class Pulse_Sequencer:
    def __init__(self, port="COM5", ps_end_pin=2, pmt_gate_pin=1, ps_sync_pin=0):
        """
        Initializes the PulseSequencer instance.

        Args:
            port (str): Serial port for the pulse sequencer.
            ps_end_pin (int): End pulse pin index.
            pmt_gate_pin (int): PMT gate pin index.
            ps_sync_pin (int): Sync pulse pin index.
        """
        self.port = port
        self.ps_end_pin = ps_end_pin
        self.pmt_gate_pin = pmt_gate_pin
        self.ps_sync_pin = ps_sync_pin
        
        self._pulses = []  # Placeholder for pulse patterns
        self._pulse_lengths = []  # Placeholder for pulse durations
        self._new_pulses = []  # Placeholder for new pulse patterns
        self._new_pulse_lengths = []  # Placeholder for new pulse durations
        self.N_Cycles = 1  # Default number of cycles
        self.end_pulse = None  # Default end pulse
        self._new_end_pulse = None  # Placeholder for new end pulse
        self.gated_fraction = 0  # Fraction of time PMT is gated

    def start(self):
        """
        Starts the pulse sequencer.
        """
        control_pulse_sequencer(self.port, 'Start')

    def stop(self):
        """
        Stops the pulse sequencer.
        """
        control_pulse_sequencer(self.port, 'Stop')

    def write_sequence(self, Continuous=False):
        """
        Writes the pulse sequence to the pulse sequencer and calculates the gated fraction.
        """
        # Ensure pulse lengths are valid
        if not self._new_pulses or not self._new_pulse_lengths or len(self._new_pulses) != len(self._new_pulse_lengths):
            raise ValueError("New pulses and new pulse lengths must be defined and of the same length.")

        # Calculate the gated fraction
        total_time = sum(self._new_pulse_lengths)
        gated_time = sum(
            length for pulse, length in zip(self._new_pulses, self._new_pulse_lengths) 
            if pulse[self.pmt_gate_pin] == '1'
        )

        self.gated_fraction = gated_time / total_time if total_time > 0 else 0

        self.sequence_length = total_time
        print(f"Total time: {total_time:.6f} µs, Gated time: {gated_time:.6f} µs, Gated fraction: {self.gated_fraction:.2f}")

        # Check if any of the new variables are different from the old ones
        if (self._pulses != self._new_pulses or 
            self._pulse_lengths != self._new_pulse_lengths or 
            self.end_pulse != self._new_end_pulse):
            print("Writing new pulse sequence to the pulse sequencer")
            print("New pulses:", self._new_pulses)
            print("New pulse lengths:", self._new_pulse_lengths)
            print("New end pulse:", self._new_end_pulse)
            # Write the pulse sequence
            write_pulse_sequencer(
                Port=self.port,  
                Pulses=self._new_pulses,
                Pulse_Lengths=self._new_pulse_lengths,
                Continuous=Continuous,
                N_Cycles=self.N_Cycles,
                End_Pulse=self._new_end_pulse
            )

            # Replace the old pulses with the new pulses
            self._pulses = self._new_pulses.copy()
            self._pulse_lengths = self._new_pulse_lengths.copy()
            self.end_pulse = self._new_end_pulse

        # Clear the new pulses and new pulse lengths
        self._new_pulses = []
        self._new_pulse_lengths = []
        self._new_end_pulse = None

class Experiment_Builder:
    def __init__(self, dds_dictionary, pulse_sequencer, ram_step=0.02, N_Cycles=1E5):
        if ram_step % 0.004 != 0:
            raise ValueError("ram_step must be a multiple of 0.004.")

        self.DDS_Dictionary = dds_dictionary
        self.cooling_section = None
        self.playback_sections = []
        self.ram_step = ram_step

        self.pulse_sequencer = pulse_sequencer
        self.pulse_sequencer.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called

        self.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called
        # Generate cooling pulse
        self.cooling_pulse = self._generate_pulse(state='cooling')

        # Check for pin conflicts
        dds_pins = {dds.pulse_sequencer_pin for dds in dds_dictionary.values()}
        if self.pulse_sequencer.pmt_gate_pin in dds_pins:
            print("Warning: pmt_gate_pin overlaps with a DDS's pulse sequencer pin.")
        if self.pulse_sequencer.ps_sync_pin in dds_pins:
            print("Warning: ps_sync_pin overlaps with a DDS's pulse sequencer pin.")
        if self.pulse_sequencer.ps_end_pin in dds_pins:
            raise ValueError("ps_end_pin must not overlap with any DDS's pulse sequencer pin.")



        
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
            pulse[self.pulse_sequencer.pmt_gate_pin] = '1'  # gate pmt during cooling
            pulse[self.pulse_sequencer.ps_sync_pin] = '1'  # Set ps_sync_pin high for cooling to identify run start
        
        elif state == 'playback' and self.pulse_sequencer.pmt_gate_pin is not None and pmt_gate_high:
            pulse[self.pulse_sequencer.pmt_gate_pin] = '1'

        elif state == 'end':
            pulse[self.pulse_sequencer.pmt_gate_pin] = '1'  # gate pmt at end of sequence
            pulse[self.pulse_sequencer.ps_end_pin] = '1'

        for dds in self.DDS_Dictionary.values():
            if state == 'cooling':
                pulse[dds.pulse_sequencer_pin] = '0'  # Set DDS pins low for cooling
                pulse[self.pulse_sequencer.pmt_gate_pin] = '1'  # gate pmt during cooling
                pulse[self.pulse_sequencer.ps_sync_pin] = '1'  # Set ps_sync_pin high for cooling to identify run start
    
            elif state == 'playback':
                pulse[dds.pulse_sequencer_pin] = '1'  # Set DDS pins high for playback
        
            elif state == 'end':
                pulse[dds.pulse_sequencer_pin] = '0'  # Same as cooling, but with ps_end_pin high
                pulse[self.pulse_sequencer.pmt_gate_pin] = '1'  # gate pmt at end of sequence
                pulse[self.pulse_sequencer.ps_end_pin] = '1'

        return ''.join(pulse)

    def set_detunings(self, detuning_dict):
        for key in detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        detunings = {key: detuning_dict[key] for key in detuning_dict if key in self.DDS_Dictionary}
        for key, detuning in detunings.items():
            self.DDS_Dictionary[key].frequency = 200 + detuning / 2  # Assuming the same conversion as for detuning

    def edit_detunings(self, detuning_dict):
        for key in detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        detunings = {key: detuning_dict[key] for key in detuning_dict if key in self.DDS_Dictionary}
        for key, detuning in detunings.items():
            self.DDS_Dictionary[key].frequency = 200 + detuning / 2  # Assuming the same conversion as for detuning
            self.DDS_Dictionary[key].edited = True

    def set_phases(self, phases_dict):
        for key in phases_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
       
        phases = {key: phases_dict[key] for key in phases_dict if key in self.DDS_Dictionary}
        for key, phase in phases.items():
            self.DDS_Dictionary[key].phase = phase
 
    def edit_phases(self, phases_dict):
        for key in phases_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
       
        phases = {key: phases_dict[key] for key in phases_dict if key in self.DDS_Dictionary}
        for key, phase in phases.items():
            self.DDS_Dictionary[key].phase = phase
            self.DDS_Dictionary[key].set_phase(phase)
               
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

    def edit_trapping_parameters(self, trapping_detuning_dict, trapping_amplitude_dict):
        if not hasattr(self, 'trapping_parameters'):
            self.trapping_parameters = {'detunings': {}, 'amplitudes': {}}
        
        for key in trapping_detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        for key, trapping_detuning in trapping_detuning_dict.items():
            if key in self.DDS_Dictionary:
                self.trapping_parameters['detunings'][key] = trapping_detuning
                self.DDS_Dictionary[key].trapping_frequency = 200 + trapping_detuning / 2  # Assuming the same conversion as for detuning
                self.DDS_Dictionary[key].edited = True
        
        for key, trapping_amplitude in trapping_amplitude_dict.items():
            if key in self.DDS_Dictionary:
                self.trapping_parameters['amplitudes'][key] = trapping_amplitude
                self.DDS_Dictionary[key].edited = True

    def create_cooling_section(self, length, amplitude_dict):
        for key in amplitude_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        cooling_amplitudes = {key: amplitude_dict.get(key, 0) for key in self.DDS_Dictionary}
        self.cooling_section = {'length': length, 'amplitudes': cooling_amplitudes}

    def edit_cooling_section(self, length, amplitude_dict):
        if not hasattr(self, 'cooling_section'):
            self.cooling_section = {'length': length, 'amplitudes': {}}
        else:
            self.cooling_section['length'] = length
        
        for key in amplitude_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        for key, amplitude in amplitude_dict.items():
            if key in self.DDS_Dictionary:
                self.cooling_section['amplitudes'][key] = amplitude
                self.DDS_Dictionary[key].edited = True

    def create_section(self, name, duration, dds_functions, pmt_gate_high=False):
        for key in dds_functions:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")

            # Check if pmt_gate_pin and ps_sync_pin are the same
            # we cannot switch between high and more than once, 
            # as we use each high signal from the sync to identify the run no. 
            if self.pulse_sequencer.pmt_gate_pin == self.pulse_sequencer.ps_sync_pin:
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

    def edit_section(self, name, dds_functions):
        # Find the section by name
        section = next((s for s in self.playback_sections if s['name'] == name), None)
        if section is None:
            raise ValueError(f"Section with name '{name}' not found.")
        
        for key in dds_functions:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        # Update the functions for the specified DDS keys
        for key, func in dds_functions.items():
            if key in section['functions']:
                section['functions'][key] = func
                self.DDS_Dictionary[key].edited = True

    def build_ram_arrays(self):
        """
        This method uses the functions associated to each DDS in each playback section to build the amplitude arrays for each DDS.
        """
        start_time = time.time()
        total_playback_length = sum(section['duration'] for section in self.playback_sections)
        # Print desired total playback length
        print(f"Intended Playback Length: {total_playback_length:.6f} µs")
        self.N_tot = 0
        
        for key, dds in self.DDS_Dictionary.items():
            if dds.edited:
                # Initialize amplitude array for this DDS
                cooling_amplitude, _ = interpolate_rf_power(
                    dds.calibration_file, 
                    self.cooling_section['amplitudes'][key], 
                    dds.frequency
                )

                if self.trapping_parameters['amplitudes'][key] is not None:
                    trapping_amplitude, _ = interpolate_rf_power(
                        dds.calibration_file, 
                        self.trapping_parameters['amplitudes'][key], 
                        dds.trapping_frequency
                    )
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
                if dds.edited:
                    # Collect fractional power values for this section
                    fractional_power_array = [
                        section['functions'][key](t - current_time) for t in time_array
                    ]
                    # Interpolate amplitudes in a single call
                    amplitude_values, _ = interpolate_rf_power_array(
                        dds.calibration_file,
                        fractional_power_array,
                        np.full_like(fractional_power_array, dds.frequency)
                    )
                    dds.amplitude_array.extend(amplitude_values)
            # Update current time to the end of this section
            current_time += effective_playback_length
        end_time = time.time()
        print(f"Total time taken to build RAM arrays: {end_time - start_time:.6f} s")

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
        if self.pulse_sequencer.pmt_gate_pin == self.pulse_sequencer.ps_sync_pin and self.playback_sections:
            # Check if the last section's pmt_gate_high is True
            # This cant be the case if they share a pulse sequencer pin
            # we need it to go from LOW to HIGH at the start of each run, so that the QuTau
            # Can identify the start as a detection event.
            if self.playback_sections[-1]['pmt_gate_high']:
                raise ValueError("pmt_gate_pin and ps_sync_pin are the same. pmt_gate_pin cannot be HIGH in the last playback section.")
        control_pulse_sequencer(self.pulse_sequencer.port, 'Stop')  # always stop pulse sequencer before a write operation
        
        # Generate end pulse
        self.pulse_sequencer._new_end_pulse = self._generate_pulse(state='end')
        pulse_out(self.pulse_sequencer.port, self.pulse_sequencer._new_end_pulse)
        
        # Initialize each DDS instance before flashing
        dds_list = list(self.DDS_Dictionary.items())
        with tqdm(total=len(dds_list), desc="Flashing DDS", unit="DDS") as pbar:
            for dds_name, dds in dds_list:
                if dds.edited:
                    pbar.set_description(f"Flashing {dds_name}")
                    dds.initialise()  # Ensure the DDS is initialized
                    dds.flash(self.ram_step)  # Then flash the DDS
                    pbar.update(1)
                else:
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
        print(f"Pulses: {pulses}, End Pulse: {self.pulse_sequencer._new_end_pulse}")
        print(f"Pulse Lengths: {pulse_lengths}")
        self.pulse_sequencer._new_pulses = pulses
        self.pulse_sequencer._new_pulse_lengths = pulse_lengths
        print(self.pulse_sequencer._new_pulses)
        print(self.pulse_sequencer._new_pulse_lengths)
        #new end pulse already set in __init__
        self.pulse_sequencer.N_Cycles = self.N_Cycles
        # Write to the pulse sequencer
        self.pulse_sequencer.write_sequence(Continuous=Continuous)

class Experiment_Builder_Singletone:
    def __init__(self, dds_dictionary, pulse_sequencer, N_Cycles=1E5):
        self.DDS_Dictionary = dds_dictionary
        self.pulse_sequencer = pulse_sequencer
        self.pulse_sequencer.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called
        self.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called
        # Generate cooling pulse
        # Check for pin conflicts
        dds_pins = {dds.pulse_sequencer_pin for dds in dds_dictionary.values()}
        if self.pulse_sequencer.pmt_gate_pin in dds_pins:
            print("Warning: pmt_gate_pin overlaps with a DDS's pulse sequencer pin.")
        if self.pulse_sequencer.ps_sync_pin in dds_pins:
            print("Warning: ps_sync_pin overlaps with a DDS's pulse sequencer pin.")
        if self.pulse_sequencer.ps_end_pin in dds_pins:
            raise ValueError("ps_end_pin must not overlap with any DDS's pulse sequencer pin.")
        # Generate end pulse
            
    def set_trapping_parameters(self, trapping_detuning_dict, trapping_amplitude_dict):
        for key in trapping_detuning_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        trapping_detunings = {key: trapping_detuning_dict.get(key, None) for key in self.DDS_Dictionary}
        trapping_amplitudes = {key: trapping_amplitude_dict.get(key, None) for key in self.DDS_Dictionary}
        
        self.trapping_parameters = {'detunings': trapping_detunings, 'amplitudes': trapping_amplitudes}
        for key, trapping_amplitude in trapping_amplitudes.items():
            if trapping_amplitude is not None:
                trapping_detuning = trapping_detunings.get(key)
                if trapping_detuning is not None:
                    trapping_frequency = 200 + trapping_detuning / 2  # Assuming the same conversion as for detuning
                    trapping_amplitude, _ = interpolate_rf_power(self.DDS_Dictionary[key].calibration_file, trapping_amplitude, trapping_frequency)
                    self.DDS_Dictionary[key].set_trapping_profile(trapping_frequency, trapping_amplitude)
                    print(f"Trapping profile set for DDS {key} with detuning {trapping_detuning} and amplitude {trapping_amplitude}.")
            else:
                self.DDS_Dictionary[key].set_trapping_profile(200, 0)

    def create_section(self, name, duration, detunings, amplitudes, pmt_gate_high=False):
        """
        Create a section with specified DDS detunings and amplitudes and pulse sequencer settings.

        Args:
            name (str): Name of the section.
            duration (float): Duration of the section.
            detunings (dict): Dictionary of DDS detunings with keys as DDS names and values as detuning values.
            amplitudes (dict): Dictionary of DDS amplitudes with keys as DDS names and values as amplitude values.
            pmt_gate_high (bool): If True, set the PMT gate pin high.
        """
        default_detuning = 0
        default_amplitude = 0

        # Initialize the bit string for the pulse sequencer
        bit_string = ['0'] * 16  # Assuming an 8-bit string for simplicity

        for key, dds in self.DDS_Dictionary.items():
            frequency = 200 + detunings.get(key, default_detuning) / 2
            amplitude,_ = interpolate_rf_power(dds.calibration_file, amplitudes.get(key, default_amplitude), frequency)
            # Check if any existing profile matches the current section's parameters
            profile_to_use = None
            for i, profile in enumerate(dds._new_profiles):
                if profile['frequency'] == frequency and profile['amplitude'] == amplitude:
                    profile_to_use = i
                    break

            if profile_to_use is None:
                # No matching profile found, use the next available profile
                if len(dds._new_profiles) < 2:
                    profile_to_use = len(dds._new_profiles)
                    dds.set_profile(profile_to_use, frequency=frequency, amplitude=amplitude)
                else:
                    raise ValueError(f"Hardware only permits two profiles. No available profiles for DDS {key}.")

            bit_string[dds.pulse_sequencer_pin] = str(profile_to_use)

        # Set the PMT gate pin
        if pmt_gate_high:
            bit_string[self.pulse_sequencer.pmt_gate_pin] = '1'

        # Set the PS sync pin high if it is the first section
        if not self.pulse_sequencer._new_pulses:  # Added line
            bit_string[self.pulse_sequencer.ps_sync_pin] = '1'  # Added line

        # Convert the bit string to a string
        bit_string = ''.join(bit_string)

        # Add the section to the pulse sequencer
        self.pulse_sequencer._new_pulses.append(bit_string)
        self.pulse_sequencer._new_pulse_lengths.append(duration)

        print(f"Section '{name}' created with duration {duration} µs and bit string {bit_string}.")

    def flash(self):
        """
        Flash the DDSs with the current profiles.
        """
        for dds in self.DDS_Dictionary.values():
            dds.flash()
        self.pulse_sequencer.N_Cycles = self.N_Cycles
                # Set end_pulse to the first pulse
        if self.pulse_sequencer._new_pulses:
            self.pulse_sequencer._new_end_pulse = (
                self.pulse_sequencer._new_pulses[0][:self.pulse_sequencer.ps_end_pin] +
                '1' +
                self.pulse_sequencer._new_pulses[0][self.pulse_sequencer.ps_end_pin + 1:]
            )
            print(f"End pulse set to {self.pulse_sequencer.end_pulse}")
        
        self.pulse_sequencer.write_sequence()

class Experiment_Runner:
    def __init__(self, dds_dictionary, pulse_sequencer, timeout=10, pmt_threshold=None, sp_threshold=None, expected_fluorescence=None, pulse_expected_fluorescence=0, catch_timeout=20, load_timeout=100):
        # Initialize QuTau_Reader with channels
        self.pulse_sequencer = pulse_sequencer
        self.qutau_reader = Server.master(QuTau_Reader, max_que=5)
        # Initialize clients for PMT_Reader and RedlabsDAC
        self.pmt_reader_client = Client(PMT_Reader)
        self.redlabs_dac_client = Client(Redlabs_DAC)
        self.dds_dictionary = dds_dictionary
        # Optional thresholds
        self.pmt_threshold = pmt_threshold
        self.sp_threshold = sp_threshold
        self.expected_fluorescence = expected_fluorescence
        self.pulse_expected_fluorescence = pulse_expected_fluorescence

        self.pmt_counts = 0
    
        # Initialize other parts of the experiment as before
        self.task = nidaqmx.Task()
        self.channel_name = '/Dev1/PFI9'  # Replace with actual DAQ input channel
        self.task.di_channels.add_di_chan(self.channel_name)

        #Init Flags
        self.calibrated_fluoresence = False

        #Flags
        self.running = False  # Flag for running status
        self.loading = False  # Flag for loading status
        self.single_ion = False # Flag for single ion detection

        # Timeouts
        self.timeout = timeout  # Timeout for the experiment
        self.catch_timeout = catch_timeout
        self.load_timeout = load_timeout

    def measure_expected_fluorescence(self, measurement_time=5):
        """
        Masures the PMT counts in cooling mode for a few seconds, and updates expected_fluorescence with this value.
        Parameters:
        measurement_time (int): The duration in seconds for which to measure the counts.
        """
        if self.calibrated_fluoresence is False:
            # Put DDS in trapping mode

            #Check counting
            counting = self.pmt_reader_client.get_counting()
            if not counting:
                self.pmt_reader_client.start_counting()

            start_time = time.time()
            average = []
            rate = self.pmt_reader_client.get_rate()
            try:
                while time.time() - start_time < measurement_time:
                    # Get counts from the PMT_Reader
                    counts = self.pmt_reader_client.get_counts()
                    counts = counts[1]['PMT']
                    recent_counts = counts[-3:]
                    avg_counts = sum(recent_counts) / len(recent_counts) if recent_counts else 0
                    if avg_counts:
                        average.append(avg_counts)  # Assuming counts is a list of values
                    time.sleep(1/rate)  # Sleep for a short interval to avoid overwhelming the PMT reader

                # Calculate the average counts per second
                averaged_counts = sum(average)/len(average)
                # average_counts_per_second = total_counts / measurement_time
                self.expected_fluorescence = averaged_counts
                print(f"Measured expected fluorescence: {self.expected_fluorescence} counts per second")

            finally:

                self.calibrated_fluoresence = True
        else:  
            return self.expected_fluorescence

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
                    lower_bound = self.expected_fluorescence * 0.5

                    if lower_bound <= avg_counts:
                        print(f"Recent PMT counts ({avg_counts}) above 50% of expected fluorescence ({self.expected_fluorescence}).")
                        print("Caught ion.")
                        trapped = True
                        break
                    else:
                        sys.stdout.write(f"\rRecent PMT counts ({avg_counts:.2f}) not within 20% of expected fluorescence ({self.expected_fluorescence}). Retrying...")
                        sys.stdout.flush()
                
                # Sleep based on PMT_Reader's rate
                time.sleep(1 / rate)
        finally:
            self.stop_catch()
        return trapped
    
    def stop_catch(self):
        # Reset the DAC pins
        for dds in self.dds_dictionary.values():
            dds.exit_trapping_mode()
        self.catching = False

    def load_loop(self, N_attempts=5):
        """
        This method will attempt to load single ions into the trap for a maximum of N_attempts. If it loads something, it will run
        a single ion check to verify that only one ion is loaded. If this fails, it will open the trap try again.
        If it fails to load an ion after N_attempts
        """
        loop = 0
        ion_status = False  # Initialize ion_status before using it in the loop condition
        while not ion_status and loop < N_attempts:
            loop += 1
            print(f"Loading attempt {loop}/{N_attempts}...")
            trapped = self.load()
            if trapped:
                ion_status = self.single_ion_check() # check
                if ion_status:
                    print("Ion loading succeeded. Sleeping for 5 seconds to allow ion to cool.")
                    time.sleep(5)
                    ion_status = self.single_ion_check()
                if ion_status:
                    print("Single ion detected. Ion loading successful.")
                    return True
                if not ion_status:
                    print("Single ion check failed. Opening trap and retrying...")
                    
            self.redlabs_dac_client.set_trap_depth(0)
            time.sleep(1)
            self.redlabs_dac_client.set_trap_depth(0.8)
        print("Ion loading failed after maximum attempts. Pausing experiment.")
        return False

    def load(self):
        """
        this method will attempt to load ions into the trap, for some time load_timeout.
        If it succeeds in loading something it willreturn true. 
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
                        trapped = True
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
                lower_bound = self.expected_fluorescence * 0.9
                upper_bound = self.expected_fluorescence * 1.1
                print(avg_counts)
                if lower_bound <= avg_counts <= upper_bound:
                    print(f"Recent PMT counts ({avg_counts}) within 10% of expected fluorescence ({self.expected_fluorescence}). Single Ion Check Passed.")
                    return True
                else:
                    print(f"Recent PMT counts ({avg_counts}) not within 10% of expected fluorescence ({self.expected_fluorescence}). Retrying ({attempt + 1}/5)...")
                    time.sleep(1)
            print(f"Failed to get PMT counts within 20% of expected fluorescence after 5 attempts.")
            self.redlabs_dac_client.set_trap_depth(0)
            time.sleep(1)
            self.redlabs_dac_client.set_trap_depth(0.8)
            return False
        
    def stop_load(self):
        try:
            self.redlabs_dac_client.reset_pins()
            # Reset the DAC pins
            for dds in self.dds_dictionary.values():
                dds.exit_trapping_mode()
            self.loading = False
        except Exception as e:
            print(f"Failed to reset DAC pins: {e}")

    def start_experiment(self, N=None):
        self.N = N  # Remember N for resuming
        self.N_Valid_Pulses = 0  # This variable keeps track of the true number of cycles run, i.e., the number of pulse sequences run whilst the ion is nicely trapped
        self.N_Total_Pulses = 0

        # Check ion status before starting the calibration run
        ion_status = self.check_ion()
        if not ion_status:
            print("Ion check failed. Attempting to catch ion...")
            ion_status = self.catch()
            if not ion_status:
                ion_status = self.load_loop()
                if not ion_status:
                    print("Failed to load ion. Pausing experiment.")
                    self.running = False
                    self.pause_experiment()
                    return

        for dds in self.dds_dictionary.values():
            dds.exit_trapping_mode()
        self.clear_channels()
        self.iteration = 0
        self.qutau_reader.enter_experiment_mode()
        self.calibrate_run_time()  # Calibrate run time on the first run
        self.iteration += 1  # Increment iteration after calibration run
        self.process_data()
        laser_status, ion_status = self.run_diagnostics()
        # Continue the experiment if diagnostics passed
        self.running = True
        if not laser_status:
            self.discard_data()
        elif laser_status:
            self.save_data()
        if not laser_status or not ion_status:  # If diagnostics fail, stop the loop
            self.running = False
        self.experiment_loop()

    def calibrate_run_time(self):
        print(f"Calibrating run time for input to go HIGH on {self.channel_name} for up to {self.timeout} seconds...")
        self.pulse_sequencer.start()
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
            
            time.sleep(0.0001)

    def experiment_loop(self):
        try:
            while True:
                if self.N is not None and self.iteration >= self.N:  # Stop after N runs
                    print(f"Finished running {self.N} iterations of {self.pulse_sequencer.N_Cycles} Cycles.")
                    self.qutau_reader.exit_experiment_mode()
                    break

                if not self.running:
                    print("Experiment paused. Waiting to resume...")
                    while not keyboard.is_pressed('p'):
                        time.sleep(0.1)
                    print("Resuming experiment...")
                    self.running = True

                self.pulse_sequencer.start()
                print(f"Waiting for input to go HIGH on {self.channel_name} for up to {self.timeout} seconds...")

                # Sleep for the calibrated run time
                if self.run_time is not None:
                    time.sleep(self.run_time)

                start_time = time.time()

                while True:
                    input_state = self.task.read()
                    if input_state:
                        print("Input high detected. Processing data and running diagnostics...")
                        if self.running:
                            self.process_data()
                            laser_status, ion_status = self.run_diagnostics()

                            if not laser_status or not ion_status:
                                self.running = False
                                self.pause_experiment()
                                break

                            if laser_status:
                                self.save_data()
                                self.iteration += 1  # Increment iteration after each run

                            break

                    elapsed_time = time.time() - start_time
                    if elapsed_time >= self.timeout:
                        print("Timeout reached. The input never went HIGH. Stopping experiment.")
                        self.running = False
                        self.pause_experiment()
                        break

                    # Always check for manual pause
                    if keyboard.is_pressed('p'):
                        print("Manual pause triggered.")
                        self.running = False
                        self.pause_experiment()
                        break

        except KeyboardInterrupt:
            print("Experiment interrupted manually.")
            self.running = False
            self.pause_experiment()  # Always call pause_experiment on interruption

    def process_data(self):
        """Handle data processing."""
        self.qutau_reader.get_data()
        # here we filter data to remove runs where the ion was not trapped.

        pulse_sequence_length = self.pulse_sequencer.sequence_length * 1E-6
        # expected_fluorescence_per_pulse = self.expected_fluorescence * self.pulse_sequencer.gated_fraction * pulse_sequence_length
        valid, total = self.qutau_reader.filter_runs_for_fluorescence(self.pulse_expected_fluorescence, pulse_sequence_length, self.pulse_sequencer.N_Cycles/100)
        self.N_Valid_Pulses += valid
        self.N_Total_Pulses += total
        print(f"Total number of valid pulses: {self.N_Valid_Pulses}")
        print(f"Total number of pulses: {self.N_Total_Pulses}")
        self.qutau_reader.compute_time_diff(pulse_sequence_length)

    def run_diagnostics(self):
        """Perform diagnostics and handle data saving or discarding based on results."""
        laser_status = self.check_lasers()
        if not laser_status:
            print("Laser check failed. Discarding data and pausing experiment.")
        
        ion_status = self.check_ion()
        if not ion_status:
            print("Ion check failed. Attempting to catch ion...")
            ion_status = self.catch()
            if not ion_status:
                ion_status = self.load_loop()

        return laser_status, ion_status  # Return both statuses for further handling

    def pause_experiment(self):
        """Pause the experiment and allow manual resume."""
        self.qutau_reader.exit_experiment_mode()
        print("Experiment paused. Press 'P' to resume.")
        while not self.running:  # Wait for running to be set to True
            if keyboard.is_pressed('p'):
                print("Resuming the experiment...")
                self.running = True
                self.resume_experiment()
                break
            time.sleep(0.1)

    def resume_experiment(self):
        """Resume the experiment."""
        if not self.check_lasers():
            print("Lasers not locked. Stopping experiment.")
            self.running = False
            return

        trapped = self.single_ion_check()
        if not trapped:
            trapped = self.load_loop()
            if not trapped:
                print("Failed to trap ion.")
                self.running = False
                return

        for dds in self.dds_dictionary.values():
            dds.exit_trapping_mode()
        self.experiment_loop()
     
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

    def get_time_diffs(self, mode, lower_cutoff=None, upper_cutoff=None):
        # Find all channels with the specified mode
        channels = [ch for ch in self.qutau_reader.channels if ch.mode == mode]
        if not channels:
            print(f"No channels found with mode {mode}.")
            return {}

        time_diffs_dict = {}

        # Collect time differences for each channel
        for channel in channels:
            time_diffs_us = np.array(channel.time_diffs) * 1E6  # Convert to NumPy array and multiply by 1E6
            print(np.sort(time_diffs_us))
            # Apply lower cutoff if specified
            if lower_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us >= lower_cutoff]
            
            # Apply upper cutoff if specified
            if upper_cutoff is not None:
                time_diffs_us = time_diffs_us[time_diffs_us <= upper_cutoff]
            
            # Add to dictionary
            time_diffs_dict[channel.name] = time_diffs_us

        return time_diffs_dict

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
            print(np.sort(time_diffs_us))
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