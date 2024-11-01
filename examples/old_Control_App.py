import tkinter as tk
from tkinter import ttk
from itcm.ad9910 import *
from itcm.Count_Managers import *
from itcm.RedLabs_Dac import *

# Assuming the following classes are defined elsewhere
# from your_module import Laser, TrapControlFrame, LoadControlPanel, Live_Plot, get_pmt_manager, LaserControl

class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control Application")
        self.geometry("1200x800")

        # Create frames for layout
        self.create_frames()

        # Initialize LaserControl frame
        self.laser_control = LaserControl(self.laser_control_frame)
        self.laser_control.pack(fill=tk.BOTH, expand=True)

        # Create laser objects and add them to the laser control frame
        self.lasers = create_laser_objects()
        self.add_lasers_to_control_panel()

        # Initialize PMT manager and live plot
        self.pmt_manager = get_pmt_manager()
        self.pmt_counts = Live_Plot(self.live_plot_frame, self.pmt_manager)
        self.pmt_counts.pack(fill=tk.BOTH, expand=True)

        self.qutau_manager = get_qutau_manager()

        # Initialize TrapControlFrame
        self.trap_ctrl = TrapControlFrame(master=self.trap_control_frame, count_manager=self.qutau_manager, default_h=-1.292, default_v=-0.498, default_trap_depth=0.6)
        self.trap_ctrl.pack(fill=tk.BOTH, expand=True)

        # Initialize LoadControlPanel with correct parameters
        self.load_control_panel = LoadControlPanel(self.load_control_panel_frame, self.pmt_manager, 2000, 100)
        self.load_control_panel.pack(fill=tk.BOTH, expand=True)

    def create_frames(self):
        # Frame for laser controls on the left
        self.laser_control_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2, bg="red")
        self.laser_control_frame.grid(row=0, column=0, rowspan=3, padx=10, pady=10, sticky="ns")

        # Frame for live plot on the top right
        self.live_plot_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2, bg="green")
        self.live_plot_frame.grid(row=0, column=1, columnspan=2, padx=10, pady=10, sticky="nsew")

        # Frame for LoadControlPanel below the live plot on the left
        self.load_control_panel_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2, bg="blue")
        self.load_control_panel_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        # Frame for TrapControlFrame below the live plot on the right
        self.trap_control_frame = tk.Frame(self, relief=tk.RAISED, borderwidth=2, bg="yellow")
        self.trap_control_frame.grid(row=1, column=2, padx=10, pady=10, sticky="nsew")

        # Configure grid weights for resizing
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def add_lasers_to_control_panel(self):
        for laser in self.lasers:
            self.laser_control.add_laser(laser)

def create_laser_objects():
    """Creates laser objects based on the given configuration."""
    calib_directory = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment Files and VIs\AOM calibration VI\Calibration_Files"
    standalone_boards = "COM9"
    standalone_lasers = [
        ("397b", 0, "397b_calib.csv", 2900),
        ("OP 866", 1, "854_rp_calib.csv", 10700),
        ("397a", 2, "397a_calib.csv", 2400),
        ("RP 854", 3, "854_rp_calib.csv", 4800),
        ("RP 850", 5, "850_rp_calib.csv", 7450),
        ("866", 6, "866_calib.csv", 7800)
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