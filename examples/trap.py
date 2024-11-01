import tkinter as tk
from tkinter import ttk
from adriq.ad9910 import *
from adriq.Counters import *
from adriq.RedLabs_Dac import *

# Assuming the following classes are defined elsewhere
# from your_module import TrapControlFrame, get_qutau_manager

class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control Application")
        self.geometry("800x600")  # Adjusted size for the trap control panel
        print("suck ur mum")
        # Initialize TrapControlFrame with correct parameters
        self.trap_control_frame = TrapControlFrame(self, count_reader = QuTau_Reader, default_h=-1.292, default_v=-0.495, default_trap_depth=0.8)
        self.trap_control_frame.place(x=10, y=10, anchor="nw", width=780, height=580)  # Adjust coordinates and size as needed

if __name__ == "__main__":
    app = ControlApp()
    app.mainloop()