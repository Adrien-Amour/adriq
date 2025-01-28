import csv
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from ipywidgets import interact, FloatSlider
from IPython.display import display
from scipy.signal import savgol_filter

def load_calibration_results(calibration_file):
    results = []
    rf_power_fractions = []
    with open(calibration_file, 'r') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the header
        max_rf_power = float(header[0])
        rf_power_fractions = [float(x) for x in header[1:]]
        for row in reader:
            results.append([float(x) for x in row])
    return results, rf_power_fractions, max_rf_power

def plot_3d_heatmap_interactive(results, rf_power_fractions):
    frequencies = np.array([row[0] for row in results])
    rf_powers = np.array(rf_power_fractions)
    optical_powers = np.array([row[1:] for row in results]) * 1E3  # Convert to mW

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    X, Y = np.meshgrid(rf_powers, frequencies)
    Z = optical_powers

    surf = ax.plot_surface(X, Y, Z, cmap='viridis')
    fig.colorbar(surf)

    ax.set_xlabel('RF Power Fraction')
    ax.set_ylabel('Frequency (MHz)')
    ax.set_zlabel('Optical Power (mW)')

    def update_plot(elev=30, azim=45):
        ax.view_init(elev=elev, azim=azim)
        fig.canvas.draw_idle()

    # Create interactive sliders for elevation and azimuth
    interact(update_plot,
             elev=FloatSlider(min=0, max=90, step=1, value=30, description='Elevation'),
             azim=FloatSlider(min=0, max=360, step=1, value=45, description='Azimuth'))
    plt.show()

def plot_optical_power_vs_rf_power(results, rf_power_fractions, fixed_frequency, smooth=False, save=False):
    # Find the row corresponding to the fixed frequency
    for row in results:
        if row[0] == fixed_frequency:
            optical_powers = np.array(row[1:]) * 1E3  # Convert to mW
            break
    else:
        print(f"Frequency {fixed_frequency} MHz not found in results.")
        return

    if smooth:
        optical_powers = savgol_filter(optical_powers, window_length=5, polyorder=2)

    plt.figure()
    plt.plot(rf_power_fractions, optical_powers, marker='o')
    plt.xlabel('RF Power Fraction')
    plt.ylabel('Optical Power (mW)')
    plt.title(f'Optical Power vs RF Power at {fixed_frequency} MHz')
    plt.grid(True)

    if save:
        plt.savefig(f'optical_power_vs_rf_power_{fixed_frequency}MHz.png')

    plt.show()

# Replace this with your CSV file path
calibration_file = input("Enter the filename to save the calibration results: ").strip()

# Load the results from the CSV file
results, rf_power_fractions, max_rf_power = load_calibration_results(calibration_file)

# Example usage
 # Replace with the desired frequency
plot_optical_power_vs_rf_power(results, rf_power_fractions, 409.5, smooth=True, save=True)
plot_optical_power_vs_rf_power(results, rf_power_fractions, 410, smooth=True, save=True)
plot_optical_power_vs_rf_power(results, rf_power_fractions, 410.5, smooth=True, save=True)
plot_optical_power_vs_rf_power(results, rf_power_fractions, 411, smooth=True, save=True)

# Plot the 3D heatmap with interactive rotation controls
plot_3d_heatmap_interactive(results, rf_power_fractions)