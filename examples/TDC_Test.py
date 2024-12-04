import numpy as np
from adriq.tdc_functions import compute_time_diffs  # Ensure this import matches your module structure
 
def test_compute_time_diffs():
    tstamp =   np.array([0, 3, 4, 5, 7, 8, 11.6, 12], dtype=np.float64)
    tchannel = np.array([1, 2, 1, 3, 2, 1, 2, 1], dtype=np.int64)
    trig_chan = 1
    signal_chans = np.array([2, 3], dtype=np.int64)
    sequence_length = 4
 
    result = compute_time_diffs(tstamp, tchannel, trig_chan, signal_chans, sequence_length)
    print("compute_time_diffs result:", result)
 
    # Check for duplicates in the result
    for i, diffs in enumerate(result):
        unique_diffs = np.unique(diffs)
        if len(unique_diffs) != len(diffs):
            print(f"Duplicates found in signal channel {signal_chans[i]}: {diffs}")
 
if __name__ == "__main__":
    test_compute_time_diffs()
 