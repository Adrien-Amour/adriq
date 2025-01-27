import numpy as np
cimport numpy as np
from libc.stdint cimport int64_t

def filter_trailing_zeros(np.ndarray[np.float64_t, ndim=1] tstamp, 
                          np.ndarray[np.int64_t, ndim=1] tchannel):
    cdef int n = tstamp.shape[0]
    cdef int i

    # Find the first zero in tstamp
    for i in range(n):
        if tstamp[i] == 0:
            break

    # Slice the arrays up to the first zero
    return tstamp[:i], tchannel[:i]

def filter_duplicate_counts(np.ndarray[np.float64_t, ndim=1] tstamp, 
                            np.ndarray[np.int64_t, ndim=1] tchannel, 
                            int signal_chan, 
                            double threshold_time):
    cdef int i
    cdef int n = tstamp.shape[0]
    cdef np.ndarray[np.float64_t, ndim=1] filtered_tstamp = np.empty(n, dtype=np.float64)
    cdef np.ndarray[np.int64_t, ndim=1] filtered_tchannel = np.empty(n, dtype=np.int64)
    cdef int count = 0
    cdef double last_time = -1.0
    cdef int duplicate_count = 0

    for i in range(n):
        if tchannel[i] == signal_chan:
            if last_time == -1.0 or (tstamp[i] - last_time) >= threshold_time:
                filtered_tstamp[count] = tstamp[i]
                filtered_tchannel[count] = tchannel[i]
                count += 1
                last_time = tstamp[i]
            else:
                duplicate_count += 1
        else:
            filtered_tstamp[count] = tstamp[i]
            filtered_tchannel[count] = tchannel[i]
            count += 1

    # Print the number of duplicate counts deleted
    print(f"Number of duplicate counts deleted for channel {signal_chan}: {duplicate_count}")

    # Slice the arrays to the actual count
    return filtered_tstamp[:count], filtered_tchannel[:count]



def compute_time_diffs(np.ndarray[np.float64_t, ndim=1] tstamp, 
                       np.ndarray[np.int64_t, ndim=1] tchannel, 
                       int trig_chan, 
                       np.ndarray[np.int64_t, ndim=1] signal_chans,
                       double sequence_length=-1.0):
    cdef int i, j
    cdef int n
    cdef int m = signal_chans.shape[0]
    cdef np.ndarray[np.float64_t, ndim=2] time_diffs
    cdef np.ndarray[np.int32_t, ndim=1] counts
    cdef double last_rf_time = -1.0
    cdef list trigger_times = []

    # Filter out trailing zeros in the timestamp array
    n = tstamp.shape[0]
    time_diffs = np.empty((m, n), dtype=np.float64)
    counts = np.zeros(m, dtype=np.int32)

    for i in range(n):
        if tchannel[i] == trig_chan:
            if last_rf_time != -1.0:
                trigger_times.append(tstamp[i] - last_rf_time)
            last_rf_time = tstamp[i]
        elif last_rf_time != -1.0:
            for j in range(m):
                if tchannel[i] == signal_chans[j]:
                    time_diff = tstamp[i] - last_rf_time
                    if sequence_length == -1.0 or time_diff <= 1.05 * sequence_length:
                        time_diffs[j, counts[j]] = time_diff
                        counts[j] += 1

    # Calculate and print the mean time between trigger pulses
#    if trigger_times:
#        mean_trigger_time = np.mean(trigger_times)
#        print(f"Mean time between trigger pulses: {mean_trigger_time:.6f} seconds")

    # Trim the time_diffs array to remove unused elements
    trimmed_time_diffs = [time_diffs[j, :counts[j]] for j in range(m)]
    
    return trimmed_time_diffs

def count_events_in_window(np.ndarray[np.float64_t, ndim=1] tstamp, 
                           np.ndarray[np.int64_t, ndim=1] tchannel, 
                           int trig_chan, 
                           int signal_chan,
                           double lower_time,
                           double upper_time):
    cdef int i
    cdef int n = tstamp.shape[0]
    cdef double last_rf_time = -1.0
    cdef int event_count = 0
    cdef int current_count = 0
    cdef np.ndarray[np.int32_t, ndim=1] event_counts = np.zeros(n, dtype=np.int32)
    cdef np.ndarray[np.float64_t, ndim=1] time_diffs = np.zeros(n, dtype=np.float64)
    cdef double total_time_diff = 0.0
    cdef int time_diff_count = 0

    for i in range(n):
        if tchannel[i] == trig_chan:
            last_rf_time = tstamp[i]
            if current_count > 0:
                event_counts[event_count] = current_count
                event_count += 1
                current_count = 0
        elif last_rf_time != -1.0 and tchannel[i] == signal_chan:
            time_diff = tstamp[i] - last_rf_time
            if lower_time <= time_diff <= upper_time:
                if current_count > 0:
                    total_time_diff += time_diff - time_diffs[event_count - 1]
                    time_diff_count += 1
                time_diffs[event_count] = time_diff
                current_count += 1

    # Handle the last event if it was not followed by another trigger
    if current_count > 0:
        event_counts[event_count] = current_count
        event_count += 1

    # Trim the event_counts array to remove unused elements
    trimmed_event_counts = event_counts[:event_count]

    # Count the number of N-count events
    unique, counts = np.unique(trimmed_event_counts, return_counts=True)
    event_count_dict = {int(k): int(v) for k, v in zip(unique, counts)}

    # Calculate the mean time difference
    mean_time_diff = total_time_diff / time_diff_count if time_diff_count > 0 else 0.0
    print(f"Mean time difference between duplicate counts: {mean_time_diff:.6f} seconds")

    return event_count_dict

def count_channel_events(np.ndarray[np.int64_t, ndim=1] tchannel):
    cdef int i
    cdef int n = tchannel.shape[0]
    cdef dict channel_counts = {}

    for i in range(n):
        if tchannel[i] in channel_counts:
            channel_counts[tchannel[i]] += 1
        else:
            channel_counts[tchannel[i]] = 1

    # Convert the dictionary to a list of [channel number, count]
    counts_list = [[channel, count] for channel, count in channel_counts.items()]

    return counts_list


def filter_runs(
    np.ndarray[np.float64_t, ndim=1] tstamp,
    np.ndarray[np.int64_t, ndim=1] tchannel,
    int trig_chan,
    int signal_chan,
    double expected_count_rate,
    double pulse_window_time,
    int bin_size=10000
):
    """
    Filters timestamp (tstamp) and channel (tchannel) data to exclude pulses
    bins with counts below a defined threshold on the signal_chan.
    Example usage is for filtering runs where an ion has collided with gas and
    hence fluorescence measurements are low.
    We

    Parameters:
        tstamp (np.ndarray[np.float64_t, ndim=1]): Array of event timestamps.
        tchannel (np.ndarray[np.int64_t, ndim=1]): Array of event channels.
        trig_chan (int): Channel indicating the start of a pulse.
        signal_chan (int): Channel that you would like to filter pulses with low signals.
        expected_counts_per_pulse (double): Expected fluorescence counts per pulse.
        pulse_window_time (int): Time window for a pulse (in same units as timestamps).
        bin_size (int): Number of pulses per bin for thresholding (default: 10000).

    Returns:
        Tuple[np.ndarray, np.ndarray, int]:
            - Filtered timestamps
            - Filtered channels
            - Number of valid pulses
    """
    # Initialization of key variables
    cdef int i, pulse_index = -1, total_pulses = 0, bin_index = 0
    cdef double current_trigger_time = -1.0, next_trigger_time = -1.0
    cdef np.ndarray[np.int32_t, ndim=1] counts
    cdef np.ndarray[np.int32_t, ndim=1] pulse_flags
    cdef np.ndarray[np.float64_t, ndim=1] pulse_start_times
    cdef np.ndarray[np.int32_t, ndim=1] bin_flags
    cdef int total_bins
    cdef int valid_pulse_count = 0  # Counter for valid pulses

    # Number of events in the input arrays
    n = tstamp.shape[0]
    # Allocate memory for pulse tracking arrays
    counts = np.zeros(n, dtype=np.int32)  # Stores fluorescence counts per pulse
    pulse_flags = np.zeros(n, dtype=np.int32)  # Marks invalid pulses
    pulse_start_times = np.zeros(n, dtype=np.float64)  # Tracks pulse start times
    expected_counts_per_pulse = expected_count_rate * pulse_window_time
    # Calculate bin-level thresholds
    expected_counts_per_bin = bin_size * expected_counts_per_pulse
    threshold_counts = 0.8 * expected_counts_per_bin  # Set to 2/3 of expectation
    # --- Loop 1: Count  events for each pulse ---
    for i in range(n):
        if tchannel[i] == trig_chan:
            # Start a new pulse when a trigger is encountered
            pulse_index += 1
            pulse_start_times[pulse_index] = tstamp[i]
            total_pulses += 1

            # Define the valid time window for this pulse
            current_trigger_time = tstamp[i]
            next_trigger_time = current_trigger_time + pulse_window_time
        elif current_trigger_time != -1.0 and tchannel[i] == signal_chan:
            # Count fluorescence events within the pulse time window
            if next_trigger_time == -1.0 or tstamp[i] < next_trigger_time:
                counts[pulse_index] += 1

    # Calculate the total number of bins based on bin size
    total_bins = (total_pulses + bin_size - 1) // bin_size  # Round up for partial bins
    bin_flags = np.zeros(total_bins, dtype=np.int32)  # Flags for invalid bins

    # --- Loop 2: Check bins for low fluorescence ---
    for i in range(total_bins):
        start_pulse = i * bin_size
        end_pulse = min((i + 1) * bin_size, total_pulses)  # Ensure not to exceed total pulses
        # Sum up fluorescence counts for all pulses in the bin 
        bin_total = np.sum(counts[start_pulse:end_pulse])
        # Flag the bin if its total fluorescence is below the threshold
        if bin_total < threshold_counts:
            bin_flags[i] = 1  # Mark bin as invalid

    # --- Loop 3: Flag pulses in invalid bins ---
    for i in range(total_bins):
        if bin_flags[i] == 1:  # If the bin is invalid
            start_pulse = i * bin_size
            end_pulse = min((i + 1) * bin_size, total_pulses)

            # Mark all pulses in this bin as invalid
            for j in range(start_pulse, end_pulse):
                pulse_flags[j] = 1

    # Allocate arrays for filtered data
    cdef np.ndarray[np.float64_t, ndim=1] filtered_tstamp = np.empty(n, dtype=np.float64)
    cdef np.ndarray[np.int64_t, ndim=1] filtered_tchannel = np.empty(n, dtype=np.int64)
    cdef int count = 0  # Counter for valid events

    # --- Loop 4: Filter out flagged pulses ---
    pulse_index = -1
    for i in range(n):
        if tchannel[i] == trig_chan:
            pulse_index += 1  # Increment pulse index on trigger

        # Skip events all events while in a flagged pulse
        if pulse_index >= 0 and pulse_flags[pulse_index] == 1:
            continue

        # Increment valid pulse count for unflagged triggers
        if tchannel[i] == trig_chan:
            valid_pulse_count += 1

        # Add valid events to the filtered arrays
        filtered_tstamp[count] = tstamp[i]
        filtered_tchannel[count] = tchannel[i]
        count += 1

    # Return the filtered data and the count of valid pulses
    return filtered_tstamp[:count], filtered_tchannel[:count], valid_pulse_count, total_pulses



