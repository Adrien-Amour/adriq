import pyvisa
import numpy as np
import time
import threading
from datetime import datetime
import csv
import sys
from adriq.Servers import Client
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QSpinBox,
    QScrollArea, QCheckBox, QFileDialog
)
from PyQt5.QtCore import QTimer
from datetime import datetime

class ScopeReader:
    host = "localhost"
    port = 8002
    def __init__(self, resource_id='USB0::0x1AB1::0x04CE::DS1ZA192712152::INSTR', rate=4):
        self.resource_id = resource_id
        self.rate = rate  # in Hz
        self.interval = 1 / rate
        self.running = False
        self.lock = threading.Lock()

        self.rm = pyvisa.ResourceManager()
        self.scope = self.rm.open_resource('USB0::0x1AB1::0x04CE::DS1ZA192712152::INSTR')
        self.scope.timeout = 5000  # ms

        self.channels = ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]
        self.preambles = {}
        self.voltages = {}
        self.timestamp = None

        self._setup_scope()
        self.start_acquisition()

    def _setup_scope(self):
        for ch in self.channels:
            self.scope.write(f":WAV:SOUR {ch}")
            self.scope.write(":WAV:MODE NORM")
            self.scope.write(":WAV:FORM BYTE")
            self.scope.write(":WAV:POIN:MODE RAW")
            preamble = self.scope.query(":WAV:PRE?").split(',')
            y_increment = float(preamble[7])
            y_origin = float(preamble[8])
            y_reference = float(preamble[9])
            self.preambles[ch] = (y_increment, y_origin, y_reference)

    def update_rate(self, new_rate):
        self.rate = new_rate
        self.interval = 1 / new_rate
        return True

    def get_rate(self):
        return self.rate

    def start_acquisition(self):
        if not self.running:
            self.running = True
            print("Oscilloscope acquisition started...")
            threading.Thread(target=self._acquisition_loop, daemon=True).start()
        return True

    def _acquisition_loop(self):
        while self.running:
            start_time = time.time()

            voltages = {}
            for ch in self.channels:
                try:
                    self.scope.write(f":WAV:SOUR {ch}")
                    y_increment, y_origin, y_reference = self.preambles[ch]
                    raw_data = self.scope.query_binary_values(":WAV:DATA?", datatype='B', container=np.array)
                    voltage = (raw_data - y_reference - y_origin) * y_increment
                    voltages[ch] = voltage
                except Exception as e:
                    print(f"Error reading {ch}: {e}")
                    voltages[ch] = None

            with self.lock:
                self.voltages = voltages
                self.timestamp = datetime.now()

            elapsed = time.time() - start_time
            time.sleep(max(0, self.interval - elapsed))

    def stop_acquisition(self):
        self.running = False
        return True

    def get_counts(self):
        with self.lock:
            return self.timestamp, self.voltages.copy()

    def close(self):
        self.stop_acquisition()
        self.scope.close()
        self.rm.close()
        print("Scope session closed.")



class ScopePlotter(QWidget):
    def __init__(self, scope_reader):
        super().__init__()
        self.scope_reader = scope_reader
        self.setMinimumWidth(1000)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
    
        # Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')
        self.plot_widget.setLabel('left', "Voltage", units='V', color='w', size='20pt')
        self.plot_widget.setLabel('bottom', "Sample Index", color='w', size='20pt')
        self.plot_widget.setYRange(-1, 14)  # <-- Add this line to fix y-axis
        self.layout.addWidget(self.plot_widget)
        self.plot_widget.setFixedHeight(300)  # Set to half the previous/default height (adjust as needed)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', "Voltage", units='V', color='w', size='20pt')
        self.plot_widget.setLabel('bottom', "Sample Index", color='w', size='20pt')
        self.layout.addWidget(self.plot_widget)

        # --- Controls Layout ---
        # First row: [Update Rate] [Spinbox] | Channel
        self.rate_row = QHBoxLayout()
        self.layout.addLayout(self.rate_row)

        self.update_rate_btn = QPushButton("Update Rate")
        self.update_rate_btn.setStyleSheet("font-size: 16pt; padding: 10px 20px;")
        self.update_rate_btn.clicked.connect(self.update_rate)
        self.rate_row.addWidget(self.update_rate_btn)

        self.rate_spinbox = QSpinBox()
        self.rate_spinbox.setRange(1, 1000)  # Match LivePlotter's range
        self.rate_spinbox.setValue(self.scope_reader.get_rate())
        self.rate_spinbox.setStyleSheet("font-size: 16pt; padding: 10px 20px;")
        self.rate_row.addWidget(self.rate_spinbox)

        self.rate_row.addStretch(1)

        self.channel_label = QLabel("Channel")
        self.channel_label.setStyleSheet("font-size: 16pt;")
        self.rate_row.addWidget(self.channel_label)

        # Second row: [Start/Stop] [Pause/Resume] [Start/Stop Log] | [Checkboxes]
        self.button_row = QHBoxLayout()
        self.layout.addLayout(self.button_row)

        self.acquisition_button = QPushButton("Start Acquisition")
        self.acquisition_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        self.acquisition_button.clicked.connect(self.toggle_acquisition)
        self.button_row.addWidget(self.acquisition_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.button_row.addWidget(self.pause_button)

        # self.log_button = QPushButton("Start Log")
        # self.log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: blue; color: white;")
        # self.log_button.clicked.connect(self.toggle_log)
        # self.button_row.addWidget(self.log_button)

        self.button_row.addStretch(1)  # Pushes checkboxes to the right

        # Channel checkboxes (vertical, right-aligned)
        self.checkbox_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_widget)
        self.checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox_widget.setLayout(self.checkbox_layout)
        self.channel_checkboxes = {}
        self.create_channel_checkboxes()
        self.button_row.addWidget(self.checkbox_widget)

        # State
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.update_interval = int(1000 / self.scope_reader.get_rate())
        self.timer.start(self.update_interval)

        self.is_paused = False
        self.is_logging = False
        self.is_acquiring = False
        self.log_writer = None
        self.log_file = None
        self.colors = ['w', 'r', 'g', 'b']
        

    def toggle_acquisition(self):
        """Start or stop acquisition from the oscilloscope."""
        if self.is_acquiring:
            self.scope_reader.stop_acquisition()
            self.acquisition_button.setText("Start Acquisition")
            self.acquisition_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        else:
            self.scope_reader.start_acquisition()
            self.acquisition_button.setText("Stop Acquisition")
            self.acquisition_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        self.is_acquiring = not self.is_acquiring


    def create_channel_checkboxes(self):
        for ch in self.scope_reader.channels:
            checkbox = QCheckBox(ch)
            checkbox.setChecked(True)
            self.checkbox_layout.addWidget(checkbox)
            self.channel_checkboxes[ch] = checkbox

    

    def update_rate(self, new_rate):
        self.scope_reader.update_rate(new_rate)
        self.update_interval = int(1000 / new_rate)
        self.timer.setInterval(self.update_interval)
        print(f"Rate updated to {new_rate} Hz ({self.update_interval} ms)")

    def toggle_pause(self):
        if self.is_paused:
            self.timer.start()
            self.pause_button.setText("Pause")
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: red; color: white;")
        else:
            self.timer.stop()
            self.pause_button.setText("Resume")
            self.pause_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: green; color: white;")
        self.is_paused = not self.is_paused

    def toggle_log(self):
        if self.is_logging:
            self.stop_log()
        else:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "CSV Files (*.csv)")
            if filename:
                self.log_file = open(filename, 'w', newline='')
                self.log_writer = csv.writer(self.log_file)
                header = ['Timestamp'] + list(self.scope_reader.channels)
                self.log_writer.writerow(header)
                self.is_logging = True
                self.log_button.setText("Stop Log")
                self.log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: purple; color: white;")
                print(f"Logging to {filename}")

    def stop_log(self):
        if self.log_file:
            self.log_file.close()
        self.log_writer = None
        self.log_file = None
        self.is_logging = False
        self.log_button.setText("Start Log")
        self.log_button.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: blue; color: white;")
        print("Logging stopped.")

    def update_plot(self):
        try:
            timestamp, voltages = self.scope_reader.get_counts()
            if voltages is None:
                return

            self.plot_widget.clear()
            for i, (ch, data) in enumerate(voltages.items()):
                if self.channel_checkboxes[ch].isChecked() and data is not None:
                    color = self.colors[i % len(self.colors)]
                    self.plot_widget.plot(data, pen=pg.mkPen(color, width=2), name=ch)

            if self.is_logging and timestamp:
                row = [timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')]
                for ch in self.scope_reader.channels:
                    if voltages[ch] is not None:
                        row.append(list(voltages[ch]))
                    else:
                        row.append("NaN")
                self.log_writer.writerow(row)

        except Exception as e:
            print(f"Plot update error: {e}")