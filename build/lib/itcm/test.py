import tkinter as tk
from itcm.RedLabs_Dac import LoadControlPanel  # Adjust the import path as necessary

def main():
    # Create the main Tkinter window
    root = tk.Tk()
    root.title("Load Control Panel")

    # Create an instance of LoadControlPanel
    # Replace `Count_Manager`, `Threshold`, and `Timeout` with appropriate values
    count_manager = None  # Initialize your Count_Manager here
    threshold = 10  # Example threshold value
    timeout = 60  # Example timeout value in seconds

    load_control_panel = LoadControlPanel(root, count_manager, threshold, timeout)
    load_control_panel.pack(fill="both", expand=True)

    # Start the Tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    main()