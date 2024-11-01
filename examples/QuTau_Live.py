import tkinter as tk
# Assuming QuTau_Manager and Live_Plot classes are defined in Count_Managers.py
from itcm.Count_Managers import QuTau_Manager, Live_Plot

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Live Plot App")
        self.geometry("800x600")

        # Instantiate the QuTau_Manager
        self.count_manager = QuTau_Manager()

        # Update the active channels to single photons and PMT counts
        channels = [1, 3]  # List of channels
        self.count_manager.update_active_channels(channels)

        # Create the Live_Plot frame and add it to the app
        self.live_plot = Live_Plot(self, self.count_manager)
        self.live_plot.pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()