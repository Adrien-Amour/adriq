import tkinter as tk
from tkinter import ttk
from adriq.ad9910 import *
from adriq.Counters import *
from adriq.RedLabs_Dac import *
from adriq.pulse_sequencer import *
from adriq.Custom_Tkinter import *
from adriq.experiment import *

# Assuming the following classes are defined elsewhere
# from your_module import LoadControlPanel, TrapControlFrame, get_pmt_manager
shift = 10

class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control Application")
        self.geometry("635x800")  # Adjusted width to accommodate both panels

        # Create a Notebook widget for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Current Control Panels
        self.current_controls_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.current_controls_tab, text="Current Controls")

        # Add all current sections to the first tab
        self.lasers = create_laser_objects(r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\dds_config.cfg", include_lasers=[
            "397a", "397b", "397c", "866", "866 OP", "850 RP", "854 Cav", "854 SP1", "850 SP1"
        ])

        self.laser_control = LaserControl(self.current_controls_tab)
        for laser in self.lasers:
            self.laser_control.add_laser(laser)

        self.laser_control.place(x=shift+0, y=0, anchor="nw", width=650, height=480)  # Adjust coordinates and size as needed
        self.laser_control.add_quick_preset_button("Cooling", r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\presets\cooling.json", bg="#AEC6CF")
        self.laser_control.add_quick_preset_button("Trapping", r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\presets\trapping.json", bg="#FFB6C1")

        self.load_control_panel = LoadControlPanel(self.current_controls_tab, PMT_Reader, Redlabs_DAC, Threshold=2000, Timeout=100)
        self.load_control_panel.place(x=shift+0, y=460, anchor="nw", width=580, height=380)  # Adjust coordinates and size as needed

        self.trap_control_frame = TrapControlFrame(self.current_controls_tab, QuTau_Reader, Redlabs_DAC, config_file=r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\dc_null_history.csv", default_trap_depth=0.8)
        self.trap_control_frame.place(x=shift+300, y=470, anchor="nw", width=580, height=380)  # Adjust coordinates and size as needed

        self.pulse_sequencer_frame = PulseSequencerFrame(self.current_controls_tab, defaultbitstring="0100000000000000", pulse_sequencer_port="COM5")
        self.pulse_sequencer_frame.place(x=shift+10, y=650, anchor="nw", width=300, height=50)  # Adjust coordinates and size as needed

        # Add a watermark to the first tab
        self.logo_label = Watermark(self.current_controls_tab)
        self.logo_label.place(x=shift+15, y=705, anchor="nw")  # Adjust coordinates as needed

        # Tab 2: Future Controls
        self.future_controls_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.future_controls_tab, text="Future Controls")

        # Placeholder for future controls
        future_label = tk.Label(self.future_controls_tab, text="Future controls will be added here.", font=("Arial", 14))
        future_label.pack(pady=20)

        # Tab 3: Experiment Control
        self.experiment_control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.experiment_control_tab, text="Experiment Control")

        # Load DDS dictionary and pulse sequencer
        dds_dict = load_dds_dict("ram", r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\dds_config.cfg")
        pulse_sequencer = Pulse_Sequencer(port="COM5")

        # Add ExperimentControlFrame to the third tab
        self.experiment_control_frame = ExperimentControlFrame(
            self.experiment_control_tab,
            dds_dict=dds_dict,
            pulse_sequencer=pulse_sequencer
        )
        self.experiment_control_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = ControlApp()
    app.mainloop()