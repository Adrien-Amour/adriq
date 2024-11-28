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