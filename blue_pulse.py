import sys
import re
import logging
import threading
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QSettings, QTimer, QProcess
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

sys.dont_write_bytecode = True

# ------------------------ Logging Configuration ------------------------
logging.disable(logging.CRITICAL)
# Uncomment for debugging:
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ------------------------ Helper Functions ------------------------

def run_pactl_command(command):
    """Run a pactl command using QProcess and return its output."""
    process = QProcess()
    process.start("pactl", command)
    if process.waitForFinished(3000):  # 3-second timeout
        output = process.readAllStandardOutput().data().decode("utf-8")
        return output
    else:
        logging.error("pactl command timed out: " + " ".join(command))
        return ""

def get_default_sink():
    output = run_pactl_command(['get-default-sink'])
    default_sink = output.strip()
    if default_sink.lower() == 'pipewire':
        sinks = list_sinks()
        if sinks:
            default_sink = sinks[0]['name']
    return default_sink

def get_default_source():
    output = run_pactl_command(['get-default-source'])
    default_source = output.strip()
    if default_source.lower() == 'pipewire':
        sources = list_sources()
        if sources:
            default_source = sources[0]['name']
    return default_source

def list_sinks():
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
    return sinks

def list_sources():
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
    return sources

def set_default_sink_cmd(sink_name):
    run_pactl_command(['set-default-sink', sink_name])

def set_default_source_cmd(source_name):
    run_pactl_command(['set-default-source', source_name])

def set_sink_volume_cmd(sink_name, volume):
    run_pactl_command(['set-sink-volume', sink_name, f"{volume}%"])

def set_source_volume_cmd(source_name, volume):
    run_pactl_command(['set-source-volume', source_name, f"{volume}%"])

def get_sink_volume_cmd(sink_name):
    output = run_pactl_command(['get-sink-volume', sink_name])
    match = re.search(r'front-left:.*?(\d+)%', output)
    return int(match.group(1)) if match else 0

def get_source_volume_cmd(source_name):
    output = run_pactl_command(['get-source-volume', source_name])
    match = re.search(r'front-left:.*?(\d+)%', output)
    return int(match.group(1)) if match else 0

def get_sink_mute_cmd(sink_name):
    output = run_pactl_command(['get-sink-mute', sink_name])
    return 'yes' in output.lower()

def get_source_mute_cmd(source_name):
    output = run_pactl_command(['get-source-mute', source_name])
    return 'yes' in output.lower()

def set_sink_mute_cmd(sink_name, mute):
    run_pactl_command(['set-sink-mute', sink_name, '1' if mute else '0'])

def set_source_mute_cmd(source_name, mute):
    run_pactl_command(['set-source-mute', source_name, '1' if mute else '0'])

def get_card_for_device(address):
    output = run_pactl_command(['list', 'cards'])
    card_name = None
    current_card = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Card #'):
            current_card = line.split('#')[1].rstrip(':')
        elif line.startswith('Name:') and current_card:
            name = line.split(':', 1)[1].strip()
            expected_prefix = f'bluez_card.{address.replace(":", "_").lower()}'
            if name.startswith(expected_prefix):
                card_name = name
                break
    return card_name

def set_card_profile(card_name, profile):
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
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
            else:
                painter.setBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50)))
                painter.setPen(QtGui.QPen(QtGui.QColor(50, 50, 50), 1))
            painter.drawRoundedRect(int(x), 0, int(bar_width), rect.height(), 3, 3)

class VolumeController(QtWidgets.QWidget):
    devices_updated = QtCore.pyqtSignal()
    bluetooth_devices_updated = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        # Flag to indicate if a scan is active
        self.scanningActive = False
        # Dictionary to store scan results so they persist
        self.scanned_devices = {}

        self.settings = QSettings("MyCompany", "BluePulse")
        self.sinks = list_sinks()
        self.sources = list_sources()
        self.default_sink = get_default_sink()
        self.default_source = get_default_source()
        self.is_muted = get_sink_mute_cmd(self.default_sink)
        self.is_input_muted = get_source_mute_cmd(self.default_source)
        self.devices_updated.connect(self.refresh_audio_devices)
        self.bluetooth_devices_updated.connect(self.refresh_bluetooth_devices)
        # Increase polling interval to 10 seconds
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(10000)
        self.poll_timer.timeout.connect(self.refresh_all_devices)
        self.poll_timer.start()
        self.init_ui()
        self.populate_bluetooth_devices()
        self.connect_paired_bluetooth_devices()
        self.start_dbus_signal_listener()
        last_bt_device = self.settings.value("last_bluetooth", "")
        if last_bt_device:
            logging.info(f"Reconnecting to last paired Bluetooth device: {last_bt_device}")
            QTimer.singleShot(1000, lambda: self.connect_and_set_bluetooth_device(last_bt_device))
    
    def init_ui(self):
        self.setWindowTitle('Blue Pulse')
        self.resize(800, 500)
        self.setStyleSheet("""
            QWidget { background-color: #000000; border: 1px solid rgba(255, 255, 255, 0.3);
                     border-radius: 12px; color: #FFFFFF; font-family: 'Segoe UI', Arial, sans-serif;
                     font-size: 14px; }
            QLabel { background: none; font-weight: bold; color: #FFFFFF; text-align: center; }
            QLabel#titleLabel { font-size: 20px; margin-bottom: 10px; }
            QLabel#volumeLabel, QLabel#deviceLabel { font-size: 14px; border: 1px solid rgba(255, 255, 255, 0.5);
                     border-radius: 6px; padding: 4px 10px; background: rgba(255, 255, 255, 0.05);
                     min-width: 120px; margin: 5px auto; }
            QComboBox { background: #333333; border: 1px solid #FFFFFF; padding: 5px; border-radius: 8px; }
            QPushButton { background-color: #444444; border: none; color: #FFFFFF; padding: 8px 16px;
                     border-radius: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #555555; }
            QListWidget { background-color: #333333; border: 1px solid #FFFFFF; padding: 5px; border-radius: 8px; }
        """)
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        left_layout = QtWidgets.QVBoxLayout()
        self.title_label = QtWidgets.QLabel("Volume Controller")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.output_device_label = QtWidgets.QLabel(f"Output Device: {self.get_device_display_name(self.default_sink)}")
        self.output_device_label.setObjectName("deviceLabel")
        self.output_device_label.setAlignment(QtCore.Qt.AlignCenter)
        self.device_selector = QtWidgets.QComboBox()
        self.populate_output_devices()
        self.device_selector.currentIndexChanged.connect(self.change_sink)
        self.label = QtWidgets.QLabel(f'Output Volume: {get_sink_volume_cmd(self.default_sink)}%')
        self.label.setObjectName("volumeLabel")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.volume_bar = VolumeBar(self)
        self.volume_bar.setFixedHeight(60)
        self.volume_bar.setVolume(get_sink_volume_cmd(self.default_sink))
        self.volume_bar.volumeChanged.connect(self.set_volume)
        
        self.input_device_label = QtWidgets.QLabel(f"Input Device: {self.get_device_display_name(self.default_source)}")
        self.input_device_label.setObjectName("deviceLabel")
        self.input_device_label.setAlignment(QtCore.Qt.AlignCenter)
        self.input_selector = QtWidgets.QComboBox()
        self.populate_input_devices()
        self.input_selector.currentIndexChanged.connect(self.change_source)
        self.input_label = QtWidgets.QLabel(f'Input Volume: {get_source_volume_cmd(self.default_source)}%')
        self.input_label.setObjectName("volumeLabel")
        self.input_label.setAlignment(QtCore.Qt.AlignCenter)
        self.input_volume_bar = VolumeBar(self)
        self.input_volume_bar.setFixedHeight(60)
        self.input_volume_bar.setVolume(get_source_volume_cmd(self.default_source))
        self.input_volume_bar.volumeChanged.connect(self.set_input_volume)
        
        left_layout.addWidget(self.title_label)
        left_layout.addWidget(self.output_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Output Device:"))
        left_layout.addWidget(self.device_selector)
        left_layout.addWidget(self.label)
        left_layout.addWidget(self.volume_bar)
        left_layout.addWidget(self.input_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Input Device:"))
        left_layout.addWidget(self.input_selector)
        left_layout.addWidget(self.input_label)
        left_layout.addWidget(self.input_volume_bar)
        left_layout.addStretch()
        
        right_layout = QtWidgets.QVBoxLayout()
        self.bluetooth_label = QtWidgets.QLabel("Bluetooth Devices:")
        self.bluetooth_label.setAlignment(QtCore.Qt.AlignCenter)
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.pair_button = QtWidgets.QPushButton("Pair")
        self.unpair_button = QtWidgets.QPushButton("Unpair")
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.device_list = QtWidgets.QListWidget()
        self.device_list.setFixedWidth(300)
        self.scan_button.clicked.connect(self.start_scan)
        self.pair_button.clicked.connect(self.pair_device)
        self.unpair_button.clicked.connect(self.unpair_device)
        self.refresh_button.clicked.connect(self.refresh_all_devices)
        self.device_list.itemDoubleClicked.connect(self.set_bluetooth_device_as_default)
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.pair_button)
        buttons_layout.addWidget(self.unpair_button)
        buttons_layout.addWidget(self.refresh_button)
        right_layout.addWidget(self.bluetooth_label)
        right_layout.addWidget(self.scan_button)
        right_layout.addWidget(self.device_list)
        right_layout.addLayout(buttons_layout)
        right_layout.addStretch()
        
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.center_window()

    def center_window(self):
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def get_device_display_name(self, device_name):
        for sink in self.sinks:
            if sink['name'] == device_name:
                return sink['description']
        for source in self.sources:
            if source['name'] == device_name:
                return source['description']
        return device_name

    def populate_output_devices(self):
        self.device_selector.blockSignals(True)
        self.device_selector.clear()
        self.sinks = list_sinks()
        for sink in self.sinks:
            self.device_selector.addItem(sink['description'], {'type': 'sink', 'data': sink})
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
        for source in self.sources:
            self.input_selector.addItem(source['description'], {'type': 'source', 'data': source})
        default_source_name = self.default_source
        for index in range(self.input_selector.count()):
            item_data = self.input_selector.itemData(index)
            if item_data['type'] == 'source' and item_data['data']['name'] == default_source_name:
                self.input_selector.setCurrentIndex(index)
                break
        self.input_selector.blockSignals(False)

    def get_paired_bluetooth_devices(self):
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
        return devices

    def populate_bluetooth_devices(self):
        # Merge scanned devices with paired devices so scan results persist.
        if not self.scanningActive:
            paired_devices = self.get_paired_bluetooth_devices()
            merged = {}
            merged.update(self.scanned_devices)
            merged.update(paired_devices)
            self.device_list.clear()
            for address, name in merged.items():
                item_text = f"{name} [{address}]"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(QtCore.Qt.UserRole, address)
                self.device_list.addItem(item)

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
        if item_data and item_data['type'] == 'sink':
            selected_sink = item_data['data']
            self.default_sink = selected_sink['name']
            set_default_sink_cmd(self.default_sink)
            volume = get_sink_volume_cmd(self.default_sink)
            self.volume_bar.setVolume(volume)
            self.label.setText(f'Output Volume: {volume}%')
            self.is_muted = get_sink_mute_cmd(self.default_sink)
            self.output_device_label.setText(f"Output Device: {self.get_device_display_name(self.default_sink)}")

    def change_source(self, index):
        item_data = self.input_selector.itemData(index)
        if item_data and item_data['type'] == 'source':
            selected_source = item_data['data']
            self.default_source = selected_source['name']
            set_default_source_cmd(self.default_source)
            volume = get_source_volume_cmd(self.default_source)
            self.input_volume_bar.setVolume(volume)
            self.input_label.setText(f'Input Volume: {volume}%')
            self.is_input_muted = get_source_mute_cmd(self.default_source)
            self.input_device_label.setText(f"Input Device: {self.get_device_display_name(self.default_source)}")

    # ------------------ Bluetooth Methods ------------------

    def start_scan(self):
        self.scanningActive = True
        self.scanned_devices.clear()  # Clear previous scan results
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
            self.scanned_devices[address] = name
            existing = [self.device_list.item(i).data(QtCore.Qt.UserRole)
                        for i in range(self.device_list.count())]
            if address not in existing:
                item_text = f"{name} [{address}]"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(QtCore.Qt.UserRole, address)
                self.device_list.addItem(item)

    def scan_finished(self):
        self.scan_button.setEnabled(True)
        self.scan_thread.quit()
        self.scan_thread.wait()
        self.scanningActive = False

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
            QTimer.singleShot(3000, self.set_bluetooth_profile)
        else:
            QtWidgets.QMessageBox.warning(self, "Pairing Failed", message)
        self.pair_thread.quit()
        self.pair_thread.wait()

    def set_bluetooth_profile(self):
        self.sinks = list_sinks()
        self.sources = list_sources()
        pa_address = self.get_recent_bluetooth_address()
        if not pa_address:
            logging.warning("No recent Bluetooth address found.")
            return
        pa_address_clean = pa_address.replace(":", "_").lower()
        card_name = get_card_for_device(pa_address)
        if not card_name:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error",
                                          "Failed to find the audio card for the Bluetooth device.")
            return
        A2DP_PROFILE = 'a2dp_sink'
        set_card_profile(card_name, A2DP_PROFILE)
        QTimer.singleShot(1500, lambda: self.refresh_after_profile_set(pa_address_clean))

    def get_recent_bluetooth_address(self):
        latest_sink = None
        latest_source = None
        for sink in self.sinks:
            if sink['name'].startswith('bluez_sink.'):
                latest_sink = sink['name']
        for source in self.sources:
            if source['name'].startswith('bluez_source.'):
                latest_source = source['name']
        address = None
        if latest_sink:
            match = re.match(r'bluez_sink\.([0-9a-f_]{17})', latest_sink)
            if match:
                address = match.group(1).replace('_', ':')
        elif latest_source:
            match = re.match(r'bluez_source\.([0-9a-f_]{17})', latest_source)
            if match:
                address = match.group(1).replace('_', ':')
        return address

    def connect_and_set_bluetooth_device(self, address, is_sink=True):
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        device_path = None
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
                props = dbus.Interface(bus.get_object('org.bluez', device_path),
                                       'org.freedesktop.DBus.Properties')
                connected = props.Get('org.bluez.Device1', 'Connected')
            except dbus.DBusException as e:
                QtWidgets.QMessageBox.warning(self, "Bluetooth Error",
                                              f"Failed to get connection status: {e}")
                return
            if not connected:
                try:
                    device.Connect()
                    QTimer.singleShot(3000, lambda addr=address: self.set_device_as_default_sink_and_source(addr, is_sink=is_sink))
                except dbus.DBusException as e:
                    QtWidgets.QMessageBox.warning(self, "Bluetooth Connection Failed",
                                                  f"Failed to connect to {address}: {e}")
            else:
                self.set_device_as_default_sink_and_source(address, is_sink=is_sink)
        else:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Not Found",
                                          f"Device {address} not found on D-Bus")

    def set_device_as_default_sink_and_source(self, address, is_sink=True):
        self.settings.setValue("last_bluetooth", address)
        pa_address = address.replace(":", "_").lower()
        card_name = get_card_for_device(address)
        if not card_name:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error",
                                          "Failed to find the audio card for the Bluetooth device.")
            return
        A2DP_PROFILE = 'a2dp_sink'
        set_card_profile(card_name, A2DP_PROFILE)
        QTimer.singleShot(1500, lambda: self.refresh_after_profile_set(pa_address))

    def refresh_after_profile_set(self, pa_address):
        self.sinks = list_sinks()
        self.sources = list_sources()
        sink_name = None
        source_name = None
        for sink in self.sinks:
            expected_sink_prefix = f'bluez_sink.{pa_address}'
            if sink['name'].startswith(expected_sink_prefix):
                sink_name = sink['name']
                break
        for source in self.sources:
            expected_source_prefix = f'bluez_source.{pa_address}'
            if source['name'].startswith(expected_source_prefix):
                source_name = source['name']
                break
        if sink_name:
            try:
                set_default_sink_cmd(sink_name)
                self.default_sink = sink_name
                volume = get_sink_volume_cmd(sink_name)
                self.volume_bar.setVolume(volume)
                self.label.setText(f'Output Volume: {volume}%')
                self.is_muted = get_sink_mute_cmd(sink_name)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default sink: {e}")
        if source_name:
            try:
                set_default_source_cmd(source_name)
                self.default_source = source_name
                volume = get_source_volume_cmd(source_name)
                self.input_volume_bar.setVolume(volume)
                self.input_label.setText(f'Input Volume: {volume}%')
                self.is_input_muted = get_source_mute_cmd(source_name)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default source: {e}")
        self.refresh_audio_devices()
        if sink_name and source_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default input and output device.")
        elif sink_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default output device.")
        elif source_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "The Bluetooth device has been set as the default input device.")
        QTimer.singleShot(3000, self.refresh_all_devices)

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
            self.bluetooth_devices_updated.emit()
        else:
            QtWidgets.QMessageBox.warning(self, "Unpairing Failed", message)
        self.unpair_thread.quit()
        self.unpair_thread.wait()

    def refresh_audio_devices(self):
        try:
            self.sinks = list_sinks()
            self.sources = list_sources()
            self.populate_output_devices()
            self.populate_input_devices()
            self.default_sink = get_default_sink()
            self.default_source = get_default_source()
            self.output_device_label.setText(f"Output Device: {self.get_device_display_name(self.default_sink)}")
            self.input_device_label.setText(f"Input Device: {self.get_device_display_name(self.default_source)}")
            volume = get_sink_volume_cmd(self.default_sink)
            self.volume_bar.setVolume(volume)
            self.label.setText(f'Output Volume: {volume}%')
            input_volume = get_source_volume_cmd(self.default_source)
            self.input_volume_bar.setVolume(input_volume)
            self.input_label.setText(f'Input Volume: {input_volume}%')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to refresh audio devices: {e}")

    def refresh_bluetooth_devices(self):
        if not self.scanningActive:
            self.populate_bluetooth_devices()

    def refresh_all_devices(self):
        self.refresh_audio_devices()
        if not self.scanningActive:
            self.refresh_bluetooth_devices()

    @QtCore.pyqtSlot()
    def emit_devices_updated(self):
        self.devices_updated.emit()

    @QtCore.pyqtSlot()
    def emit_bluetooth_devices_updated(self):
        self.bluetooth_devices_updated.emit()

    def start_dbus_signal_listener(self):
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            self.device_property_changed,
            dbus_interface='org.freedesktop.DBus.Properties',
            signal_name='PropertiesChanged',
            arg0='org.bluez.Device1',
            path_keyword='path'
        )

    def device_property_changed(self, interface, changed, invalidated, path):
        if 'Connected' in changed:
            QTimer.singleShot(3000, self.refresh_all_devices)

    def set_bluetooth_device_as_default(self, item):
        address = item.data(QtCore.Qt.UserRole)
        self.connect_and_set_bluetooth_device(address)

    # --- Added method: connect_paired_bluetooth_devices ---
    def connect_paired_bluetooth_devices(self):
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
                    try:
                        device = dbus.Interface(bus.get_object('org.bluez', path),
                                                'org.bluez.Device1')
                        device.Connect()
                        QTimer.singleShot(5000, lambda addr=address: self.set_device_as_default_sink_and_source(addr, is_sink=True))
                    except dbus.DBusException as e:
                        logging.error(f"Failed to connect to {name} [{address}]: {e}")
        QTimer.singleShot(6000, self.refresh_all_devices)

class ScanWorker(QtCore.QObject):
    devicesFound = QtCore.pyqtSignal(dict)
    scanFinished = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.devices = {}
    @QtCore.pyqtSlot()
    def start_scan(self):
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                                 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()
        adapter_path = None
        for path, interfaces in objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                adapter_path = path
                break
        if adapter_path is None:
            self.scanFinished.emit()
            return
        adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path),
                                 'org.bluez.Adapter1')
        try:
            adapter.StartDiscovery()
        except dbus.DBusException as e:
            self.scanFinished.emit()
            return
        QtCore.QThread.sleep(10)
        try:
            adapter.StopDiscovery()
        except dbus.DBusException as e:
            logging.error(f"Failed to stop discovery: {e}")
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Device1' in interfaces:
                device_properties = interfaces['org.bluez.Device1']
                address = device_properties.get('Address', '')
                name = device_properties.get('Name', address)
                if address not in self.devices:
                    self.devices[address] = name
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
        props = dbus.Interface(bus.get_object('org.bluez', device_path),
                               'org.freedesktop.DBus.Properties')
        try:
            props.Set('org.bluez.Device1', 'Trusted', True)
        except dbus.DBusException as e:
            logging.error(f"Failed to set device as trusted: {e}")
        try:
            device.Pair()
            QtCore.QThread.sleep(2)
            device.Connect()
            self.pairingResult.emit(True, "Pairing and connection successful")
        except dbus.DBusException as e:
            if e.get_dbus_name() == 'org.bluez.Error.AlreadyExists':
                try:
                    device.Connect()
                    self.pairingResult.emit(True, "Device already paired and connected")
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
            self.unpairingResult.emit(True, "Unpairing successful")
        except dbus.DBusException as e:
            self.unpairingResult.emit(False, str(e))

class Agent(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self):
        logging.info("Agent: Release called.")
    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        logging.info(f"Agent: AuthorizeService called for device {device} and UUID {uuid}. Auto-authorizing.")
    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device):
        logging.info(f"Agent: RequestPinCode called for device {device}. Returning PIN '0000'.")
        return "0000"
    @dbus.service.method('org.bluez.Agent1', in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered):
        logging.info(f"Agent: DisplayPasskey called for device {device} with passkey {passkey} entered {entered} times.")
    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode):
        logging.info(f"Agent: DisplayPinCode called for device {device} with pincode {pincode}.")
    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        logging.info(f"Agent: RequestConfirmation called for device {device} with passkey {passkey}. Auto-confirming.")
        return
    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        logging.info(f"Agent: RequestAuthorization called for device {device}. Auto-authorizing.")
        return
    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        logging.info("Agent: Cancel called.")

def main():
    DBusGMainLoop(set_as_default=True)
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    gobject_loop = GLib.MainLoop()
    gobject_thread = threading.Thread(target=gobject_loop.run, daemon=True)
    gobject_thread.start()
    bus = dbus.SystemBus()
    agent_path = "/test/agent"
    capability = "NoInputNoOutput"
    agent = Agent(bus, agent_path)
    agent_manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                                   "org.bluez.AgentManager1")
    try:
        agent_manager.RegisterAgent(agent_path, capability)
    except dbus.DBusException as e:
        if e.get_dbus_name() != 'org.bluez.Error.AlreadyExists':
            raise e
    try:
        agent_manager.RequestDefaultAgent(agent_path)
    except dbus.DBusException as e:
        if e.get_dbus_name() != 'org.bluez.Error.AlreadyExists':
            raise e
    controller = VolumeController()
    controller.show()
    ret = app.exec_()
    try:
        agent_manager.UnregisterAgent(agent_path)
    except dbus.DBusException as e:
        logging.error(f"Failed to unregister agent: {e}")
    gobject_loop.quit()
    sys.exit(ret)

if __name__ == '__main__':
    main()
