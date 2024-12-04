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

    # Filter out trailing zeros in the timestamp array
    n = tstamp.shape[0]
    time_diffs = np.empty((m, n), dtype=np.float64)
    counts = np.zeros(m, dtype=np.int32)

    for i in range(n):
        if tchannel[i] == trig_chan:
            last_rf_time = tstamp[i]
        elif last_rf_time != -1.0:
            for j in range(m):
                if tchannel[i] == signal_chans[j]:
                    time_diff = tstamp[i] - last_rf_time
                    if sequence_length == -1.0 or time_diff <= 1.05 * sequence_length:
                        time_diffs[j, counts[j]] = time_diff
                        counts[j] += 1

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