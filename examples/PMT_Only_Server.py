from adriq.Counters import *
from adriq.Servers import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,  QFrame
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QCheckBox, QHBoxLayout
from PyQt5.QtCore import QTimer
import sys
if __name__ == "__main__":
    # Server.status_check(QuTau_Reader, max_que=5)
    
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    main_window.setWindowTitle("PMT Reader Live Counts")

    # Create the main widget and layout
    central_widget = QWidget()
    layout = QVBoxLayout()

    # Create the plotters
    plotter1 = LivePlotter(PMT_Reader)
    # plotter2 = LivePlotter(QuTau_Reader)
# 
    # Set fixed square size for each plotter
    square_size = 400  # Define the desired square size
    plotter1.setFixedSize(square_size, square_size)
    # plotter2.setFixedSize(square_size, square_size)

    # Add plotters to the layout
    layout.addWidget(plotter1)
    # layout.addWidget(plotter2)

    # Set layout to the central widget
    central_widget.setLayout(layout)
    main_window.setCentralWidget(central_widget)

    main_window.show()
    sys.exit(app.exec_())
