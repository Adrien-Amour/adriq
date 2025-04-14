import numpy as np
import matplotlib.pyplot as plt
from adriq.RedLabs_Dac import *
from adriq.Counters import *
from adriq.Servers import *

class MicromotionAmplitudePlotter:
    def __init__(self, redlabs_dac, tdc_reader):
        self.tdc_client = Client(tdc_reader)
        self.redlabs_dac_client = Client(redlabs_dac)

    def measure_micromotion_amplitude(self, H, V, trap_depth, no_runs=50, rate=5, no_bins=200):
        """
        Set the trap depth, H, and V values, and measure micromotion amplitude.
        """
        # Set the trap depth
        self.redlabs_dac_client.set_trap_depth(trap_depth)
        # # Set the H and V values
        self.redlabs_dac_client.dc_min_shift(H, V)
        # Perform RF correlation to measure micromotion amplitude
        popt, _, _ = self.tdc_client.RF_correlation(no_runs, rate, no_bins)
        if len(popt) > 0:
            amplitude = popt[0]  # Extract amplitude from the fit parameters
        else:
            amplitude = np.nan  # Handle cases where no data is returned
        return amplitude

    def plot_micromotion_amplitude(self, H, V_Values, trap_depths, no_runs=50, rate=5, no_bins=200):
        """
        Vary V over a range and plot the micromotion amplitude for each trap depth.
        Each trap depth will have its own y-axis.
        """
        print(f"V values: {V_Values}")
        fig, ax1 = plt.subplots(figsize=(8, 6))

        # Colors for each trap depth
        colors = ['b', 'r', 'g', 'c', 'm', 'y']  # Add more colors if needed
        axes = [ax1]  # List to store axes for each trap depth

        for i, trap_depth in enumerate(trap_depths):
            amplitudes = []
            for V in V_Values:
                amplitude = self.measure_micromotion_amplitude(H, V, trap_depth, no_runs, rate, no_bins)
                print(f"Trap Depth: {trap_depth}, V: {V}, Amplitude: {np.abs(amplitude)}")
                amplitudes.append(np.abs(amplitude))

            # Create a new y-axis for each trap depth after the first
            if i > 0:
                ax = ax1.twinx()
                axes.append(ax)
                ax.spines['right'].set_position(('outward', 60 * (i - 1)))  # Offset each new axis
            else:
                ax = ax1

            # Plot the results for this trap depth
            ax.plot(V_Values, amplitudes, label=f"Trap Depth: {trap_depth} V", color=colors[i % len(colors)])
            ax.set_ylabel(f"Amplitude (Trap Depth: {trap_depth} V)", color=colors[i % len(colors)])
            ax.tick_params(axis='y', labelcolor=colors[i % len(colors)])

        # Configure the shared x-axis
        ax1.set_xlabel("V Value")
        ax1.set_title(f"Micromotion Amplitude vs V (H = {H})")
        ax1.grid(True)

        # Add legends for all axes
        lines, labels = [], []
        for ax in axes:
            line, label = ax.get_legend_handles_labels()
            lines.extend(line)
            labels.extend(label)
        ax1.legend(lines, labels, loc='upper left')

        plt.show()


# Example usage
if __name__ == "__main__":
    # Replace these with actual client instances
    redlabs_dac_client = None  # Replace with your Redlabs_DAC client
    count_reader_client = None  # Replace with your count_reader_client

    plotter = MicromotionAmplitudePlotter(Redlabs_DAC, QuTau_Reader)
    
    # Define the parameters
    H = -1.5  # Input value of H
    V_range = (-0.636, -0.65)  # Range of V values
    V_Values = np.arange(-0.67, -0.65, 0.002)  # Generate V values
    trap_depths = [0.8,1.0]  # Trap depths to test
    no_runs = 20  # Number of runs for RF correlation
    rate = 5  # Rate for RF correlation
    no_bins = 100  # Number of bins for RF correlation

    # Plot the micromotion amplitude
    plotter.plot_micromotion_amplitude(H, V_Values, trap_depths, no_runs, rate, no_bins)