import tkinter as tk
from tkinter import ttk
from adriq.ad9910 import *
from adriq.Counters import *
from adriq.RedLabs_Dac import *
from adriq.pulse_sequencer import *

# Assuming the following classes are defined elsewhere
# from your_module import LoadControlPanel, TrapControlFrame, get_pmt_manager

class ControlApp(tk.Tk):
    def __init__(self):

        self.lasers = create_laser_objects()
    
        super().__init__()
        self.title("Control Application")
        self.geometry("600x1200")  # Adjusted width to accommodate both panels

        # Initialize LoadControlPanel with correct parameters
        self.load_control_panel = LoadControlPanel(self, PMT_Reader, Threshold=2000, Timeout=100)
        self.load_control_panel.place(x=0, y=460, anchor="nw", width=580, height=380)  # Adjust coordinates and size as needed

        # Initialize TrapControlFrame with correct parameters
        self.trap_control_frame = TrapControlFrame(self, QuTau_Reader, default_h=-1.27, default_v=-0.495, default_trap_depth=0.8)
        self.trap_control_frame.place(x=300, y=470, anchor="nw", width=580, height=380)  # Adjust coordinates and size as needed

        self.pulse_sequencer_frame = PulseSequencerFrame(self, defaultbitstring="0100000000000000", pulse_sequencer_port="COM5")
        self.pulse_sequencer_frame.place(x=10, y=650, anchor="nw", width=300, height=50)  # Adjust coordinates and size as needed
    
        self.laser_control = LaserControl(self)
        for laser in self.lasers:
            self.laser_control.add_laser(laser)


        self.laser_control.place(x=50, y=0, anchor="nw", width=550, height=480)  # Adjust coordinates and size as needed
        # Create laser objects and add them to the laser control frame

def create_laser_objects():
    """Creates laser objects based on the given configuration."""
    calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"
    standalone_boards = "COM9"
    standalone_lasers = [
        ("397a", 2, "397a_calib.csv", 2400),
        ("397b", 0, "397b_calib.csv", 2900),
        ("397c", 4, "397c_calib.csv", 1600),
        ("866", 6, "866_calib.csv", 7800),
        ("OP 866", 1, "854_rp_calib.csv", 10700),
        ("854 Cav", 3, "854_rp_calib.csv", 4800),
        ("RP 850", 5, "850_rp_calib.csv", 7450),
    ]
    
    lasers = []
    for name, board, calib_file, max_rf_power in standalone_lasers:
        laser = Laser(name, standalone_boards, "standalone", board, f"{calib_directory}\\{calib_file}", max_rf_power)
        lasers.append(laser)
    
    phaselocked_boards = "COM10"
    lasers.append(Laser("850 SP1", phaselocked_boards, "master", 0, f"{calib_directory}\\850_calib.csv", 15000))
    lasers.append(Laser("854 SP1", phaselocked_boards, "slave", 2, f"{calib_directory}\\854_calib.csv", 15000))

    return lasers


if __name__ == "__main__":
    app = ControlApp()
    app.mainloop()