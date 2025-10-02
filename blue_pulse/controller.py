# -*- coding: utf-8 -*-
import re, sys
import logging
import dbus
sys.dont_write_bytecode = True
from .qt_compat import (
    QtCore, QtWidgets, QSettings, QTimer, pyqtSignal, pyqtSlot,
    qt_align_center, qt_user_role, available_geometry
)
from .ui.volume_bar import VolumeBar
from .audio_pactl import (
    get_audio_snapshot,
    set_default_sink_cmd, set_default_source_cmd,
    set_sink_volume_cmd,  set_source_volume_cmd,
    set_sink_mute_cmd,    set_source_mute_cmd,
    get_card_for_device,  set_card_profile
)
from .workers import ScanWorker, PairWorker, UnpairWorker
from .defaults_profiles import ProfilesWindow    

logging.disable(logging.CRITICAL)

class VolumeController(QtWidgets.QWidget):
    devices_updated = pyqtSignal()
    bluetooth_devices_updated = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Persistent / runtime state
        self.settings = QSettings("MyCompany", "BluePulse")

        # place-holders until snapshot loads
        self.sinks = []
        self.sources = []
        self.default_sink = ""
        self.default_source = ""
        self.is_muted = False
        self.is_input_muted = False

        # Scan state
        self.scanningActive = False
        self.scanned_devices = {}

        # Timer: periodic refresh (lightweight now)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(10000)  # 10s
        self.poll_timer.timeout.connect(self.refresh_all_devices)
        self.poll_timer.start()

        # Signals
        self.devices_updated.connect(self.refresh_audio_devices)
        self.bluetooth_devices_updated.connect(self.refresh_bluetooth_devices)

        # Build UI (fast)
        self.init_ui()

        # Defer heavy work until after first paint
        QTimer.singleShot(0, self._bootstrap_after_show)

    # -------- deferred startup --------
    def _bootstrap_after_show(self):
        snap = get_audio_snapshot()
        self._apply_snapshot(snap)
        self.start_dbus_signal_listener()
        self.populate_bluetooth_devices()
        last_bt = self.settings.value("last_bluetooth", "")
        if last_bt:
            QTimer.singleShot(1500, lambda: self.connect_and_set_bluetooth_device(last_bt))

    def _apply_snapshot(self, snap: dict):
        self.sinks   = snap["sinks"]
        self.sources = snap["sources"]
        self.default_sink   = snap["defaults"]["sink"]
        self.default_source = snap["defaults"]["source"]

        # UI: selectors
        self.populate_output_devices()
        self.populate_input_devices()

        # Labels
        self.output_device_label.setText(f"Output Device: {self.get_device_display_name(self.default_sink)}")
        self.input_device_label.setText(f"Input Device: {self.get_device_display_name(self.default_source)}")

        # Volumes/mutes
        out = snap["sink_map"].get(self.default_sink, {"volume": 0, "mute": False})
        inn = snap["source_map"].get(self.default_source, {"volume": 0, "mute": False})
        self.is_muted = out["mute"]
        self.is_input_muted = inn["mute"]

        self.volume_bar.setVolume(out["volume"])
        self.label.setText(f"Output Volume: {out['volume']}%")
        self.input_volume_bar.setVolume(inn["volume"])
        self.input_label.setText(f"Input Volume: {inn['volume']}%")

    # -------- UI --------
    def init_ui(self):
        self.setWindowTitle('Blue Pulse')
        self.resize(880, 520)
        self._profiles_window = None
        
        # Warm dark (coffee/cocoa) theme
        self.setStyleSheet("""
            QWidget {
                background-color: #140E0B;        /* deep cocoa */
                color: #F0E6DC;                    /* warm ivory text */
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
            QLabel {
                background: transparent;
                color: #F0E6DC;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: 700;
                padding: 6px 0 12px 0;
            }
            QLabel#volumeLabel, QLabel#deviceLabel {
                font-size: 13px;
                padding: 6px 12px;
                border: 1px solid #3B2A22;        /* roasted border */
                border-radius: 8px;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #1E140F, stop:1 #120C09);
            }
            QComboBox {
                background: #1B120D;
                color: #F5ECE3;
                border: 1px solid #3B2A22;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QComboBox:hover { border-color: #5A3F31; }   /* lighter roast */
            QComboBox QAbstractItemView {
                background: #1B120D;
                color: #F5ECE3;
                selection-background-color: #2A1A12;
                selection-color: #FFFFFF;
                border: 1px solid #3B2A22;
            }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #2A1C15, stop:1 #1B120D);  /* espresso sheen */
                color: #F7F0E8;
                border: 1px solid #3B2A22;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                           stop:0 #342318, stop:1 #20140F);
                border-color: #5A3F31;
            }
            QPushButton:pressed {
                background: #1A120E;
                border-color: #734E38;            /* caramel edge */
            }
            QListWidget {
                background: #1A120E;
                color: #F0E6DC;
                border: 1px solid #3B2A22;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: #2A1A12;             /* dark walnut */
                color: #FFFFFF;
            }
        """)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(18)

        # Left column
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(12)

        self.title_label = QtWidgets.QLabel("Volume Controller")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(qt_align_center())

        self.output_device_label = QtWidgets.QLabel("Output Device: …")
        self.output_device_label.setObjectName("deviceLabel")
        self.output_device_label.setAlignment(qt_align_center())

        self.device_selector = QtWidgets.QComboBox()
        self.device_selector.currentIndexChanged.connect(self.change_sink)

        self.label = QtWidgets.QLabel("Output Volume: 0%")
        self.label.setObjectName("volumeLabel")
        self.label.setAlignment(qt_align_center())

        self.volume_bar = VolumeBar(self)
        self.volume_bar.setFixedHeight(64)
        self.volume_bar.volumeChanged.connect(self.set_volume)

        self.input_device_label = QtWidgets.QLabel("Input Device: …")
        self.input_device_label.setObjectName("deviceLabel")
        self.input_device_label.setAlignment(qt_align_center())

        self.input_selector = QtWidgets.QComboBox()
        self.input_selector.currentIndexChanged.connect(self.change_source)

        self.input_label = QtWidgets.QLabel("Input Volume: 0%")
        self.input_label.setObjectName("volumeLabel")
        self.input_label.setAlignment(qt_align_center())

        self.input_volume_bar = VolumeBar(self)
        self.input_volume_bar.setFixedHeight(64)
        self.input_volume_bar.volumeChanged.connect(self.set_input_volume)

        left_layout.addWidget(self.title_label)
        left_layout.addWidget(self.output_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Output Device:"))
        left_layout.addWidget(self.device_selector)
        left_layout.addWidget(self.label)
        left_layout.addWidget(self.volume_bar)

        left_layout.addSpacing(6)
        left_layout.addWidget(self.input_device_label)
        left_layout.addWidget(QtWidgets.QLabel("Input Device:"))
        left_layout.addWidget(self.input_selector)
        left_layout.addWidget(self.input_label)
        left_layout.addWidget(self.input_volume_bar)
        left_layout.addStretch()

        # Right column: Bluetooth
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(10)

        self.bluetooth_label = QtWidgets.QLabel("Bluetooth Devices")
        self.bluetooth_label.setAlignment(qt_align_center())

        self.scan_button = QtWidgets.QPushButton("Scan")
        self.pair_button = QtWidgets.QPushButton("Pair")
        self.unpair_button = QtWidgets.QPushButton("Unpair")
        self.refresh_button = QtWidgets.QPushButton("Refresh")

        self.device_list = QtWidgets.QListWidget()
        self.device_list.setFixedWidth(320)
        self.device_list.itemDoubleClicked.connect(self.set_bluetooth_device_as_default)

        self.scan_button.clicked.connect(self.start_scan)
        self.pair_button.clicked.connect(self.pair_device)
        self.unpair_button.clicked.connect(self.unpair_device)
        self.refresh_button.clicked.connect(self.refresh_all_devices)

        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(self.pair_button)
        btns.addWidget(self.unpair_button)
        btns.addWidget(self.refresh_button)

        right_layout.addWidget(self.bluetooth_label)
        right_layout.addWidget(self.scan_button)
        right_layout.addWidget(self.device_list)
        right_layout.addLayout(btns)
        # Open the Defaults/Profiles (Power) window
        self.profiles_button = QtWidgets.QPushButton("Profiles/Power")
        self.profiles_button.clicked.connect(self.open_profiles_window)
        right_layout.addWidget(self.profiles_button)

        right_layout.addStretch()

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 1)

        self.center_window()

    def center_window(self):
        geo = available_geometry(self)
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def open_profiles_window(self):
        if self._profiles_window is None:
            self._profiles_window = ProfilesWindow()
        self._profiles_window.show()
        self._profiles_window.raise_()
        self._profiles_window.activateWindow()


    # -------- Device population --------
    def get_device_display_name(self, device_name):
        for s in self.sinks:
            if s.get('name') == device_name:
                return s.get('description', device_name)
        for s in self.sources:
            if s.get('name') == device_name:
                return s.get('description', device_name)
        return device_name

    def populate_output_devices(self):
        self.device_selector.blockSignals(True)
        self.device_selector.clear()
        for sink in self.sinks:
            self.device_selector.addItem(sink.get('description', sink.get('name', '')),
                                         {'type': 'sink', 'data': sink})
        for i in range(self.device_selector.count()):
            data = self.device_selector.itemData(i)
            if data and data.get('type') == 'sink' and data['data'].get('name') == self.default_sink:
                self.device_selector.setCurrentIndex(i)
                break
        self.device_selector.blockSignals(False)

    def populate_input_devices(self):
        self.input_selector.blockSignals(True)
        self.input_selector.clear()
        for source in self.sources:
            self.input_selector.addItem(source.get('description', source.get('name', '')),
                                        {'type': 'source', 'data': source})
        for i in range(self.input_selector.count()):
            data = self.input_selector.itemData(i)
            if data and data.get('type') == 'source' and data['data'].get('name') == self.default_source:
                self.input_selector.setCurrentIndex(i)
                break
        self.input_selector.blockSignals(False)

    # -------- Volumes / changes --------
    def set_volume(self, value):
        self.label.setText(f'Output Volume: {value}%')
        if self.default_sink:
            set_sink_volume_cmd(self.default_sink, value)
            if self.is_muted and value > 0:
                set_sink_mute_cmd(self.default_sink, False)
                self.is_muted = False

    def set_input_volume(self, value):
        self.input_label.setText(f'Input Volume: {value}%')
        if self.default_source:
            set_source_volume_cmd(self.default_source, value)
            if self.is_input_muted and value > 0:
                set_source_mute_cmd(self.default_source, False)
                self.is_input_muted = False

    def change_sink(self, index):
        data = self.device_selector.itemData(index)
        if data and data.get('type') == 'sink':
            s = data['data']
            self.default_sink = s.get('name', '')
            if self.default_sink:
                set_default_sink_cmd(self.default_sink)
                snap = get_audio_snapshot()
                self._apply_snapshot(snap)

    def change_source(self, index):
        data = self.input_selector.itemData(index)
        if data and data.get('type') == 'source':
            s = data['data']
            self.default_source = s.get('name', '')
            if self.default_source:
                set_default_source_cmd(self.default_source)
                snap = get_audio_snapshot()
                self._apply_snapshot(snap)

    # ------------------ Bluetooth Methods ------------------
    def start_scan(self):
        self.scanningActive = True
        self.scanned_devices.clear()
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
            existing = [self.device_list.item(i).data(qt_user_role()) for i in range(self.device_list.count())]
            if address not in existing:
                item = QtWidgets.QListWidgetItem(f"{name} [{address}]")
                item.setData(qt_user_role(), address)
                self.device_list.addItem(item)

    def scan_finished(self):
        self.scan_button.setEnabled(True)
        self.scan_thread.quit()
        self.scan_thread.wait()
        self.scanningActive = False

    def get_paired_bluetooth_devices(self):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()
        devices = {}
        for path, ifaces in objects.items():
            if 'org.bluez.Device1' in ifaces:
                p = ifaces['org.bluez.Device1']
                address = p.get('Address', '')
                name = p.get('Name', address)
                if p.get('Paired', False):
                    devices[address] = name
        return devices

    def populate_bluetooth_devices(self):
        if self.scanningActive:
            return
        merged = {}
        merged.update(self.scanned_devices)
        merged.update(self.get_paired_bluetooth_devices())
        self.device_list.clear()
        for address, name in merged.items():
            item = QtWidgets.QListWidgetItem(f"{name} [{address}]")
            item.setData(qt_user_role(), address)
            self.device_list.addItem(item)

    def pair_device(self):
        item = self.device_list.currentItem()
        if not item:
            return
        address = item.data(qt_user_role())
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
        self.sinks   = get_audio_snapshot()["sinks"]
        self.sources = get_audio_snapshot()["sources"]
        pa_address = self.get_recent_bluetooth_address()
        if not pa_address:
            logging.warning("No recent Bluetooth address found.")
            return
        card = get_card_for_device(pa_address)
        if not card:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error", "Failed to find audio card for device.")
            return
        set_card_profile(card, 'a2dp_sink')
        QTimer.singleShot(1500, lambda: self.refresh_after_profile_set(pa_address.replace(":", "_").lower()))

    def get_recent_bluetooth_address(self):
        snap = get_audio_snapshot()
        addr = None
        for s in snap["sinks"]:
            nm = s.get("name", "")
            if nm.startswith("bluez_sink."):
                m = re.match(r'bluez_sink\.([0-9a-f_]{17})', nm)
                if m:
                    addr = m.group(1).replace("_", ":")
        if addr:
            return addr
        for s in snap["sources"]:
            nm = s.get("name", "")
            if nm.startswith("bluez_source."):
                m = re.match(r'bluez_source\.([0-9a-f_]{17})', nm)
                if m:
                    return m.group(1).replace("_", ":")
        return None

    def connect_and_set_bluetooth_device(self, address, is_sink=True):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()
        device_path = None
        for path, ifaces in objects.items():
            if 'org.bluez.Device1' in ifaces:
                props = ifaces['org.bluez.Device1']
                if props.get('Address') == address:
                    device_path = path
                    break
        if not device_path:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Not Found", f"Device {address} not found on D-Bus")
            return

        device = dbus.Interface(bus.get_object('org.bluez', device_path), 'org.bluez.Device1')
        props_iface = dbus.Interface(bus.get_object('org.bluez', device_path), 'org.freedesktop.DBus.Properties')
        try:
            connected = props_iface.Get('org.bluez.Device1', 'Connected')
        except dbus.DBusException as e:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Error", f"Failed to get connection status: {e}")
            return

        if not connected:
            try:
                device.Connect()
                QTimer.singleShot(3000, lambda a=address: self.set_device_as_default_sink_and_source(a, is_sink=is_sink))
            except dbus.DBusException as e:
                QtWidgets.QMessageBox.warning(self, "Bluetooth Connection Failed", f"Failed to connect to {address}: {e}")
        else:
            self.set_device_as_default_sink_and_source(address, is_sink=is_sink)

    def set_device_as_default_sink_and_source(self, address, is_sink=True):
        self.settings.setValue("last_bluetooth", address)
        pa_address = address.replace(":", "_").lower()
        card = get_card_for_device(address)
        if not card:
            QtWidgets.QMessageBox.warning(self, "Bluetooth Device Error", "Failed to find audio card for the device.")
            return
        set_card_profile(card, 'a2dp_sink')
        QTimer.singleShot(1500, lambda: self.refresh_after_profile_set(pa_address))

    def refresh_after_profile_set(self, pa_address):
        snap = get_audio_snapshot()
        sink_name = next((s["name"] for s in snap["sinks"] if s["name"].startswith(f"bluez_sink.{pa_address}")), None)
        src_name  = next((s["name"] for s in snap["sources"] if s["name"].startswith(f"bluez_source.{pa_address}")), None)

        if sink_name:
            try:
                set_default_sink_cmd(sink_name)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default sink: {e}")
        if src_name:
            try:
                set_default_source_cmd(src_name)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "PulseAudio Error", f"Failed to set default source: {e}")

        self._apply_snapshot(get_audio_snapshot())
        if sink_name and src_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "Bluetooth device set as default input and output.")
        elif sink_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "Bluetooth device set as default output.")
        elif src_name:
            QtWidgets.QMessageBox.information(self, "Bluetooth Device Set",
                                              "Bluetooth device set as default input.")
        QTimer.singleShot(3000, self.refresh_all_devices)

    def unpair_device(self):
        item = self.device_list.currentItem()
        if not item:
            return
        address = item.data(qt_user_role())
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

    # -------- Refreshes --------
    def refresh_audio_devices(self):
        try:
            snap = get_audio_snapshot()
            self._apply_snapshot(snap)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to refresh audio devices: {e}")

    def refresh_bluetooth_devices(self):
        if not self.scanningActive:
            self.populate_bluetooth_devices()

    def refresh_all_devices(self):
        self.refresh_audio_devices()
        if not self.scanningActive:
            self.refresh_bluetooth_devices()

    # -------- D-Bus listener --------
    @pyqtSlot()
    def emit_devices_updated(self):
        self.devices_updated.emit()

    @pyqtSlot()
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

    def set_bluetooth_device_as_default(self, item: QtWidgets.QListWidgetItem):
        address = item.data(qt_user_role())
        self.connect_and_set_bluetooth_device(address)

    # Optional: connect paired devices shortly after launch
    def connect_paired_bluetooth_devices(self):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()
        for path, ifaces in objects.items():
            if 'org.bluez.Device1' in ifaces:
                p = ifaces['org.bluez.Device1']
                address = p.get('Address', '')
                paired = p.get('Paired', False)
                connected = p.get('Connected', False)
                if paired and not connected:
                    try:
                        dev = dbus.Interface(bus.get_object('org.bluez', path), 'org.bluez.Device1')
                        dev.Connect()
                        QTimer.singleShot(5000, lambda a=address: self.set_device_as_default_sink_and_source(a, is_sink=True))
                    except dbus.DBusException as e:
                        logging.error(f"Failed to connect to {address}: {e}")
        QTimer.singleShot(6000, self.refresh_all_devices)
