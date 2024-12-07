import sys
import time
import threading
import subprocess
import re
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
sys.dont_write_bytecode = True

# ------------------------ Logging Configuration ------------------------

# Configure logging to output to both console and a log file
#logging.basicConfig(
#    level=logging.DEBUG,
#    format='%(asctime)s - %(levelname)s - %(message)s',
#    handlers=[
#        logging.FileHandler("blue_pulse.log"),
#        logging.StreamHandler(sys.stdout)
#    ]
#)

# Disable all logging messages
logging.disable(logging.CRITICAL)

# ------------------------ Helper Functions ------------------------

def run_pactl_command(command):
    """Run a pactl command and return the output."""
    try:
        logging.debug(f"Running pactl command: {' '.join(['pactl'] + command)}")
        result = subprocess.run(['pactl'] + command, capture_output=True, text=True, check=True)
        logging.debug(f"pactl output: {result.stdout.strip()}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running pactl {' '.join(command)}: {e.stderr.strip()}")
        return ""

def get_default_sink():
    """Get the default sink name."""
    output = run_pactl_command(['get-default-sink'])
    default_sink = output.strip()
    logging.debug(f"Default sink: {default_sink}")
    if default_sink.lower() == 'pipewire':
        # Fallback to the first available sink
        sinks = list_sinks()
        if sinks:
            default_sink = sinks[0]['name']
            logging.info(f"Default sink set to first available sink: {default_sink}")
    return default_sink

def get_default_source():
    """Get the default source name."""
    output = run_pactl_command(['get-default-source'])
    default_source = output.strip()
    logging.debug(f"Default source: {default_source}")
    if default_source.lower() == 'pipewire':
        # Fallback to the first available source
        sources = list_sources()
        if sources:
            default_source = sources[0]['name']
            logging.info(f"Default source set to first available source: {default_source}")
    return default_source

def list_sinks():
    """List all sinks with their details."""
    output = run_pactl_command(['list', 'sinks'])
    sinks = []
    sink = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Sink #'):
            if sink:
                sinks.append(sink)
                sink = {}
            sink['index'] = line.split('#')[1].strip()
        elif line.startswith('Name:'):
            sink['name'] = line.split(':', 1)[1].strip()
        elif line.startswith('Description:'):
            sink['description'] = line.split(':', 1)[1].strip()
    if sink:
        sinks.append(sink)
    logging.debug(f"Available Sinks: {sinks}")
    return sinks

def list_sources():
    """List all sources with their details."""
    output = run_pactl_command(['list', 'sources'])
    sources = []
    source = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Source #'):
            if source:
                sources.append(source)
                source = {}
            source['index'] = line.split('#')[1].strip()
        elif line.startswith('Name:'):
            source['name'] = line.split(':', 1)[1].strip()
        elif line.startswith('Description:'):
            source['description'] = line.split(':', 1)[1].strip()
    if source:
        sources.append(source)
    logging.debug(f"Available Sources: {sources}")
    return sources

def set_default_sink_cmd(sink_name):
    """Set the default sink."""
    logging.info(f"Setting default sink to: {sink_name}")
    run_pactl_command(['set-default-sink', sink_name])

def set_default_source_cmd(source_name):
    """Set the default source."""
    logging.info(f"Setting default source to: {source_name}")
    run_pactl_command(['set-default-source', source_name])

def set_sink_volume_cmd(sink_name, volume):
    """Set the volume for a sink (0-100)."""
    logging.info(f"Setting volume for sink {sink_name} to {volume}%")
    run_pactl_command(['set-sink-volume', sink_name, f"{volume}%"])

def set_source_volume_cmd(source_name, volume):
    """Set the volume for a source (0-100)."""
    logging.info(f"Setting volume for source {source_name} to {volume}%")
    run_pactl_command(['set-source-volume', source_name, f"{volume}%"])

def get_sink_volume_cmd(sink_name):
    """Get the current volume of a sink."""
    output = run_pactl_command(['get-sink-volume', sink_name])
    match = re.search(r'front-left:.*?(\d+)%', output)
    if match:
        volume = int(match.group(1))
        logging.debug(f"Volume for sink {sink_name}: {volume}%")
        return volume
    logging.warning(f"Could not determine volume for sink {sink_name}")
    return 0

def get_source_volume_cmd(source_name):
    """Get the current volume of a source."""
    output = run_pactl_command(['get-source-volume', source_name])
    match = re.search(r'front-left:.*?(\d+)%', output)
    if match:
        volume = int(match.group(1))
        logging.debug(f"Volume for source {source_name}: {volume}%")
        return volume
    logging.warning(f"Could not determine volume for source {source_name}")
    return 0

def get_sink_mute_cmd(sink_name):
    """Get the mute status of a sink."""
    output = run_pactl_command(['get-sink-mute', sink_name])
    is_muted = 'yes' in output.lower()
    logging.debug(f"Mute status for sink {sink_name}: {is_muted}")
    return is_muted

def get_source_mute_cmd(source_name):
    """Get the mute status of a source."""
    output = run_pactl_command(['get-source-mute', source_name])
    is_muted = 'yes' in output.lower()
    logging.debug(f"Mute status for source {source_name}: {is_muted}")
    return is_muted

def set_sink_mute_cmd(sink_name, mute):
    """Set the mute status of a sink."""
    logging.info(f"Setting mute for sink {sink_name} to {'mute' if mute else 'unmute'}")
    run_pactl_command(['set-sink-mute', sink_name, '1' if mute else '0'])

def set_source_mute_cmd(source_name, mute):
    """Set the mute status of a source."""
    logging.info(f"Setting mute for source {source_name} to {'mute' if mute else 'unmute'}")
    run_pactl_command(['set-source-mute', source_name, '1' if mute else '0'])

def get_card_for_device(address):
    """Get the card name for a given Bluetooth device address."""
    output = run_pactl_command(['list', 'cards'])
    card_name = None
    current_card = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Card #'):
            # New card section
            current_card = line.split('#')[1].rstrip(':')
        elif line.startswith('Name:') and current_card:
            name = line.split(':', 1)[1].strip()
            expected_prefix = f'bluez_card.{address.replace(":", "_").lower()}'
            if name.startswith(expected_prefix):
                card_name = name
                logging.debug(f"Found card {card_name} for address {address}")
                break
    if not card_name:
        logging.warning(f"No card found for device address: {address}")
    return card_name

def set_card_profile(card_name, profile):
    """Set the profile for a card."""
    logging.info(f"Setting profile for card {card_name} to {profile}")
    run_pactl_command(['set-card-profile', card_name, profile])

# ------------------------ GUI Components ------------------------

class VolumeBar(QtWidgets.QWidget):
    volumeChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._volume = 50
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0);")

    def setVolume(self, volume):
        self._volume = max(0, min(volume, 100))
        self.update()
        self.volumeChanged.emit(self._volume)

    def getVolume(self):
        return self._volume

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.adjustVolume(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            self.adjustVolume(event.pos())

    def adjustVolume(self, position):
        rect = self.rect()
        new_volume = int((position.x() / rect.width()) * 100)
        self.setVolume(new_volume)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        bar_count, bar_spacing = 15, 4
        bar_width = (rect.width() - (bar_spacing * (bar_count - 1))) / bar_count
        active_bars = int((self._volume / 100) * bar_count)

        for i in range(bar_count):
            x = i * (bar_width + bar_spacing)
            if i < active_bars:
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))  # White for active
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
            else:
                painter.setBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50)))   # Dark Gray for inactive
                painter.setPen(QtGui.QPen(QtGui.QColor(50, 50, 50), 1))

            painter.drawRoundedRect(int(x), 0, int(bar_width), rect.height(), 3, 3)

class VolumeController(QtWidgets.QWidget):
    devices_updated = QtCore.pyqtSignal()
    bluetooth_devices_updated = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

        # Initialize audio devices
        self.sinks = list_sinks()
        self.sources = list_sources()
        self.default_sink = get_default_sink()
        self.default_source = get_default_source()

        logging.debug("Connected to PipeWire via pactl.")

        self.is_muted = get_sink_mute_cmd(self.default_sink)
        self.is_input_muted = get_source_mute_cmd(self.default_source)

        # Connect the signals to respective slots
        self.devices_updated.connect(self.refresh_audio_devices)
        self.bluetooth_devices_updated.connect(self.refresh_bluetooth_devices)

        # Start PulseAudio (PipeWire) event listener
        self.start_pulse_event_listener()

        self.init_ui()

        # Populate Bluetooth devices on initialization
        self.populate_bluetooth_devices()

        # Automatically connect to already paired Bluetooth devices
        self.connect_paired_bluetooth_devices()

        # Start listening for D-Bus signals
        self.start_dbus_signal_listener()

    def init_ui(self):
        self.setWindowTitle('Blue Pulse')
        self.resize(800, 500)

        self.setStyleSheet("""
            QWidget {
                background-color: #000000; /* Black background */
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 12px;
                color: #FFFFFF; /* White text */
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QLabel {
                background: none;
                font-weight: bold;
                color: #FFFFFF; /* White text */
                text-align: center;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: bold;
                color: #FFFFFF; /* White text */
                margin-bottom: 10px;
            }
            QLabel#volumeLabel, QLabel#deviceLabel {
                font-size: 14px;
                color: #FFFFFF; /* White text */
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-radius: 6px;
                padding: 4px 10px;
                background: rgba(255, 255, 255, 0.05);
                min-width: 120px;
                margin: 5px auto;
            }
            QComboBox {
                background: #333333; /* Dark gray background */
                border: 1px solid #FFFFFF; /* White border */
                color: #FFFFFF; /* White text */
                padding: 5px;
                border-radius: 8px;
                font-size: 14px;
            }
            QComboBox:hover {
                background: #444444; /* Slightly lighter gray on hover */
                border: 1px solid #FFFFFF;
            }
            QComboBox QAbstractItemView {
                background: #222222; /* Darker background for dropdown */
                color: #FFFFFF; /* White text */
                border: none;
                selection-background-color: #555555; /* Gray selection background */
            }
            QPushButton {
                background-color: #444444; /* Dark gray background */
                border: none;
                color: #FFFFFF; /* White text */
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555555; /* Lighter gray on hover */
            }
            QListWidget {
                background-color: #333333; /* Dark gray background */
                border: 1px solid #FFFFFF; /* White border */
                color: #FFFFFF; /* White text */
                padding: 5px;
                border-radius: 8px;
            }
            QPushButton#refreshButton {
                background-color: #555555; /* Darker gray for refresh button */
                color: #FFFFFF;
            }
            QPushButton#refreshButton:hover {
                background-color: #666666; /* Lighter gray on hover */
            }
        """)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left Side (Volume Controls)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(10)

        # Title Label
        self.title_label = QtWidgets.QLabel("Volume Controller")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)

        # New Labels for Device Names
        self.output_device_label = QtWidgets.QLabel(f"Output Device: {self.get_device_display_name(self.default_sink)}")
        self.output_device_label.setObjectName("deviceLabel")
        self.output_device_label.setAlignment(QtCore.Qt.AlignCenter)

        self.input_device_label = QtWidgets.QLabel(f"Input Device: {self.get_device_display_name(self.default_source)}")
        self.input_device_label.setObjectName("deviceLabel")
        self.input_device_label.setAlignment(QtCore.Qt.AlignCenter)

        # Output Device Selector
        self.device_selector = QtWidgets.QComboBox()
        self.populate_output_devices()
        self.device_selector.currentIndexChanged.connect(self.change_sink)

        # Output Volume Bar and Label
        self.label = QtWidgets.QLabel(f'Output Volume: {get_sink_volume_cmd(self.default_sink)}%')
        self.label.setObjectName("volumeLabel")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.volume_bar = VolumeBar(self)
        self.volume_bar.setFixedHeight(60)
        self.volume_bar.setVolume(get_sink_volume_cmd(self.default_sink))
        self.volume_bar.volumeChanged.connect(self.set_volume)

        # Input Device Selector
        self.input_selector = QtWidgets.QComboBox()
        self.populate_input_devices()
        self.input_selector.currentIndexChanged.connect(self.change_source)

        # Input Volume Bar and Label
        self.input_label = QtWidgets.QLabel(f'Input Volume: {get_source_volume_cmd(self.default_source)}%')
        self.input_label.setObjectName("volumeLabel")
        self.input_label.setAlignment(QtCore.Qt.AlignCenter)
        self.input_volume_bar = VolumeBar(self)
        self.input_volume_bar.setFixedHeight(60)
        self.input_volume_bar.setVolume(get_source_volume_cmd(self.default_source))
        self.input_volume_bar.volumeChanged.connect(self.set_input_volume)

        # Assemble Left Layout
        left_layout.addWidget(self.title_label)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.output_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Output Device:"))
        left_layout.addWidget(self.device_selector)
        left_layout.addWidget(self.label)
        left_layout.addWidget(self.volume_bar)
        left_layout.addSpacing(20)
        left_layout.addWidget(self.input_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Input Device:"))
        left_layout.addWidget(self.input_selector)
        left_layout.addWidget(self.input_label)
        left_layout.addWidget(self.input_volume_bar)
        left_layout.addStretch()

        # Right Side (Bluetooth Controls)
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(10)

        self.bluetooth_label = QtWidgets.QLabel("Bluetooth Devices:")
        self.bluetooth_label.setAlignment(QtCore.Qt.AlignCenter)

        self.scan_button = QtWidgets.QPushButton("Scan")
        self.pair_button = QtWidgets.QPushButton("Pair")
        self.unpair_button = QtWidgets.QPushButton("Unpair")
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")

        self.device_list = QtWidgets.QListWidget()
        self.device_list.setFixedWidth(300)
        self.device_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.device_list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.scan_button.clicked.connect(self.start_scan)
        self.pair_button.clicked.connect(self.pair_device)
        self.unpair_button.clicked.connect(self.unpair_device)
        self.refresh_button.clicked.connect(self.refresh_all_devices)

        # Connect double-click event
        self.device_list.itemDoubleClicked.connect(self.set_bluetooth_device_as_default)

        # Buttons Layout
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.pair_button)
        buttons_layout.addWidget(self.unpair_button)
        buttons_layout.addWidget(self.refresh_button)

        right_layout.addWidget(self.bluetooth_label)
        right_layout.addWidget(self.scan_button)
        right_layout.addWidget(self.device_list)
        right_layout.addLayout(buttons_layout)
        right_layout.addStretch()

        # Add left and right layouts to main layout
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        # Center the window on the screen
        self.center_window()

    def center_window(self):
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def get_device_display_name(self, device_name):
        """Return the description of the device given its name."""
        for sink in self.sinks:
            if sink['name'] == device_name:
                return sink['description']
        for source in self.sources:
            if source['name'] == device_name:
                return source['description']
        return device_name  # Fallback to device_name if description not found

    def populate_output_devices(self):
        self.device_selector.blockSignals(True)
        self.device_selector.clear()
        self.sinks = list_sinks()
        logging.info("Available Output Devices:")
        # Add pactl sinks
        for sink in self.sinks:
            logging.info(f"- {sink['name']}: {sink['description']}")
            self.device_selector.addItem(sink['description'], {'type': 'sink', 'data': sink})
        # Set current index to default sink
        default_sink_name = self.default_sink
        for index in range(self.device_selector.count()):
            item_data = self.device_selector.itemData(index)
            if item_data['type'] == 'sink' and item_data['data']['name'] == default_sink_name:
                self.device_selector.setCurrentIndex(index)
                break
        self.device_selector.blockSignals(False)

    def populate_input_devices(self):
        self.input_selector.blockSignals(True)
        self.input_selector.clear()
        self.sources = list_sources()
        logging.info("Available Input Devices:")
        # Add pactl sources
        for source in self.sources:
            logging.info(f"- {source['name']}: {source['description']}")
            self.input_selector.addItem(source['description'], {'type': 'source', 'data': source})
        # Set current index to default source
        default_source_name = self.default_source
        for index in range(self.input_selector.count()):
            item_data = self.input_selector.itemData(index)
            if item_data['type'] == 'source' and item_data['data']['name'] == default_source_name:
                self.input_selector.setCurrentIndex(index)
                break
        self.input_selector.blockSignals(False)

    def get_paired_bluetooth_devices(self):
        """Retrieve a dictionary of paired Bluetooth devices."""
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        devices = {}
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                address = device_properties.get('Address', '')
                name = device_properties.get('Name', address)
                paired = device_properties.get('Paired', False)
                if paired:
                    devices[address] = name
        logging.debug(f"Paired Bluetooth Devices: {devices}")
        return devices

    def populate_bluetooth_devices(self):
        """Populate the Bluetooth devices list with paired devices."""
        self.device_list.clear()
        paired_devices = self.get_paired_bluetooth_devices()
        for address, name in paired_devices.items():
            item_text = f"{name} [{address}]"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.UserRole, address)
            self.device_list.addItem(item)
            logging.info(f"Added paired device to list: {name} [{address}]")

    def set_volume(self, value):
        self.label.setText(f'Output Volume: {value}%')
        set_sink_volume_cmd(self.default_sink, value)
        if self.is_muted and value > 0:
            set_sink_mute_cmd(self.default_sink, False)
            self.is_muted = False

    def set_input_volume(self, value):
        self.input_label.setText(f'Input Volume: {value}%')
        set_source_volume_cmd(self.default_source, value)
        if self.is_input_muted and value > 0:
            set_source_mute_cmd(self.default_source, False)
            self.is_input_muted = False

    def change_sink(self, index):
        item_data = self.device_selector.itemData(index)
        if item_data:
            if item_data['type'] == 'sink':
                selected_sink = item_data['data']
                if selected_sink:
                    self.default_sink = selected_sink['name']
                    set_default_sink_cmd(self.default_sink)
                    volume = get_sink_volume_cmd(self.default_sink)
                    self.volume_bar.setVolume(volume)
                    self.label.setText(f'Output Volume: {volume}%')
                    self.is_muted = get_sink_mute_cmd(self.default_sink)
                    
                    # Update the output device label
                    self.output_device_label.setText(f"Output Device: {self.get_device_display_name(self.default_sink)}")
                    
                    logging.info(f"Default sink changed to {selected_sink['description']}")

    def change_source(self, index):
        item_data = self.input_selector.itemData(index)
        if item_data:
            if item_data['type'] == 'source':
                selected_source = item_data['data']
                if selected_source:
                    self.default_source = selected_source['name']
                    set_default_source_cmd(self.default_source)
                    volume = get_source_volume_cmd(self.default_source)
                    self.input_volume_bar.setVolume(volume)
                    self.input_label.setText(f'Input Volume: {volume}%')
                    self.is_input_muted = get_source_mute_cmd(self.default_source)
                    
                    # Update the input device label
                    self.input_device_label.setText(f"Input Device: {self.get_device_display_name(self.default_source)}")
                    
                    logging.info(f"Default source changed to {selected_source['description']}")

    def connect_and_set_bluetooth_device(self, address, is_sink=True):
        logging.info(f"Connecting to Bluetooth device {address} and setting as default {'sink' if is_sink else 'source'}")
        # Attempt to connect the device if not connected
        bus = dbus.SystemBus()
        device_path = None
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                if device_properties.get('Address') == address:
                    device_path = path
                    break
        if device_path:
            device = dbus.Interface(bus.get_object('org.bluez', device_path),
                                    'org.bluez.Device1')
            try:
                props = dbus.Interface(bus.get_object('org.bluez', device_path), 'org.freedesktop.DBus.Properties')
                connected = props.Get('org.bluez.Device1', 'Connected')
            except dbus.DBusException as e:
                QtWidgets.QMessageBox.warning(self, "Bluetooth Error", f"Failed to get connection status: {e}")
                logging.error(f"Failed to get connection status for {address}: {e}")
                return

            if not connected:
                try:
                    device.Connect()
                    logging.info(f"Connected to {address}")
                    # Wait a bit for the connection to be established
                    QtCore.QTimer.singleShot(5000, lambda addr=address: self.set_device_as_default_sink_and_source(addr, is_sink=is_sink))
                except dbus.DBusException as e:
                    QtWidgets.QMessageBox.warning(self, "Bluetooth Connection Failed", f"Failed to connect to {address}: {e}")
                    logging.error(f"Failed to connect to {address}: {e}")
            else:
                self.set_device_as_default_sink_and_source(address, is_sink=is_sink)
        else:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Not Found", f"Device {address} not found on D-Bus")
            logging.warning(f"Device {address} not found on D-Bus")

    def start_scan(self):
        self.device_list.clear()
        self.scan_button.setEnabled(False)
        self.scan_thread = QtCore.QThread()
        self.scan_worker = ScanWorker()
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_worker.devicesFound.connect(self.update_device_list)
        self.scan_worker.scanFinished.connect(self.scan_finished)
        self.scan_thread.started.connect(self.scan_worker.start_scan)
        self.scan_thread.start()

    def update_device_list(self, device):
        for address, name in device.items():
            # Check if the device is already in the list to avoid duplicates
            existing_items = [self.device_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.device_list.count())]
            if address not in existing_items:
                item_text = f"{name} [{address}]"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(QtCore.Qt.UserRole, address)
                self.device_list.addItem(item)
                logging.info(f"Added device to list: {name} [{address}]")

    def scan_finished(self):
        self.scan_button.setEnabled(True)
        self.scan_thread.quit()
        self.scan_thread.wait()
        logging.info("Bluetooth scan finished.")

    def pair_device(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            address = selected_item.data(QtCore.Qt.UserRole)
            self.pair_button.setEnabled(False)
            self.unpair_button.setEnabled(False)
            self.pair_thread = QtCore.QThread()
            self.pair_worker = PairWorker(address)
            self.pair_worker.moveToThread(self.pair_thread)
            self.pair_worker.pairingResult.connect(self.pairing_finished)
            self.pair_thread.started.connect(self.pair_worker.pair)
            self.pair_thread.start()

    def pairing_finished(self, success, message):
        self.pair_button.setEnabled(True)
        self.unpair_button.setEnabled(True)
        if success:
            QtWidgets.QMessageBox.information(self, "Pairing Result", message)
            # Wait longer before setting the profile
            QtCore.QTimer.singleShot(5000, self.set_bluetooth_profile)
        else:
            QtWidgets.QMessageBox.warning(self, "Pairing Failed", message)
        self.pair_thread.quit()
        self.pair_thread.wait()

    def set_bluetooth_profile(self):
        try:
            # Refresh the sinks and sources
            self.sinks = list_sinks()
            self.sources = list_sources()

            pa_address = self.get_recent_bluetooth_address()
            if not pa_address:
                logging.warning("No recent Bluetooth address found.")
                return

            pa_address_clean = pa_address.replace(":", "_").lower()
            card_name = get_card_for_device(pa_address)
            if not card_name:
                logging.error(f"No card found for device {pa_address}")
                QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error",
                                              "Failed to find the audio card for the Bluetooth device.")
                return

            # Set profile to A2DP Sink
            A2DP_PROFILE = 'a2dp_sink'
            set_card_profile(card_name, A2DP_PROFILE)
            logging.info(f"Set card {card_name} to profile {A2DP_PROFILE}")

            # Allow some time for PipeWire to apply the profile
            time.sleep(2)

            # Refresh sinks and sources after setting profile
            self.sinks = list_sinks()
            self.sources = list_sources()

            # Find the sink and source again
            sink_name = None
            source_name = None

            for sink in self.sinks:
                expected_sink_prefix = f'bluez_sink.{pa_address_clean}'
                if sink['name'].startswith(expected_sink_prefix):
                    sink_name = sink['name']
                    logging.info(f"Matched sink: {sink_name}")
                    break

            for source in self.sources:
                expected_source_prefix = f'bluez_source.{pa_address_clean}'
                if source['name'].startswith(expected_source_prefix):
                    source_name = source['name']
                    logging.info(f"Matched source: {source_name}")
                    break

            if sink_name:
                try:
                    set_default_sink_cmd(sink_name)
                    self.default_sink = sink_name
                    volume = get_sink_volume_cmd(sink_name)
                    self.volume_bar.setVolume(volume)
                    self.label.setText(f'Output Volume: {volume}%')
                    self.is_muted = get_sink_mute_cmd(sink_name)
                    logging.info(f"Set default sink to {sink_name}")
                except Exception as e:
                    logging.error(f"Failed to set default sink: {e}")
                    QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default sink: {e}")

            if source_name:
                try:
                    set_default_source_cmd(source_name)
                    self.default_source = source_name
                    volume = get_source_volume_cmd(source_name)
                    self.input_volume_bar.setVolume(volume)
                    self.input_label.setText(f'Input Volume: {volume}%')
                    self.is_input_muted = get_source_mute_cmd(source_name)
                    logging.info(f"Set default source to {source_name}")
                except Exception as e:
                    logging.error(f"Failed to set default source: {e}")
                    QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default source: {e}")

            # Refresh the device lists
            self.refresh_audio_devices()

            # Show a dialog box to inform the user
            if sink_name and source_name:
                QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                                  "The Bluetooth device has been set as the default input and output device.")
            elif sink_name:
                QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                                  "The Bluetooth device has been set as the default output device.")
            elif source_name:
                QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                                  "The Bluetooth device has been set as the default input device.")

            # Additional Wait to ensure PipeWire applies the changes
            QtCore.QTimer.singleShot(3000, self.refresh_all_devices)
        except Exception as e:
            logging.error(f"Failed to set Bluetooth profile: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to set Bluetooth profile: {e}")

    def get_recent_bluetooth_address(self):
        """Retrieve the most recently connected Bluetooth device's address."""
        # Iterate through sinks and sources to find the latest bluez_sink/source
        latest_sink = None
        latest_source = None

        for sink in self.sinks:
            if sink['name'].startswith('bluez_sink.'):
                latest_sink = sink['name']

        for source in self.sources:
            if source['name'].startswith('bluez_source.'):
                latest_source = source['name']

        # Extract address from sink/source name
        address = None
        if latest_sink:
            match = re.match(r'bluez_sink\.([0-9a-f_]{17})', latest_sink)
            if match:
                address = match.group(1).replace('_', ':')
        elif latest_source:
            match = re.match(r'bluez_source\.([0-9a-f_]{17})', latest_source)
            if match:
                address = match.group(1).replace('_', ':')

        logging.debug(f"Recent Bluetooth Address: {address}")
        return address

    def unpair_device(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            address = selected_item.data(QtCore.Qt.UserRole)
            self.pair_button.setEnabled(False)
            self.unpair_button.setEnabled(False)
            self.unpair_thread = QtCore.QThread()
            self.unpair_worker = UnpairWorker(address)
            self.unpair_worker.moveToThread(self.unpair_thread)
            self.unpair_worker.unpairingResult.connect(self.unpairing_finished)
            self.unpair_thread.started.connect(self.unpair_worker.unpair)
            self.unpair_thread.start()

    def unpairing_finished(self, success, message):
        self.pair_button.setEnabled(True)
        self.unpair_button.setEnabled(True)
        if success:
            QtWidgets.QMessageBox.information(self, "Unpairing Result", message)
            # Refresh Bluetooth devices after unpairing
            self.bluetooth_devices_updated.emit()
        else:
            QtWidgets.QMessageBox.warning(self, "Unpairing Failed", message)
        self.unpair_thread.quit()
        self.unpair_thread.wait()

    def refresh_audio_devices(self):
        logging.info("Refreshing audio devices...")
        try:
            self.sinks = list_sinks()
            self.sources = list_sources()
            self.populate_output_devices()
            self.populate_input_devices()

            # Update default sink and source after refreshing
            self.default_sink = get_default_sink()
            self.default_source = get_default_source()
            logging.info(f"Default sink: {self.default_sink}")
            logging.info(f"Default source: {self.default_source}")

            # Update the device name labels
            self.output_device_label.setText(f"Output Device: {self.get_device_display_name(self.default_sink)}")
            self.input_device_label.setText(f"Input Device: {self.get_device_display_name(self.default_source)}")

            # Update the volume bars and labels
            volume = get_sink_volume_cmd(self.default_sink)
            self.volume_bar.setVolume(volume)
            self.label.setText(f'Output Volume: {volume}%')

            input_volume = get_source_volume_cmd(self.default_source)
            self.input_volume_bar.setVolume(input_volume)
            self.input_label.setText(f'Input Volume: {input_volume}%')
        except Exception as e:
            logging.error(f"Failed to refresh audio devices: {e}")
            QtWidgets.QMessageBox.warning(self, "Error",
                                          f"Failed to refresh audio devices: {e}")

    def refresh_bluetooth_devices(self):
        logging.info("Refreshing Bluetooth devices...")
        self.populate_bluetooth_devices()

    def refresh_all_devices(self):
        self.refresh_audio_devices()
        self.refresh_bluetooth_devices()

    @QtCore.pyqtSlot()
    def emit_devices_updated(self):
        self.devices_updated.emit()

    @QtCore.pyqtSlot()
    def emit_bluetooth_devices_updated(self):
        self.bluetooth_devices_updated.emit()

    def start_pulse_event_listener(self):
        logging.info("Starting PulseAudio (PipeWire) event listener...")
        # Start a separate thread to poll for changes
        self.polling_thread = threading.Thread(target=self.poll_audio_events, daemon=True)
        self.polling_thread.start()

    def poll_audio_events(self):
        """Poll for audio device changes periodically."""
        previous_sinks = list_sinks()
        previous_sources = list_sources()
        poll_interval = 2  # Adjust as needed (seconds)
        while True:
            time.sleep(poll_interval)
            current_sinks = list_sinks()
            current_sources = list_sources()
            if current_sinks != previous_sinks or current_sources != previous_sources:
                logging.info("Audio devices changed detected.")
                previous_sinks = current_sinks
                previous_sources = current_sources
                QtCore.QMetaObject.invokeMethod(self, 'emit_devices_updated', QtCore.Qt.QueuedConnection)
                QtCore.QMetaObject.invokeMethod(self, 'emit_bluetooth_devices_updated', QtCore.Qt.QueuedConnection)

    def connect_paired_bluetooth_devices(self):
        """Automatically connect to all already paired Bluetooth devices."""
        logging.info("Connecting to all already paired Bluetooth devices...")
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                address = device_properties.get('Address', '')
                name = device_properties.get('Name', address)
                paired = device_properties.get('Paired', False)
                connected = device_properties.get('Connected', False)
                if paired and not connected:
                    logging.info(f"Attempting to connect to paired device: {name} [{address}]")
                    try:
                        device = dbus.Interface(bus.get_object('org.bluez', path),
                                                'org.bluez.Device1')
                        device.Connect()
                        logging.info(f"Connected to {name} [{address}]")
                        # Wait longer to allow PipeWire to recognize the connection
                        QtCore.QTimer.singleShot(5000, lambda addr=address: self.set_device_as_default_sink_and_source(addr, is_sink=True))
                    except dbus.DBusException as e:
                        logging.error(f"Failed to connect to {name} [{address}]: {e}")
        # After attempting connections, refresh device lists after delay
        QtCore.QTimer.singleShot(6000, self.refresh_all_devices)

    def start_dbus_signal_listener(self):
        """Start listening to D-Bus signals for device property changes."""
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            self.device_property_changed,
            dbus_interface='org.freedesktop.DBus.Properties',
            signal_name='PropertiesChanged',
            arg0='org.bluez.Device1',
            path_keyword='path'
        )
        logging.info("Started listening for D-Bus signals.")

    def device_property_changed(self, interface, changed, invalidated, path):
        """Handle D-Bus signals for device property changes."""
        if 'Connected' in changed:
            logging.info(f"Device {path} property 'Connected' changed to {changed['Connected']}")
            # Delay refresh to ensure devices are properly recognized
            QtCore.QTimer.singleShot(3000, self.refresh_all_devices)

    def set_bluetooth_device_as_default(self, item):
        """Set the double-clicked Bluetooth device as default sink and source."""
        address = item.data(QtCore.Qt.UserRole)
        logging.info(f"Double-clicked on device: {address}")
        self.connect_and_set_bluetooth_device(address)

    def set_device_as_default_sink_and_source(self, address, is_sink=True):
        """Set the Bluetooth device as the default sink and/or source."""
        pa_address = address.replace(":", "_").lower()
        card_name = get_card_for_device(address)
        if not card_name:
            logging.error(f"No card found for device {address}")
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error",
                                          "Failed to find the audio card for the Bluetooth device.")
            return

        # Set profile to A2DP Sink
        A2DP_PROFILE = 'a2dp_sink'
        set_card_profile(card_name, A2DP_PROFILE)
        logging.info(f"Set card {card_name} to profile {A2DP_PROFILE}")

        # Allow some time for PipeWire to apply the profile
        time.sleep(2)

        # Refresh sinks and sources after setting profile
        self.sinks = list_sinks()
        self.sources = list_sources()

        # Find the sink and source again
        sink_name = None
        source_name = None

        for sink in self.sinks:
            expected_sink_prefix = f'bluez_sink.{pa_address}'
            if sink['name'].startswith(expected_sink_prefix):
                sink_name = sink['name']
                logging.info(f"Matched sink: {sink_name}")
                break

        for source in self.sources:
            expected_source_prefix = f'bluez_source.{pa_address}'
            if source['name'].startswith(expected_source_prefix):
                source_name = source['name']
                logging.info(f"Matched source: {source_name}")
                break

        if sink_name:
            try:
                set_default_sink_cmd(sink_name)
                self.default_sink = sink_name
                volume = get_sink_volume_cmd(sink_name)
                self.volume_bar.setVolume(volume)
                self.label.setText(f'Output Volume: {volume}%')
                self.is_muted = get_sink_mute_cmd(sink_name)
                logging.info(f"Set default sink to {sink_name}")
            except Exception as e:
                logging.error(f"Failed to set default sink: {e}")
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default sink: {e}")

        if source_name:
            try:
                set_default_source_cmd(source_name)
                self.default_source = source_name
                volume = get_source_volume_cmd(source_name)
                self.input_volume_bar.setVolume(volume)
                self.input_label.setText(f'Input Volume: {volume}%')
                self.is_input_muted = get_source_mute_cmd(source_name)
                logging.info(f"Set default source to {source_name}")
            except Exception as e:
                logging.error(f"Failed to set default source: {e}")
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default source: {e}")

        # Refresh the device lists
        self.refresh_audio_devices()

        # Show a dialog box to inform the user
        if sink_name and source_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default input and output device.")
        elif sink_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default output device.")
        elif source_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default input device.")

        # Additional Wait to ensure PipeWire applies the changes
        QtCore.QTimer.singleShot(3000, self.refresh_all_devices)

# ------------------------ Worker Classes ------------------------

class ScanWorker(QtCore.QObject):
    devicesFound = QtCore.pyqtSignal(dict)
    scanFinished = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.devices = {}

    @QtCore.pyqtSlot()
    def start_scan(self):
        # Get system bus
        bus = dbus.SystemBus()

        # Get the bluez adapter
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        adapter_path = None
        for path, interfaces in objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                adapter_path = path
                break

        if adapter_path is None:
            logging.error("Bluetooth adapter not found")
            self.scanFinished.emit()
            return

        adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path),
                                 'org.bluez.Adapter1')

        # Start discovery
        try:
            adapter.StartDiscovery()
            logging.info("Started Bluetooth discovery...")
        except dbus.DBusException as e:
            logging.error(f"Failed to start discovery: {e}")
            self.scanFinished.emit()
            return

        # Wait for devices to be discovered
        time.sleep(10)  # Increased scan duration for better discovery

        # Stop discovery
        try:
            adapter.StopDiscovery()
            logging.info("Stopped Bluetooth discovery.")
        except dbus.DBusException as e:
            logging.error(f"Failed to stop discovery: {e}")

        # Get the list of devices
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                address = device_properties.get('Address', '')
                name = device_properties.get('Name', address)
                if address not in self.devices:
                    self.devices[address] = name
                    logging.info(f"Found device: {name} [{address}]")
                    self.devicesFound.emit({address: name})

        self.scanFinished.emit()

class PairWorker(QtCore.QObject):
    pairingResult = QtCore.pyqtSignal(bool, str)

    def __init__(self, device_address):
        super().__init__()
        self.device_address = device_address

    @QtCore.pyqtSlot()
    def pair(self):
        bus = dbus.SystemBus()
        # Get device path
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        device_path = None
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                if device_properties.get('Address') == self.device_address:
                    device_path = path
                    break

        if device_path is None:
            self.pairingResult.emit(False, "Device not found")
            return

        device = dbus.Interface(bus.get_object('org.bluez', device_path),
                                'org.bluez.Device1')

        # Set trusted
        props = dbus.Interface(bus.get_object('org.bluez', device_path),
                               'org.freedesktop.DBus.Properties')
        try:
            props.Set('org.bluez.Device1', 'Trusted', True)
            logging.info("Set device as trusted.")
        except dbus.DBusException as e:
            logging.error(f"Failed to set device as trusted: {e}")

        # Pair and connect
        try:
            device.Pair()
            logging.info("Pairing initiated...")
            # Wait for pairing to complete
            time.sleep(5)
            device.Connect()
            logging.info("Connected to device.")
            self.pairingResult.emit(True, "Pairing and connection successful")
        except dbus.DBusException as e:
            error_name = e.get_dbus_name()
            logging.error(f"Pairing error: {error_name}")
            if error_name == 'org.bluez.Error.AlreadyExists':
                try:
                    device.Connect()
                    logging.info("Device is already paired and connected.")
                    self.pairingResult.emit(True, "Device is already paired and connected")
                except dbus.DBusException as conn_e:
                    self.pairingResult.emit(False, f"Already paired, but failed to connect: {conn_e}")
            else:
                self.pairingResult.emit(False, str(e))

class UnpairWorker(QtCore.QObject):
    unpairingResult = QtCore.pyqtSignal(bool, str)

    def __init__(self, device_address):
        super().__init__()
        self.device_address = device_address

    @QtCore.pyqtSlot()
    def unpair(self):
        bus = dbus.SystemBus()
        # Get device path
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        adapter_path = None
        device_path = None
        for path, interfaces in objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                adapter_path = path
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                if device_properties.get('Address') == self.device_address:
                    device_path = path
                    break

        if device_path is None or adapter_path is None:
            self.unpairingResult.emit(False, "Device not found")
            return

        adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path),
                                 'org.bluez.Adapter1')

        try:
            adapter.RemoveDevice(device_path)
            logging.info("Unpaired device successfully.")
            self.unpairingResult.emit(True, "Unpairing successful")
        except dbus.DBusException as e:
            logging.error(f"Failed to unpair device: {e}")
            self.unpairingResult.emit(False, str(e))

# ------------------------ D-Bus Agent ------------------------

class Agent(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self):
        logging.info("Agent: Release called.")

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        logging.info(f"Agent: AuthorizeService called for device {device} and UUID {uuid}.")

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device):
        logging.info(f"Agent: RequestPinCode called for device {device}.")
        return '0000'

    @dbus.service.method('org.bluez.Agent1', in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered):
        logging.info(f"Agent: DisplayPasskey called for device {device} with passkey {passkey} entered {entered} times.")

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode):
        logging.info(f"Agent: DisplayPinCode called for device {device} with pincode {pincode}.")

    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        logging.info(f"Agent: RequestConfirmation called for device {device} with passkey {passkey}.")

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        logging.info(f"Agent: RequestAuthorization called for device {device}.")

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        logging.info("Agent: Cancel called.")

# ------------------------ Main Function ------------------------

def main():
    # Initialize the D-Bus main loop
    DBusGMainLoop(set_as_default=True)
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Start the GLib main loop in a separate thread
    gobject_loop = GLib.MainLoop()
    gobject_thread = threading.Thread(target=gobject_loop.run, daemon=True)
    gobject_thread.start()
    logging.info("GLib main loop started.")

    # Create and register the agent
    bus = dbus.SystemBus()
    agent_path = "/test/agent"
    capability = "NoInputNoOutput"
    agent = Agent(bus, agent_path)
    agent_manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                                   "org.bluez.AgentManager1")
    try:
        agent_manager.RegisterAgent(agent_path, capability)
        logging.info("Agent registered.")
    except dbus.DBusException as e:
        if e.get_dbus_name() == 'org.bluez.Error.AlreadyExists':
            logging.warning("Agent already registered.")
        else:
            logging.error(f"Failed to register agent: {e}")
            raise e
    try:
        agent_manager.RequestDefaultAgent(agent_path)
        logging.info("Agent set as default.")
    except dbus.DBusException as e:
        if e.get_dbus_name() == 'org.bluez.Error.AlreadyExists':
            logging.warning("Agent is already the default agent.")
        else:
            logging.error(f"Failed to set default agent: {e}")
            raise e

    controller = VolumeController()
    controller.show()

    ret = app.exec_()

    # Unregister the agent when the application exits
    try:
        agent_manager.UnregisterAgent(agent_path)
        logging.info("Agent unregistered.")
    except dbus.DBusException as e:
        logging.error(f"Failed to unregister agent: {e}")

    # Quit the GLib main loop
    gobject_loop.quit()
    logging.info("GLib main loop stopped.")
    sys.exit(ret)

if __name__ == '__main__':
    main()
