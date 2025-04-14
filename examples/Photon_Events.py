import numpy as np
from adriq.tdc_functions import find_n_photon_events
# Example input data
tstamp = np.array([0, 65, 100, 170, 185, 200, 120, 190, 300, 310, 400, 462, 463, 490,  500])  # Example timestamps (in clock cycles)
tchannel = np.array([0, 1, 0, 2, 1, 0, 1, 1, 0, 2,0,1, 2,1,0])  # Example channels
trig_chan = 0  # Trigger channel
photon_chans = np.array([1, 2])  # Photon channels
photon_windows = np.array([[60e-6, 80e-6], [80e-6, 100e-6]])  # Photon windows (in seconds)
timebase = 1e-6  # Timebase (1 µs per clock cycle)
print(len(tstamp))
print(len(tchannel))
# Call the function
n_photon_events = find_n_photon_events(
    tstamp=tstamp,
    tchannel=tchannel,
    trig_chan=trig_chan,
    photon_chans=photon_chans,
    photon_windows=photon_windows,
    timebase=timebase
)

# Print the results
if n_photon_events is not None:
    for event in n_photon_events:
        print(event)
else:
    print("No valid N-photon events found.")