import ctypes
import os
import sys
import pkg_resources
import numpy as np

class QuTau:
	def __init__(self):
		# Determine the DLL directory based on system architecture
		if sys.maxsize > 2**32:
			# 64-bit Python
			dll_dir = pkg_resources.resource_filename('adriq', 'DLL_64bit')
			dll_name = 'tdcbase.dll'
			print("Python 64 Bit - loading 64 Bit DLL")
		else:
			# 32-bit Python
			dll_dir = pkg_resources.resource_filename('adriq', 'DLL_32bit')
			dll_name = 'tdcbase.dll'
			print("Python 32 Bit - loading 32 Bit DLL")

		# Construct the full path to the DLL
		dll_path = os.path.join(dll_dir, dll_name)
		print("DLL Path:", dll_path)

		# Load the DLL
		self.qutools_dll = ctypes.windll.LoadLibrary(dll_path)
		self.devtype_dict = { 0: 'DEVTYPE_1A', #quTAU
			1: 'DEVTYPE_1B', # quTAU(H)
			2: 'DEVTYPE_1C', # quPSI
			3: 'DEVTYPE_2A', # quTAG
			4: 'DEVTYPE_NONE'}

		self.DEVTYPE_1A = 0
		self.DEVTYPE_1B = 1
		self.DEVTYPE_1C = 2
		self.DEVTYPE_2A = 3
		
		# Fileformats ----------------------------------------
		self.fileformat_dict = { 0: 'ASCII',
			1: 'BINARY',
			2: 'COMPRESSED',
			3: 'RAW',
			4: 'NONE' }
			
		self.FILEFORMAT_ASCII = 0
		self.FILEFORMAT_BINARY = 1
		self.FILEFORMAT_RAW = 2
		self.FILEFORMAT_NONE = 3
		
		# Signal conditioning --------------------------------
		self.signalcond_dict = { 0: 'TTL',
			1: 'LVTTL',
			2: 'NIM',
			3: 'MISC',
			4: 'NONE'}
		
		self.SIGNALCOND_TTL = 0
		self.SIGNALCOND_LVTTL = 1
		self.SIGNALCOND_NIM = 2
		self.SIGNALCOND_MISC = 3
		
		self.simtype_dict = { 0: 'FLAT',
			1: 'NORMAL',
			2: 'NONE'}
		
		self.SIMTYPE_FLAT = 0
		self.SIMTYPE_NORMAL = 1
		
		# Error types ----------------------------------------
		self.err_dict = {0 : 'No error', 
			1 : 'Receive timed out', 
			2 : 'No connection was established',
			3 : 'Error accessing the USB driver',
			4 : 'Unknown Error',
			5 : 'Unknown Error',
			6 : 'Unknown Error',
			7 : 'Can''t connect device because already in use',
			8 : 'Unknown error',
			9 : 'Invalid device number used in call',
			10 : 'Parameter in fct. call is out of range',
			11 : 'Failed to open specified file',
			12 : 'Library has != been initialized',
			13 : 'Requested Feature is != enabled',
			14 : 'Requested Feature is != available'}
			
		# ----------------------------------------------------
		self.dev_nr=-1
		
		self.Initialize()
		
		self._bufferSize = 1000000
		self.setBufferSize(self._bufferSize)
		
		self._deviceType = self.getDeviceType()
		self._timebase = self.getTimebase()
		
		self._featureHBT = self.checkFeatureHBT()
		self._featureLifetime = self.checkFeatureLifetime()
		
		print ("Found "+self.devtype_dict[self._deviceType]+" device.")
		
		print ("Initialized with QuTau DLL v%f"%(self.getVersion()))


# Init --------------------------------------------------------------	
	def Initialize(self): 
		ans = self.qutools_dll.TDC_init(self.dev_nr)
        
		if (ans != 0):
			print ("Error in TDC_init:" + self.err_dict[ans])
		return ans

	def deInitialize(self):
		ans = self.qutools_dll.TDC_deInit()
        
		if (ans != 0): # from the documentation: "never fails"
			print ("Error in TDC_deInit:" + self.err_dict[ans])
		return ans

# Device Info -------------------------------------------------------------
	def getVersion(self):
		func = self.qutools_dll.TDC_getVersion
		func.restype = ctypes.c_double
		ans = func()
		return ans        
	
	def getTimebase(self):
		timebase = ctypes.c_double()
		ans = self.qutools_dll.TDC_getTimebase(ctypes.byref(timebase))
		if (ans!=0):
			print ("Error in TDC_getTimebase:"+self.err_dict[ans])
		return timebase.value
	
	def getDeviceType(self):
		ans = self.qutools_dll.TDC_getDevType()
		return ans
	
	def checkFeatureHBT(self):
		ans = self.qutools_dll.TDC_checkFeatureHbt()
		if (ans == 1):
			return True # Feature available
		else:
			return False # Feature != available
	
	def checkFeatureLifetime(self):
		ans = self.qutools_dll.TDC_checkFeatureLifeTime()
		if (ans == 1):
			return True # Feature available
		else:
			return False # Feature != available

# multiple devices ---------------------------------	
	def addressDevice(self,deviceNumber):
		print ("!= implemented")
		return 0
	
	def connect(self,deviceNumber):
		print ("!= implemented")
		return 0
	
	def disconnect(self,deviceNumber):
		print ("!= implemented")
		return 0

	def discover(self,deviceNumber):
		print ("!= implemented")
		return 0

	def getCurrentAddress(self,deviceNumber):
		print ("!= implemented")
		return 0
		
	def getDeviceInfo(self,deviceNumber):
		devnum = ctypes.c_int321(deviceNumber)
		devicetype = ctypes.c_int32()
		deviceid = ctypes.c_int32()
		serialnumnber=ctypes.c_char_p()
		connected = ctypes.s_int32()
		
		ans = self.qutools_dll.TDC_getDeviceInfo(devnum,ctypes.byref(devicetype), ctypes.byref(deviceid), ctypes.byref(serialnumber), ctypes.byref(connected))
		
		if (ans!=0):
			print ("Error in TDC_getDeviceInfo:"+self.ans_dict[err])
			
		return (devicetype.value, deviceid.value, serialnumber.value,connected.value)
		
# Configure Channels ----------------------------------------------------------------
	def getSignalConditioning(self, channel):
		if (self._deviceType == self.DEVTYPE_1A):
			# != available for DEVTYPE-1A
			print ("Error: getSignalConditioning is != available for this device type")
			return -1
			
		chn = ctypes.c_int32(channel)
		conditioning = ctypes.c_int()
		edg = ctypes.c_int32()
		ter = ctypes.c_int32()
		threshold = ctypes.c_double()
		
		ans = self.qutools_dll.TDC_getSignalConditioning(chn, ctypes.byref(conditioning), ctypes.byref(edg), ctypes.byref(ter), ctypes.byref(threshold))
		
		if (ans != 0):
			print ("Error in TDC_getSignalConditioning:"+self.err_dict[ans])
			
		return (conditioning.value,edg.value == 1, ter.value == 1, threshold.value)
	
	def setSignalConditioning(self, channel, conditioning, edge, termination, threshold):
		if (self._deviceType == self.DEVTYPE_1A):
			# != available for DEVTYPE-1A
			print ("Error: setSignalConditioning is != available for this device type")
			return -1
		
		chn = ctypes.c_int32(channel)
		con = ctypes.c_int(conditioning)
		if (edge):
			edg = ctypes.c_int32(1) # True: Rising
		else:
			edg = ctypes.c_int32(0) # False: Falling
			
		if (termination):
			ter = ctypes.c_int32(1) # True: ON (50 Ohms)
		else:
			ter = ctypes.c_int32(0) # False: OFF (5 kOhms)
			
		thr = ctypes.c_double(threshold)
		
		ans = self.qutools_dll.TDC_configureSignalConditioning(chn,con,edg,ter,thr)
		if (ans != 0):
			print ("Error in TDC_configureSignalConditioning:"+self.err_dict[ans])
		return ans
	
	def getDivider(self):
		if (self._deviceType == self.DEVTYPE_1A):
			# != available for DEVTYPE-1A
			print ("Error: getDivider is != available for this device type")
			return -1
		
		divider = ctypes.c_int32()
		reconstruct = ctypes.c_bool()
		ans = self.qutools_dll.TDC_getSyncDivider(ctypes.byref(divider), ctypes.byref(reconstruct))	
		
		if (ans != 0):
			print ("Error in TDC_getSyncDivider:" + self.err_dict[ans])			
		return (divider.value, reconstruct.value)
		
	def setDivider(self, divider, reconstruct):
		if (self._deviceType == self.DEVTYPE_1A):
			# != available for DEVTYPE-1A
			print ("Error: setDivider is != available for this device type")
			return -1
		
		div = ctypes.c_int32(divider)
		rec = ctypes.c_bool(reconstruct)
		ans = self.qutools_dll.TDC_configureSyncDivider(div, rec)	
		if (ans != 0):
			print ("Error in TDC_configureSyncDivider:" + self.err_dict[ans])
		return ans
		
	def getChannelsDelay(self):
		print ("!= implemented")
		return 0
		
	def setChannelsDelay(self, delays):
		print ("!= implemented")
		return 0
		
	def getDeadTime(self):
		if (self._deviceType != self.DEVTYPE_2A):
			# only available in DEVTYPE_2A
			print ("Error: getDeadtime is != available for this device type")
			return -1
		
		print ("!= implemented")
		return 0
		
	def setDeadTime(self):
		if (self._deviceType != self.DEVTYPE_2A):
			# only available in DEVTYPE_2A
			print ("Error: getDeadtime is != available for this device type")
			return -1
		
		print ("!= implemented")
		return 0
	
	def setTermination(self, on):
		if (self.getDevType() != self_DEVTYPE_1A):
			# only available in DEVTYPE_1A
			print ("Error: setTermination != available for this device type")
			return -1
			
		print ("!= implemented")
		return 0
	
	def enableTDCInput(self, enable):
		print ("!= implemented")
		return 0
	
	def enableChannels(self, channels):
		if len(channels) > 0:
			bitstring = ''
			for k in range(max(channels)+1):
				if k in channels:
					bitstring = '1' + bitstring
				else:
					bitstring = '0' + bitstring
		else:
			bitstring = '0'

		channelMask = ctypes.c_int32(int(bitstring, 2))
		ans = self.qutools_dll.TDC_enableChannels(channelMask)
		if (ans!=0):
			print ("Error in TDC_enableChannels:"+self.err_dict[ans])
		
		return ans
		
# Define Measurements -------------------------------------------------------
	def setCoincidenceWindow(self, coincWin):
		coincidence = ctypes.c_int32(coincWin)
		ans = self.qutools_dll.TDC_setCoincidenceWindows(coincidence)
		if (ans!=0):
			print ("Error in TDC_setCoincidenceWindows:"+dict_err[ans])
		return 0
		
	def setExposureTime(self, expTime):
		exposure = ctypes.c_int32(expTime)
		ans = self.qutools_dll.TDC_setExposureTime(exposure)
		if (ans!=0):
			print ("Error in TDC_setExposureTime:"+dict_err[ans])
		return ans
		
	def getDeviceParams(self):
		chn = ctypes.c_int32()
		coinc = ctypes.c_int32()
		exptime = ctypes.c_int32()
		
		ans = self.qutools_dll.TDC_getDeviceParams(ctypes.byref(chn), ctypes.byref(coinc), ctypes.byref(exptime))
		if ans!=0:
			print ("Error in TDC_getDeviceParams:"+dict_err[ans])
		return (chn.value, coinc.value, exptime.value)

# Self test ---------------------------------------------------------------------
	def configureSelftest(self, channelmask, period, burstSize, burstDist):
		print ("!= implemented")
		return 0
	
	def generateTimestamps(self, simtype, par, count):
		print ("!= implemented")
		return 0
		
# Timestamping ---------------------------------------------------------
	def getBufferSize(self):
		sz = ctypes.c_int32()
        
		self.qutools_dll.TDC_getTimestampBufferSize.argtypes = [ctypes.POINTER(ctypes.c_int32)]
		self.qutools_dll.TDC_getTimestampBufferSize.restype = [ctypes.c_int32]
        
		ans = self.qutools_dll.TDC_setTimestampBufferSize(ctypes.byref(sz))
		if (ans!=0):
			print ("Error in TDC_getTimestampBufferSize:"+self.err_dict[ans])
		return sz.value
	
	def setBufferSize(self, size):
		self._bufferSize = size
		sz = ctypes.c_int32(size)
		ans = self.qutools_dll.TDC_setTimestampBufferSize(self._bufferSize)
		if (ans!=0):
			print ("Error in TDC_setTimestampBufferSize: "+self.err_dict[ans])
		return ans
		
	def getDataLost(self):
		lost = ctypes.c_int32()
		ans = self.qutools_dll.TDC_getDataLost(ctypes.byref(lost))
		if (ans!=0):
			print ("Error in TDC_getDataLost:"+self.err_dict[ans])
		return lost.value
		
	def freezeBuffers(self):
		return 0
	
	def getLastTimestamps(self,reset):
		res = ctypes.c_int32(reset)
		timestamps = np.zeros(int(self._bufferSize), dtype=np.int64)
		channels = np.zeros(int(self._bufferSize), dtype=np.int8)
		valid = ctypes.c_int32()
        
		self.qutools_dll.TDC_getLastTimestamps.argtypes = [ctypes.c_int32,ctypes.POINTER(ctypes.c_int64),ctypes.POINTER(ctypes.c_int8),ctypes.POINTER(ctypes.c_int32)]
		self.qutools_dll.TDC_getLastTimestamps.restype = ctypes.c_int32
        
		ans = self.qutools_dll.TDC_getLastTimestamps(reset,timestamps.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),channels.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),ctypes.byref(valid))
         
		if (ans!=0): # "never fails"
			print ("Error in TDC_getLastTimestamps:"+self.err_dict[ans])
			
		return (timestamps, channels, valid.value)
	
# File IO -------------------------------------------
	def writeTimestamps(self):
		print ("!= implemented")
		return 0
		
	def inputTimestamps(self, timestamps,channels,count):
		print ("!= implemented")
		return 0
	
	def readTimestamps(self, filename, fileformat):
		print ("!= implemented")
		return 0
		
# Counting --------------------------------------------
	def getCoincCounters(self):
		print ("!= implemented")
		return 0
# APD (qupsi) -------------------------------------------------------
# (!= implemented)

# Start-Stop --------------------------------------------------------

# Lifetime ----------------------------------------------------------

# HBT ---------------------------------------------------------------
	