import time
import clr
from System import Decimal as NetDecimal
import tkinter as tk
from tkinter import ttk, messagebox
from adriq.Servers import Client
from adriq.Custom_Tkinter import *
import time
from decimal import Decimal
import libximc.highlevel as ximc

# -------------------------------
# IMPORTANT: SET YOUR KINESIS INSTALL DIRECTORY
# Kinesis must be installed, and you must provide the correct path to its .NET DLLs.
# Typically, the path is either:
#   - "C:\\Program Files\\Thorlabs\\Kinesis"          (for 64-bit)
#   - "C:\\Program Files (x86)\\Thorlabs\\Kinesis"    (for 32-bit systems)
# You can verify the exact path by finding files like: Thorlabs.MotionControl.DeviceManagerCLI.dll
# -------------------------------
KINESIS_PATH = "C:\\Program Files\\Thorlabs\\Kinesis"

# Add .NET assembly references using the install path
clr.AddReference(f"{KINESIS_PATH}\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference(f"{KINESIS_PATH}\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference(f"{KINESIS_PATH}\\Thorlabs.MotionControl.KCube.DCServoCLI.dll")

from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.KCube.DCServoCLI import *

class Thorlabs_Motorised_WaveplateMount:
    host = "localhost"
    port = 8008

    def __init__(self, serial_number="27502257", default_position=22.9, name="HWP"):
        self.serial_number = str(serial_number)
        self.default_position = NetDecimal(default_position)
        self.name = name
        self.current_position = NetDecimal(0.0)
        self.device = None

        self._connect_and_initialize()
        self.home()
        self.move_to_default()

    def _log(self, message):
        print(f"[{self.name}] {message}")

    def _connect_and_initialize(self):
        self._log("Connecting to device...")
        DeviceManagerCLI.BuildDeviceList()
        self.device = KCubeDCServo.CreateKCubeDCServo(self.serial_number)

        self.device.Connect(self.serial_number)
        time.sleep(0.25)
        self.device.StartPolling(250)
        time.sleep(0.25)
        self.device.EnableDevice()
        time.sleep(0.25)

        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)

        config = self.device.LoadMotorConfiguration(
            self.serial_number,
            DeviceConfiguration.DeviceSettingsUseOptionType.UseDeviceSettings
        )
        time.sleep(0.25)

        self._log(f"Connected to: {self.device.GetDeviceInfo().Description}")

    def home(self):
        self._log("Homing device...")
        self.device.Home(60000)
        self.current_position = NetDecimal(0.0)
        self._log("Homing complete.")

    def move_to(self, position):
        target = NetDecimal(float(position)) if not isinstance(position, NetDecimal) else position
        self._log(f"Moving to position: {target}")
        self.device.MoveTo(target, 60000)
        time.sleep(1)
        self.current_position = target
        self._log(f"Reached position: {self.current_position}")

    def move_to_default(self):
        self._log(f"Moving to default position: {self.default_position}")
        self.move_to(self.default_position)

    def get_position(self):
        pos = self.device.Position
        self.current_position = pos
        return float(str(pos))
    
    def get_name(self):
        return self.name

    def disconnect(self):
        self._log("Stopping and disconnecting...")
        self.device.StopPolling()
        self.device.Disconnect()
        self._log("Disconnected.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()




class Standa_Motorised_WaveplateMount:
    host = "localhost"
    port = 8009

    def __init__(self, device_uri="xi-com:\\.\COM3", default_position=164, name="QWP"):
        self.name = name
        if device_uri is None:
            self._log("No device_uri provided. Attempting to auto-detect device...")
            devices = list(ximc.enumerate_devices())
            if not devices:
                raise RuntimeError("No Standa devices found. Please connect a device.")
            self.device_uri = devices[0]['uri']  # <-- Extract the URI string from the dict
            self._log(f"Auto-detected device_uri: {self.device_uri}")
        else:
            self.device_uri = device_uri

        self.default_position = Decimal(default_position)
        self.current_position = Decimal(0.0)
        self.axis = None

        self._connect_and_initialize()
        self.home()
        self.move_to_default()

    def _log(self, message):
        print(f"[{self.name}] {message}")

    def _connect_and_initialize(self):
        self._log("Connecting to device...")
        MicrostepMode = ximc._flag_enumerations.MicrostepMode
        self.axis = ximc.Axis(self.device_uri)
        self.axis.open_device()
        # Set calibration: 1 user unit = 1 degree, microstep mode = 1 (full step)
        self.axis.set_calb(A=1/80.0, MicrostepMode=MicrostepMode.MICROSTEP_MODE_FULL)
        self._log("Device connected and calibrated.")

    def home(self):
        self._log("Homing device (moving to 0 degrees)...")
        self.axis.command_move_calb(0.0)
        while True:
            pos = self.axis.get_position_calb()
            if abs(pos.Position - 0.0) < 0.1:
                break
            time.sleep(0.1)
        self.current_position = Decimal(0.0)
        self._log("Homing complete.")

    def move_to(self, position):
        target = Decimal(position) if not isinstance(position, Decimal) else position
        self._log(f"Moving to position: {float(target):.4f} degrees")
        self.axis.command_move_calb(float(target))
        while True:
            pos = self.axis.get_position_calb()
            if abs(pos.Position - float(target)) < 0.1:
                break
            time.sleep(0.1)
        self.current_position = target
        self._log(f"Reached position: {float(self.current_position):.4f} degrees")


    def move_to_default(self):
        self._log(f"Moving to default position: {float(self.default_position):.4f} degrees")
        self.move_to(self.default_position)

    def get_name(self):
        return self.name
    
    def get_position(self):
        pos = self.axis.get_position_calb()
        return float(str(self.current_position))
    

    def close(self):
        if self.axis:
            self.axis.close_device()
            self._log("Device connection closed.")


class WaveplateMountControlPanel(tk.Frame):
    def __init__(self, master, WaveplateMount):
        super().__init__(master, relief=tk.RAISED, borderwidth=2)
        
        
        # Create a DAC client and store it as an instance variable
        self.waveplatemount = Client(WaveplateMount)
        self.name = self.waveplatemount.get_name()

        self.name = self.waveplatemount.get_name()
        # Create a label
        label = tk.Label(self, text=f"{self.name} Angle:")
        label.pack(side=tk.LEFT, padx=5)

        # Create a CustomSpinbox
        self.spinbox = CustomSpinbox(self, from_=0, to=360.0, initial_value=0.0, increment=10, width=10)
        self.spinbox.set_callback(self.move_to)  # Set the callback for the spinbox
        self.spinbox.pack(side=tk.LEFT, padx=5)

        # Start periodic voltage reading
        self.update_spinbox_with_current_angle()

    def move_to(self, angle):
        """Set the piezo voltage using the DAC client."""
        try:
            self.waveplatemount.move_to(angle)
            print(f"Waveplate Angle Set To: {angle} degrees")
        except Exception as e:
            print(f"Error setting wavelplate angle: {e}")

    def update_spinbox_with_current_angle(self):
        """Periodically update the spinbox with the current piezo voltage."""
        try:
            # Only update if the spinbox does NOT have focus
            if not self.spinbox.focus_get() == self.spinbox:
                current_angle = self.waveplatemount.get_position()
                self.spinbox.var.set(f"{current_angle:.3f}")
        except Exception as e:
            print(f"Error reading waveplate angle: {e}")

        self.after(1000, self.update_spinbox_with_current_angle)
