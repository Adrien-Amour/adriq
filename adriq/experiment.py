import numpy as np
import matplotlib.pyplot as plt
from .ad9910 import *
from .pulse_sequencer import *


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
    def __init__(self, port, board, mode, pulse_sequencer_pin, frequency, amplitude_array=None):
        # Initialization as previously defined.
        self.port = port
        self.board = board
        self.mode = mode
        self.pulse_sequencer_pin = pulse_sequencer_pin
        self.frequency = frequency
        self.phase = 0
        self.amplitude_array = amplitude_array
        self.initialised = False
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
        write_ram(
            self.port,
            self.board,
            "Amplitude",
            self.amplitude_array,
            Frequency=self.frequency,
            Amplitude=1,
            Phase=self.phase,
            Show_RAM=False

        )

        start_ram(self.port, self.board) # because of firmware we have to start ram to actually flash the DDS
        # Set profile 0 to direct switch mode (start = 0, stop = 1)
        ram_profile_setting(self.port, self.board, 0, Start_Address=1, End_Address=1, Profile_Mode="Direct Switch")
        
        # Set profile 1 to playback mode (start = 1, stop = 1000)
        ram_profile_setting(self.port, self.board, 1, Amplitude_Ramp_Rate_Divider=int(ramp_rate_divider), Start_Address=2, End_Address=len(self.amplitude_array)-1, Profile_Mode="Ramp-Up", No_Dwell_High=True)
    

        self.flashed = True  # Mark as flashed after successfully setting profiles and uploading RAM


class ExperimentalSequence:
    def __init__(self, dds_dictionary, ram_step=0.02, pulse_sequencer_port="COM5", N_Cycles = 1E6, PMT_Gate_Pin=13, run_identifier_pin=14, run_end_pin=15):
        if ram_step % 0.004 != 0:
            raise ValueError("ram_step must be a multiple of 0.004.")

        self.DDS_Dictionary = dds_dictionary
        self.cooling_section = None
        self.playback_sections = []
        self.ram_step = ram_step
        self.pulse_sequencer_port = pulse_sequencer_port
        # Store pulse sequencer properties
        self.PMT_Gate_Pin = PMT_Gate_Pin
        self.run_identifier_pin = run_identifier_pin
        self.run_end_pin = run_end_pin
        self.N_Cycles = int(N_Cycles)  # Number of cycles for the pulse sequencer to run after start is called
        # Generate cooling and playback pulses
        self.cooling_pulse = self._generate_pulse(state='cooling')
        self.playback_pulse = self._generate_pulse(state='playback')

        # Check for pin conflicts
        dds_pins = {dds.pulse_sequencer_pin for dds in dds_dictionary.values()}
        if PMT_Gate_Pin in dds_pins:
            print("Warning: PMT_Gate_Pin overlaps with a DDS's pulse sequencer pin.")
        if run_identifier_pin in dds_pins:
            print("Warning: run_identifier_pin overlaps with a DDS's pulse sequencer pin.")
        if run_end_pin in dds_pins:
            raise ValueError("run_end_pin must not overlap with any DDS's pulse sequencer pin.")

        # Generate end pulse
        self.end_pulse = self._generate_pulse(state='end')

    def _generate_pulse(self, state):
        """
        Generates a 16-bit string for the pulse sequencer output based on the state.
        
        Parameters:
        state (str): The state of the pulse ('cooling', 'playback', or 'end').

        Returns:
        str: A 16-bit binary string representing the pulse.
        """
        pulse = ['0'] * 16  # Start with all bits low

        for dds in self.DDS_Dictionary.values():
            if state == 'cooling':
                pulse[dds.pulse_sequencer_pin] = '0'  # Set DDS pins low for cooling
            elif state == 'playback':
                pulse[dds.pulse_sequencer_pin] = '1'  # Set DDS pins high for playback
            elif state == 'end':
                pulse[dds.pulse_sequencer_pin] = '0'  # Same as cooling, but with run_end_pin high

        # Set PMT_Gate_Pin and run_identifier_pin if applicable
        if state in ['cooling', 'playback'] and self.PMT_Gate_Pin is not None:
            pulse[self.PMT_Gate_Pin] = '1'

        if state == 'playback' and self.run_identifier_pin is not None:
            pulse[self.run_identifier_pin] = '1'

        if state == 'end' and self.run_end_pin is not None:
            pulse[self.run_end_pin] = '1'

        return ''.join(pulse)

    def create_cooling_section(self, length, amplitude_dict):
        for key in amplitude_dict:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        cooling_amplitudes = {key: amplitude_dict.get(key, 0) for key in self.DDS_Dictionary}
        self.cooling_section = {'length': length, 'amplitudes': cooling_amplitudes}

    def create_section(self, name, duration, dds_functions):
        for key in dds_functions:
            if key not in self.DDS_Dictionary:
                raise ValueError(f"Unidentified DDS key: {key}")
        
        section_functions = {key: dds_functions.get(key, lambda t: 0) for key in self.DDS_Dictionary}
        self.playback_sections.append({'name': name, 'duration': duration, 'functions': section_functions})

    def build_ram_arrays(self):
        total_playback_length = sum(section['duration'] for section in self.playback_sections)

        # Print desired total playback length
        print(f"Intended Playback Length: {total_playback_length:.6f} µs")
        self.N_tot = 0

        for key, dds in self.DDS_Dictionary.items():
            # Initialize amplitude array for this DDS
            dds.amplitude_array = [self.cooling_section['amplitudes'][key],self.cooling_section['amplitudes'][key]]  #some boards only work with direct switch on ram word 1, also i added the zero as a safety net feature, in case no dwell high fails

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
                amplitude_array = [
                    section['functions'][key](t - current_time) for t in time_array
                ]
                dds.amplitude_array.extend(amplitude_array)

            # Update current time to the end of this section
            current_time += effective_playback_length

        for key, dds in self.DDS_Dictionary.items():
            # Ensure amplitude_array only contains numeric values by casting all elements to float
            dds.amplitude_array = np.array(dds.amplitude_array, dtype=float)
            # Round the values and convert to integers
            dds.amplitude_array = np.round(dds.amplitude_array).astype(int)
   
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
            plt.plot(time_axis, dds.amplitude_array, label=f"{key} DDS")

        # Remove duplicate labels for the dashed lines in the legend
        handles, labels = plt.gca().get_legend_handles_labels()
        unique_handles_labels = dict(zip(labels, handles))
        plt.legend(unique_handles_labels.values(), unique_handles_labels.keys())

        # Plot styling
        plt.title('Amplitude Arrays of Each DDS with Cooling and Playback Pulses Highlighted')
        plt.xlabel('Time (µs)')
        plt.ylabel('Amplitude')
        plt.grid(True)
        plt.show()

    def flash(self):
        """
        Calls the flash method of all DDS instances and writes to the pulse sequencer.
        Initializes each DDS before calling their flash method.
        """
        # Initialize each DDS instance before flashing
        for dds in self.DDS_Dictionary.values():
            dds.initialise()  # Ensure the DDS is initialized
            dds.flash(self.ram_step)       # Then flash the DDS

        # Construct the pulses and lengths for the pulse sequencer
        pulses = [self.cooling_pulse, self.playback_pulse]
        pulse_lengths = [
            self.cooling_section['length'],
            sum(section['duration'] for section in self.playback_sections)
        ]
        
        # Debug prints for verification
        print(f"Pulses: {pulses}, End Pulse: {self.end_pulse}")
        print(f"Pulse Lengths: {pulse_lengths}")
        # Write to the pulse sequencer
        write_pulse_sequencer(
            Port=self.pulse_sequencer_port,  # Replace with actual port if needed
            Pulses=pulses,
            Pulse_Lengths=pulse_lengths,
            Continuous=False,
            N_Cycles=self.N_Cycles,
            End_Pulse=self.end_pulse
        )
