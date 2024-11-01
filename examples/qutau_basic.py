# Example for using basic functions of the quTAU
#
# Author: qutools GmbH
# Last edited: Sep 2021
#
# Tested with python 3.9 (32 & 64 bit), numpy-1.13.3 and Windows 10 (64bit), install USB driver first
#
# This is demo code. Use at your own risk. No warranties.
#
# It may be used and modified with no restriction; raw copies as well as 
# modified versions may be distributed without limitation.
from itcm import QuTau
import time

# initialize device
qutau = QuTau.QuTau()
devType = qutau.getDeviceType()

if (devType == qutau.DEVTYPE_1A):
	print ("found quTAU!")
elif (devType == qutau.DEVTYPE_1B):
	print ("found quTAU(H)!")
elif (devType == qutau.DEVTYPE_1C):
	print ("found quPSI!")
elif (devType == qutau.DEVTYPE_2A):
	print ("found quTAG!")
else:
	print ("no suitable device found - demo mode activated")
	
print ("Device timebase:" + str(qutau.getTimebase()))

# configure channel 0
qutau.setSignalConditioning(0,qutau.SIGNALCOND_LVTTL,True,False,2) #LVTTL, rising edge, 5kOhm termination
qutau.setDivider(16,False)

# configure channel 2
qutau.setSignalConditioning(2,qutau.SIGNALCOND_LVTTL,True,False,2) #LVTTL, rising edge, 5kOhm termination





print("setBufferSize: ", qutau.err_dict[qutau.setBufferSize(1000000)])

# enable channels
qutau.enableChannels((0,1))


# measurement
firstTimestamps = qutau.getLastTimestamps(True)


for i in range(20):
#while(True):        
	
	lost = qutau.getDataLost()
	time.sleep(0.5)
	timestamps = qutau.getLastTimestamps(True)
	lost = qutau.getDataLost()
	print("lost data: ", lost)

	tstamp = timestamps[0]
	tchannel = timestamps[1]
	values = timestamps[2]

	channel1 = 0
	
	for k in range(values):
		if tchannel[k] == 1:
			channel1 += 1
	
	print ("number of timestamps in channel 1:"+str(2*channel1))

	
# deinitialize device
qutau.deInitialize()
