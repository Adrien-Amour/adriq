from adriq.ad9910 import general_setting_master, general_setting_slave, general_setting_standalone, single_tone_profile_setting, interpolate_rf_power
from adriq.pulse_sequencer import control_pulse_sequencer, write_pulse_sequencer

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
        self.trapping_frequency = None
        self.trapping_amplitude = None

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
        while len(self._profiles) <= profile:
            self._profiles.append({'frequency': 200, 'amplitude': 0, 'phase': 0})

        self._profiles[profile] = {
            'frequency': frequency,
            'amplitude': amplitude,
            'phase': phase
        }

    def flash(self):
        """Apply the single tone profile settings for all profiles."""
        print(self.board)
        for profile, settings in enumerate(self._profiles):
            single_tone_profile_setting(
                Port=self.port,
                Board=self.board,
                Profile=profile,
                PLL_Multiplier=self.PLL_MULTIPLIER,
                Amplitude=settings['amplitude'],
                Phase_Offset=settings['phase'],
                Frequency=settings['frequency'],
                Verbose=False
            )

    def enter_trapping_mode(self):
        """
        Enter trapping mode, applying the trapping frequency and amplitude 
        if they differ from profile 0's settings.
        """
        if self.trapping_frequency is not None and self.trapping_amplitude is not None:
            # Check if the trapping settings differ from profile 0
            profile_0 = self._profiles[0]
            if (
                profile_0['frequency'] != self.trapping_frequency
                or profile_0['amplitude'] != self.trapping_amplitude
            ):
                # Update profile 0 with trapping settings
                self.set_profile(0, frequency=self.trapping_frequency, amplitude=self.trapping_amplitude)

                # Apply the updated profile settings
                single_tone_profile_setting(
                    Port=self.port,
                    Board=self.board,
                    Profile=0,
                    PLL_Multiplier=self.PLL_MULTIPLIER,
                    Amplitude=self.trapping_amplitude,
                    Phase_Offset=profile_0['phase'],  # Keep the existing phase
                    Frequency=self.trapping_frequency,
                    Verbose=False
                )

    def exit_trapping_mode(self):
        """
        Exit trapping mode, restoring the original profile 0 settings 
        if they differ from the trapping settings.
        """
        if self.trapping_frequency is not None and self.trapping_amplitude is not None:
            # Check if profile 0 settings differ from the original settings
            original_frequency = self._profiles[0]['frequency']
            original_amplitude = self._profiles[0]['amplitude']
            original_phase = self._profiles[0]['phase']

            if (
                original_frequency != self.trapping_frequency
                or original_amplitude != self.trapping_amplitude
            ):
                # Restore the original profile 0 settings
                single_tone_profile_setting(
                    Port=self.port,
                    Board=self.board,
                    Profile=0,
                    PLL_Multiplier=self.PLL_MULTIPLIER,
                    Amplitude=original_amplitude,
                    Phase_Offset=original_phase,
                    Frequency=original_frequency,
                    Verbose=False
                )
        
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
        
        self.pulses = []  # Placeholder for pulse patterns
        self.pulse_lengths = []  # Placeholder for pulse durations
        self.N_Cycles = 1  # Default number of cycles
        self.end_pulse = None  # Default end pulse
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
        if not self.pulses or not self.pulse_lengths or len(self.pulses) != len(self.pulse_lengths):
            raise ValueError("Pulses and pulse lengths must be defined and of the same length.")

        # Calculate the gated fraction
        total_time = sum(self.pulse_lengths)
        gated_time = sum(
            length for pulse, length in zip(self.pulses, self.pulse_lengths) 
            if pulse[self.pmt_gate_pin] == '1'
        )

        self.gated_fraction = gated_time / total_time if total_time > 0 else 0

        self.sequence_length = total_time
        print(f"Total time: {total_time:.6f} µs, Gated time: {gated_time:.6f} µs, Gated fraction: {self.gated_fraction:.2f}")
        # Write the pulse sequence
        write_pulse_sequencer(
            Port=self.port,  
            Pulses=self.pulses,
            Pulse_Lengths=self.pulse_lengths,
            Continuous=Continuous,
            N_Cycles=self.N_Cycles,
            End_Pulse=self.end_pulse
        )


class Experiment_Builder:
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
        for key, trapping_detuning in trapping_detunings.items():
            if trapping_detuning is not None:
                self.DDS_Dictionary[key].trapping_frequency = 200 + trapping_detuning / 2  # Assuming the same conversion as for detuning

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
            print(type(amplitude))
            # Check if any existing profile matches the current section's parameters
            profile_to_use = None
            for i, profile in enumerate(dds._profiles):
                if profile['frequency'] == frequency and profile['amplitude'] == amplitude:
                    profile_to_use = i
                    break

            if profile_to_use is None:
                # No matching profile found, use the next available profile
                if len(dds._profiles) < 2:
                    profile_to_use = len(dds._profiles)
                    dds.set_profile(profile_to_use, frequency=frequency, amplitude=amplitude)
                else:
                    raise ValueError(f"Hardware only permits two profiles. No available profiles for DDS {key}.")

            bit_string[dds.pulse_sequencer_pin] = str(profile_to_use)

        # Set the PMT gate pin
        if pmt_gate_high:
            bit_string[self.pulse_sequencer.pmt_gate_pin] = '1'

        # Convert the bit string to a string
        bit_string = ''.join(bit_string)

        # Add the section to the pulse sequencer
        self.pulse_sequencer.pulses.append(bit_string)
        self.pulse_sequencer.pulse_lengths.append(duration)

        print(f"Section '{name}' created with duration {duration} µs and bit string {bit_string}.")

    
    def flash(self):
        """
        Flash the DDSs with the current profiles.
        """
        print(self.pulse_sequencer.pulses)
        print(self.pulse_sequencer.pulse_lengths)
        for dds in self.DDS_Dictionary.values():
            dds.flash()
        self.pulse_sequencer.N_Cycles = self.N_Cycles
                # Set end_pulse to the first pulse
        if self.pulse_sequencer.pulses:
            self.pulse_sequencer.end_pulse = self.pulse_sequencer.pulses[0]
        pulse_sequencer.write_sequence()
        

# Create DDS instances
b = DDS_Singletone(port="COM9", board=0, mode="standalone", pulse_sequencer_pin=15, calibration_file="C:/Users/probe/OneDrive - University of Sussex/Desktop/Experiment_Config/Calibration_Files/397b_calib.csv")
# Create a dictionary of DDS instances
dds_dictionary = {
    "DDS1": b,
}

# Create a Pulse_Sequencer instance
pulse_sequencer = Pulse_Sequencer(port="COM5", ps_end_pin=2, pmt_gate_pin=1, ps_sync_pin=0)

# Create an Experiment_Builder instance
experiment_builder = Experiment_Builder(dds_dictionary, pulse_sequencer, N_Cycles=1E5)

# Set trapping parameters
experiment_builder.set_trapping_parameters(
    trapping_detuning_dict={"DDS1": -48},
    trapping_amplitude_dict={"DDS1": 0.4}
)

# Create sections
experiment_builder.create_section(
    name="Section 1",
    duration=10,
    detunings={"DDS1": -18},
    amplitudes={"DDS1": 0.2},
    pmt_gate_high=True
)

experiment_builder.create_section(
    name="Section 2",
    duration=10,
    detunings={"DDS1": 18},
    amplitudes={"DDS1": 0.2},
    pmt_gate_high=True
)


experiment_builder.flash()
pulse_sequencer.start()