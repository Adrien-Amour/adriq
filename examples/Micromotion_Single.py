import sys
import numpy as np
import matplotlib.pyplot as plt
from itcm.Count_Managers import QuTau_Manager

def sine_wave(x, amplitude, frequency, phase, offset):
    return amplitude * np.sin(frequency * 2 * np.pi * x + phase) + offset

def main():
    # Initialize QuTau_Manager
    qu_tau_manager = QuTau_Manager()

    # Define parameters for RF_correlation
    no_runs = 50  # Example value, replace with actual value
    rate = 10  # Example value, replace with actual value
    no_bins = 200  # Example value, replace with actual value

    print("Press Enter to call RF_correlation. Press Ctrl+C to exit.")

    try:
        while True:
            input()  # Wait for Enter key press
            (amplitude, frequency, phase, offset), hist, bin_edges = qu_tau_manager.RF_correlation(no_runs, rate, no_bins)
            print(f"Fit parameters: Amplitude={amplitude}, Frequency={frequency}, Phase={phase}, Offset={offset}")
            # Calculate bin centers from bin edges
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            plt.figure()
            plt.bar(bin_centers, hist, width=bin_centers[1] - bin_centers[0], alpha=0.6, label='Histogram')
            plt.plot(bin_centers, sine_wave(bin_centers, amplitude, frequency, phase, offset), 'r-', label='Fit')
            plt.xlabel('Time Difference')
            plt.ylabel('Counts')
            plt.legend()
            plt.show()

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == '__main__':
    main()