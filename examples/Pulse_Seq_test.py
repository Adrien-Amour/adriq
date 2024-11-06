from adriq.pulse_sequencer import *

class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.load_control_panel = PulseSequencerFrame(self)

if __name__ == "__main__":
    app = ControlApp()
    app.mainloop()