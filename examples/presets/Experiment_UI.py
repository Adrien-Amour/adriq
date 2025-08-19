import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QTableWidget, QTableWidgetItem, 
                           QPushButton, QLabel, QSpinBox, QDoubleSpinBox, 
                           QFrame, QHeaderView, QSizePolicy, QListWidget, 
                           QLineEdit, QGroupBox, QFileDialog, QMessageBox, QAbstractItemView)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import numpy as np

# Add these imports for experiment functionality
from adriq.experiment import load_dds_dict, Pulse_Sequencer, Experiment_Builder, Experiment_Runner
from adriq.pulse_sequencer import control_pulse_sequencer

class LaserControlUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Control UI")
        self.setGeometry(100, 100, 900, 800)  # Increased height
        
        # Initialize experiment components
        self.dds_dict = None
        self.pulse_sequencer = None
        self.exp_sequence = None
        self.exp_runner = None
        self.current_preset_data = None
        self.section_data = {}  # Store section data for display
        
        # Set up the main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create the laser control frame (similar to your tkinter frame)
        self.create_laser_control_frame(layout)
        
        # Create the section management area
        self.create_section_management(layout)
        
        # Create the experiment execution area
        self.create_experiment_execution(layout)
        
    def create_laser_control_frame(self, parent_layout):
        """Create the main laser control frame with table and preset buttons"""
        
        # Main frame container (similar to ttk.Frame with raised border)
        main_frame = QFrame()
        main_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        main_frame.setLineWidth(2)
        main_frame.setContentsMargins(10, 10, 10, 10)
        
        frame_layout = QVBoxLayout(main_frame)
        
        # Create the laser table
        self.create_laser_table(frame_layout)
        
        # Create preset buttons
        self.create_preset_buttons(frame_layout)
        
        parent_layout.addWidget(main_frame)
    
    def create_laser_table(self, parent_layout):
        """Create the laser control table similar to LaserControl"""
        
        # Create table widget
        self.laser_table = QTableWidget()
        self.laser_table.setColumnCount(3)  # Name, Detuning, Power Fraction (removed Section Name)
        
        # Set headers - removed Section Name column
        headers = ["Name", "Detuning", "Power Fraction"]
        self.laser_table.setHorizontalHeaderLabels(headers)
        
        # Set table properties
        self.laser_table.setAlternatingRowColors(True)
        self.laser_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.laser_table.verticalHeader().setVisible(False)
        
        # Set minimum height to show all rows without scrolling
        self.laser_table.setMinimumHeight(350)  # Increased height
        
        # Set column widths to match the appearance
        header = self.laser_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)          # Detuning
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)          # Power Fraction
        
        # Add sample laser data (matching your typical laser names)
        sample_lasers = [
            "397a", "397b", "397c", "866", "866 OP", "850 RP", 
            "854 Cav", "854 SP1", "854 SP2", "850 SP1", "850 SP2"
        ]
        
        self.laser_table.setRowCount(len(sample_lasers))
        
        for row, laser_name in enumerate(sample_lasers):
            self.add_laser_row(row, laser_name)
        
        # Calculate and set the exact height needed
        row_height = self.laser_table.rowHeight(0) if self.laser_table.rowCount() > 0 else 30
        header_height = self.laser_table.horizontalHeader().height()
        total_height = header_height + (row_height * len(sample_lasers)) + 10  # +10 for margins
        self.laser_table.setFixedHeight(total_height)
        
        parent_layout.addWidget(self.laser_table)
    
    def add_laser_row(self, row, laser_name):
        """Add a single laser row to the table"""
        
        # Name column
        name_item = QTableWidgetItem(laser_name)
        name_item.setFlags(Qt.ItemIsEnabled)
        name_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.laser_table.setItem(row, 0, name_item)
        
        # Detuning spinbox
        detuning_spinbox = QDoubleSpinBox()
        detuning_spinbox.setRange(-50.0, 50.0)
        detuning_spinbox.setSingleStep(0.1)
        detuning_spinbox.setValue(0.0)
        detuning_spinbox.setSuffix(" MHz")
        self.laser_table.setCellWidget(row, 1, detuning_spinbox)
        
        # Power fraction spinbox
        power_spinbox = QDoubleSpinBox()
        power_spinbox.setRange(0.0, 1.0)
        power_spinbox.setSingleStep(0.01)
        power_spinbox.setValue(0.0)
        power_spinbox.setDecimals(3)
        self.laser_table.setCellWidget(row, 2, power_spinbox)
    
    def create_preset_buttons(self, parent_layout):
        """Create the preset buttons section"""
        
        # Create horizontal layout for buttons
        button_layout = QHBoxLayout()
        
        # Save Preset button
        save_btn = QPushButton("Save Preset")
        save_btn.setFixedHeight(35)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        button_layout.addWidget(save_btn)
        
        # Load Preset button - now functional
        load_btn = QPushButton("Load Preset")
        load_btn.setFixedHeight(35)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        load_btn.clicked.connect(self.load_preset)
        button_layout.addWidget(load_btn)
        
        # Add stretch to push buttons to the left
        button_layout.addStretch()
        
        parent_layout.addLayout(button_layout)
    
    def load_preset(self):
        """Load a preset from the Experiment Presets folder and automatically add as section"""
        # Define the preset directory
        preset_dir = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\presets"
        
        # Open file dialog to select preset file
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Experiment Preset", 
            preset_dir, 
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Load the preset file
                with open(file_path, 'r') as f:
                    preset_data = json.load(f)
                
                self.current_preset_data = preset_data
                
                # Update the laser table with preset data
                self.update_laser_table_from_preset(preset_data)
                
                # Get the preset name from filename (without extension)
                preset_name = os.path.splitext(os.path.basename(file_path))[0]
                
                # Automatically set the section name to the preset filename
                self.section_name_input.setText(preset_name)
                
                # Automatically add the section with the loaded preset data
                self.add_section_from_laser_control()
                
                self.status_label.setText(f"✓ Loaded preset: {preset_name} and added as section")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #4CAF50;
                        color: white;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                """)
                
            except Exception as e:
                self.status_label.setText(f"✗ Failed to load preset: {str(e)}")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #f44336;
                        color: white;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                """)
    
    def update_laser_table_from_preset(self, preset_data):
        """Update the laser table with data from the preset"""
        for row in range(self.laser_table.rowCount()):
            laser_name = self.laser_table.item(row, 0).text()
            
            if laser_name in preset_data:
                laser_data = preset_data[laser_name]
                
                # Update detuning
                if 'detuning' in laser_data:
                    detuning_widget = self.laser_table.cellWidget(row, 1)
                    if detuning_widget:
                        detuning_widget.setValue(float(laser_data['detuning']))
                
                # Update power fraction (optical_power)
                if 'optical_power' in laser_data:
                    power_widget = self.laser_table.cellWidget(row, 2)
                    if power_widget:
                        power_widget.setValue(float(laser_data['optical_power']))
    
    def get_active_laser_parameters(self):
        """Get parameters for all lasers with non-zero power"""
        active_lasers = {}
        for row in range(self.laser_table.rowCount()):
            laser_name = self.laser_table.item(row, 0).text()
            
            # Get detuning
            detuning_widget = self.laser_table.cellWidget(row, 1)
            detuning = detuning_widget.value() if detuning_widget else 0.0
            
            # Get power fraction
            power_widget = self.laser_table.cellWidget(row, 2)
            power_fraction = power_widget.value() if power_widget else 0.0
            
            # Only include lasers with non-zero power
            if power_fraction > 0:
                active_lasers[laser_name] = {
                    'detuning': detuning,
                    'power_fraction': power_fraction
                }
        
        return active_lasers
    
    def create_section_management(self, parent_layout):
        """Create the section management area"""
        
        # Create a group box for section management
        section_group = QGroupBox("Section Management")
        section_group.setFont(QFont("Arial", 12, QFont.Bold))
        section_layout = QVBoxLayout(section_group)
        
        # Create horizontal layout for input and buttons
        input_layout = QHBoxLayout()
        
        # Section name input
        input_layout.addWidget(QLabel("Section Name:"))
        self.section_name_input = QLineEdit()
        self.section_name_input.setPlaceholderText("Enter section name or load preset...")
        input_layout.addWidget(self.section_name_input)
        
        # Add section button - now connected to laser control
        add_btn = QPushButton("Add Section")
        add_btn.setFixedHeight(30)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_btn.clicked.connect(self.add_section_from_laser_control)
        input_layout.addWidget(add_btn)
        
        # Remove section button
        remove_btn = QPushButton("Remove Section")
        remove_btn.setFixedHeight(30)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        remove_btn.clicked.connect(self.remove_section)
        input_layout.addWidget(remove_btn)
        
        section_layout.addLayout(input_layout)
        
        # Create the section list with detailed information and drag-and-drop
        self.section_list = QListWidget()
        self.section_list.setMaximumHeight(200)
        
        # Enable drag and drop for reordering
        self.section_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.section_list.setDefaultDropAction(Qt.MoveAction)
        
        # Style the list
        self.section_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #333;
                border-radius: 3px;
                background-color: #f9f9f9;
                selection-background-color: #4CAF50;
                selection-color: white;
                font-family: monospace;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ddd;
            }
            QListWidget::item:hover {
                background-color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)
        
        # Add info label about drag and drop
        info_label = QLabel("Available Sections (drag to reorder):")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        section_layout.addWidget(info_label)
        section_layout.addWidget(self.section_list)
        
        parent_layout.addWidget(section_group)
    
    def create_experiment_execution(self, parent_layout):
        """Create the experiment execution area"""
        
        # Create a group box for experiment execution
        exec_group = QGroupBox("Experiment Execution")
        exec_group.setFont(QFont("Arial", 12, QFont.Bold))
        exec_layout = QVBoxLayout(exec_group)
        
        # Create button layout for experiment controls
        button_layout = QHBoxLayout()
        
        # Initialize Experiment button
        init_btn = QPushButton("Initialize Experiment")
        init_btn.setFixedHeight(35)
        init_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        init_btn.clicked.connect(self.initialize_experiment)
        button_layout.addWidget(init_btn)
        
        # Run Experiment button
        run_btn = QPushButton("Run Experiment")
        run_btn.setFixedHeight(35)
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        run_btn.clicked.connect(self.run_experiment)
        button_layout.addWidget(run_btn)
        
        button_layout.addStretch()
        exec_layout.addLayout(button_layout)
        
        # Create second row for save/load experiment buttons
        experiment_layout = QHBoxLayout()
        
        # Save Experiment button
        save_exp_btn = QPushButton("Save Experiment")
        save_exp_btn.setFixedHeight(35)
        save_exp_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        save_exp_btn.clicked.connect(self.save_experiment)
        experiment_layout.addWidget(save_exp_btn)
        
        # Load Experiment button
        load_exp_btn = QPushButton("Load Experiment")
        load_exp_btn.setFixedHeight(35)
        load_exp_btn.setStyleSheet("""
            QPushButton {
                background-color: #795548;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6D4C41;
            }
        """)
        load_exp_btn.clicked.connect(self.load_experiment)
        experiment_layout.addWidget(load_exp_btn)
        
        experiment_layout.addStretch()
        exec_layout.addLayout(experiment_layout)
        
        # Status label
        self.status_label = QLabel("Ready - No experiment initialized")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #e0e0e0;
                padding: 5px;
                border-radius: 3px;
                margin-top: 10px;
            }
        """)
        exec_layout.addWidget(self.status_label)
        
        parent_layout.addWidget(exec_group)
    
    def save_experiment(self):
        """Save the current experiment configuration (section order and data) to a file"""
        if not self.section_data:
            QMessageBox.warning(self, "Warning", "No sections to save. Please add some sections first.")
            return
        
        # Define the experiment directory
        experiment_dir = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\experiments"
        
        # Create directory if it doesn't exist
        os.makedirs(experiment_dir, exist_ok=True)
        
        # Open file dialog to save experiment file
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Experiment Configuration",
            experiment_dir,
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Get the current section order
                section_order = self.get_section_order()
                
                # Create experiment data structure
                experiment_data = {
                    "experiment_name": os.path.splitext(os.path.basename(file_path))[0],
                    "created_date": str(np.datetime64('now')),
                    "section_order": section_order,
                    "sections": {}
                }
                
                # Add each section's data
                for section_name in section_order:
                    if section_name in self.section_data:
                        experiment_data["sections"][section_name] = self.section_data[section_name]
                
                # Save to file
                with open(file_path, 'w') as f:
                    json.dump(experiment_data, f, indent=4)
                
                experiment_name = experiment_data["experiment_name"]
                QMessageBox.information(self, "Success", 
                                      f"Saved experiment '{experiment_name}' with {len(section_order)} sections:\n" +
                                      " → ".join(section_order))
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save experiment: {str(e)}")
    
    def load_experiment(self):
        """Load a complete experiment configuration from a file"""
        # Define the experiment directory
        experiment_dir = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\experiments"
        
        # Create directory if it doesn't exist
        os.makedirs(experiment_dir, exist_ok=True)
        
        # Open file dialog to select experiment file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Experiment Configuration",
            experiment_dir,
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Load the experiment file
                with open(file_path, 'r') as f:
                    experiment_data = json.load(f)
                
                # Validate experiment data structure
                if not all(key in experiment_data for key in ["experiment_name", "section_order", "sections"]):
                    QMessageBox.critical(self, "Error", "Invalid experiment file format")
                    return
                
                # Clear current sections
                self.section_list.clear()
                self.section_data.clear()
                
                # Load sections in the saved order
                section_order = experiment_data["section_order"]
                sections_data = experiment_data["sections"]
                
                # Restore each section
                for section_name in section_order:
                    if section_name in sections_data:
                        # Restore section data
                        self.section_data[section_name] = sections_data[section_name]
                        
                        # Create display text and add to list
                        display_text = self.create_section_display_text(section_name, sections_data[section_name])
                        self.section_list.addItem(display_text)
                
                experiment_name = experiment_data["experiment_name"]
                
                # Update status
                self.status_label.setText(f"Loaded experiment: {experiment_name} ({len(section_order)} sections)")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #4CAF50;
                        color: white;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                """)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load experiment: {str(e)}")
                self.status_label.setText(f"Failed to load experiment: {str(e)}")
                self.status_label.setStyleSheet("""
                    QLabel {
                        background-color: #f44336;
                        color: white;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 10px;
                    }
                """)
    
    def load_experiment_presets_for_sections(self):
        """Load the individual preset files for each section in the current experiment"""
        if not self.section_data:
            self.status_label.setText("⚠ No sections loaded. Please load an experiment first.")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        preset_dir = r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Python_Package2\ADRIQ\examples\presets"
        section_order = self.get_section_order()
        loaded_sections = []
        failed_sections = []
        
        for section_name in section_order:
            preset_file = os.path.join(preset_dir, f"{section_name}.json")
            
            if os.path.exists(preset_file):
                try:
                    # Load the preset file
                    with open(preset_file, 'r') as f:
                        preset_data = json.load(f)
                    
                    # Update the current section with preset data
                    loaded_sections.append(section_name)
                    
                except Exception as e:
                    failed_sections.append(f"{section_name}: {str(e)}")
            else:
                failed_sections.append(f"{section_name}: Not found")
        
        # Show results in status
        if loaded_sections and not failed_sections:
            self.status_label.setText(f"✓ All presets loaded: {', '.join(loaded_sections)}")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
        else:
            status_text = f"Presets - Loaded: {len(loaded_sections)}, Failed: {len(failed_sections)}"
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)

    def add_section_from_laser_control(self):
        """Add a section with parameters from the laser control table"""
        section_name = self.section_name_input.text().strip()
        if not section_name:
            self.status_label.setText("⚠ Please enter a section name")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        # Get active laser parameters (non-zero power)
        active_lasers = self.get_active_laser_parameters()
        
        if not active_lasers:
            self.status_label.setText("⚠ No lasers with non-zero power found in the laser table")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        # Check if section already exists
        if section_name in self.section_data:
            self.status_label.setText(f"⚠ Section '{section_name}' already exists")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        # Store section data
        self.section_data[section_name] = active_lasers
        
        # Create detailed display text
        display_text = self.create_section_display_text(section_name, active_lasers)
        
        # Add to section list with detailed information
        self.section_list.addItem(display_text)
        self.section_name_input.clear()
        
        # Show success message with laser info
        laser_names = list(active_lasers.keys())
        self.status_label.setText(f"✓ Added section '{section_name}' with {len(laser_names)} lasers: {', '.join(laser_names)}")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 5px;
                border-radius: 3px;
                margin-top: 10px;
            }
        """)
    
    def create_section_display_text(self, section_name, laser_data):
        """Create detailed display text for a section"""
        lines = [f"[{section_name}]"]
        
        for laser_name, params in laser_data.items():
            # Use the correct parameter names from your data structure
            power_fraction = params.get('power_fraction', 0)
            detuning = params.get('detuning', 0)
            lines.append(f"  {laser_name}: {power_fraction:.3f} @ {detuning:+.1f} MHz")
        
        return "\n".join(lines)


    def remove_section(self):
        """Remove selected section from the list"""
        current_item = self.section_list.currentItem()
        if current_item:
            # Extract section name from display text
            item_text = current_item.text()
            section_name = item_text.split(']')[0][1:]  # Extract name from [section_name]
            
            # Remove from data and list
            if section_name in self.section_data:
                del self.section_data[section_name]
            
            self.section_list.takeItem(self.section_list.row(current_item))
            self.status_label.setText(f"✓ Removed section '{section_name}'")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
        else:
            self.status_label.setText("⚠ Please select a section to remove")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
    
    def initialize_experiment(self):
        """Initialize the experiment components"""
        try:
            # Initialize components (similar to your Bidrive_optimising.py)
            self.dds_dict = load_dds_dict("ram", r"C:\Users\probe\OneDrive - University of Sussex\Desktop\Experiment_Config\dds_config.cfg")
            self.pulse_sequencer = Pulse_Sequencer()
            self.exp_sequence = Experiment_Builder(self.dds_dict, self.pulse_sequencer, ram_step=0.08)
            
            # Initialize experiment runner
            self.exp_runner = Experiment_Runner(
                self.dds_dict,
                self.pulse_sequencer,
                timeout=100,
                pmt_threshold=1500,
                expected_fluorescence=6000,
                pulse_expected_fluorescence=1500,
                sp_threshold=None,
                load_timeout=100,
                trigger_mode="ram",
                cavity_lock=True,
            )
            
            # Set basic parameters
            self.exp_sequence.set_detunings(detuning_dict={
                "850 SP1": -28.2, "850 SP2": 27.4, "854 SP1": 0, "854 SP2": 0, 
                "397a": -18, "854 Cav": 0, "397c": -18, "866": -18, "866 OP": 30, "850 RP": 0
            })
            
            self.exp_sequence.set_trapping_parameters(
                trapping_detuning_dict={"397c": -50},
                trapping_amplitude_dict={"397c": 0.8}
            )
            
            # Create cooling section
            self.exp_sequence.create_cooling_section(length=6, amplitude_dict={"397c": 0.3, "854 SP1": 0.1, "850 RP": 0.2})
            
            self.status_label.setText("✓ Experiment initialized successfully")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            
        except Exception as e:
            self.status_label.setText(f"✗ Failed to initialize experiment: {str(e)}")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #f44336;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
    
    def run_experiment(self):
        """Run the experiment with all sections in the list (in order)"""
        if not self.exp_sequence:
            self.status_label.setText("⚠ Please initialize experiment first")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        if not self.section_data:
            self.status_label.setText("⚠ No sections to run")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #FF9800;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            return
        
        try:
            # Get sections in the order they appear in the list
            section_order = self.get_section_order()
            
            # Load each section in order
            for section_name in section_order:
                if section_name in self.section_data:
                    self.load_section_preset(section_name)
                else:
                    print(f"Warning: Section '{section_name}' not found in section_data")
            
            # Build and flash the experiment
            self.exp_sequence.build_ram_arrays()
            self.exp_sequence.flash()
            
            self.status_label.setText(f"🚀 Experiment running with {len(section_order)} sections: {' → '.join(section_order)}")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #2196F3;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
            
        except Exception as e:
            self.status_label.setText(f"✗ Failed to run experiment: {str(e)}")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #f44336;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                    margin-top: 10px;
                }
            """)
    
    def get_section_order(self):
        """Get the current order of sections in the list"""
        section_order = []
        for i in range(self.section_list.count()):
            item = self.section_list.item(i)
            item_text = item.text()
            section_name = item_text.split(']')[0][1:]  # Extract name from [section_name]
            section_order.append(section_name)
        return section_order
    
    def load_section_preset(self, section_name):
        """Load a section preset based on the section name and stored laser settings"""
        
        # Get stored laser parameters for this section
        if section_name not in self.section_data:
            print(f"No data found for section: {section_name}")
            return
        
        section_lasers = self.section_data[section_name]
        
        # Create DDS functions (constant amplitude)
        dds_functions = {}
        for laser_name, params in section_lasers.items():
            amplitude = params['power_fraction']
            dds_functions[laser_name] = lambda t, amp=amplitude: amp
        
        if not dds_functions:
            print(f"No active lasers found for section: {section_name}")
            return
        
        # Define section parameters based on section name
        section_params = self.get_section_parameters(section_name)
        
        # Create the section
        self.exp_sequence.create_section(
            name=section_name,
            duration=section_params['duration'],
            dds_functions=dds_functions,
            pmt_gate_high=section_params['pmt_gate_high']
        )
        
        print(f"Loaded section: {section_name} with {len(dds_functions)} active lasers")
    
    def get_section_parameters(self, section_name):
        """Get default parameters for different section types"""
        section_defaults = {
            'cooling': {'duration': 6, 'pmt_gate_high': False},
            'optical pumping': {'duration': 12, 'pmt_gate_high': True},
            'pump to ground state': {'duration': 2, 'pmt_gate_high': True},
            'stirap': {'duration': 6, 'pmt_gate_high': False},
            'single photon': {'duration': 7, 'pmt_gate_high': False},
            'trapping': {'duration': 10, 'pmt_gate_high': False}
        }
        
        # Default parameters if section type not found
        default_params = {'duration': 5, 'pmt_gate_high': False}
        
        return section_defaults.get(section_name.lower(), default_params)

class ExperimentUI(QMainWindow):
    """Main window that could contain multiple control panels"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Experiment Control UI")
        self.setGeometry(50, 50, 1100, 1100)  # Increased height for larger table
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add title
        title_label = QLabel("Experiment Control Interface")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # Add the laser control widget
        self.laser_control = LaserControlUI()
        
        # Extract the laser control frame from LaserControlUI
        laser_frame = self.laser_control.centralWidget()
        layout.addWidget(laser_frame)
        
        # Add some spacing
        layout.addStretch()
        
        # Status bar
        self.statusBar().showMessage("Ready - Load presets and configure experiment")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show the main window
    window = ExperimentUI()
    window.show()
    
    sys.exit(app.exec_())