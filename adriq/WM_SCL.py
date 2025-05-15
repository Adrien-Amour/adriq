import csv
import ctypes
import os
import numpy as np
import time
import pkg_resources

dll_dir = pkg_resources.resource_filename('adriq', 'WM_SCL_DLL')

dll_name = 'SharedLib.dll'  # Replace with your DLL name
dll_path = os.path.join(dll_dir, dll_name)

lib = ctypes.CDLL(dll_path)

# Define the function argument types for RSet_Feedback
lib.RSet_Feedback.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int32]
lib.RSet_Feedback.restype = None
#initialise with a feedback of 0 to start with
feedback_array = np.array([0, 0, 0, 0, 0], dtype=np.float64)
array_len = len(feedback_array)
lib.RSet_Feedback(feedback_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), array_len)


def shift_397(shift):
    feedback_array = np.array([0, shift, 0, 0, 0], dtype=np.float64)
    array_len = len(feedback_array)

    # Measure the time taken to call the DLL function
    lib.RSet_Feedback(feedback_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), array_len)


def shift_854(shift):
    feedback_array = np.array([0, 0, shift, 0, 0], dtype=np.float64)
    array_len = len(feedback_array)

    # Measure the time taken to call the DLL function
    lib.RSet_Feedback(feedback_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), array_len)

def shift_866(shift):
    feedback_array = np.array([0, 0, 0, shift, 0], dtype=np.float64)
    array_len = len(feedback_array)

    # Measure the time taken to call the DLL function
    lib.RSet_Feedback(feedback_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), array_len)

def shift_850(shift):
    feedback_array = np.array([0, 0, 0, 0, shift], dtype=np.float64)
    array_len = len(feedback_array)

    # Measure the time taken to call the DLL function
    lib.RSet_Feedback(feedback_array.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), array_len)