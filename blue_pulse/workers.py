# -*- coding: utf-8 -*-
from .qt_compat import QtCore, pyqtSignal, pyqtSlot
import dbus, sys
sys.dont_write_bytecode = True
class ScanWorker(QtCore.QObject):
    devicesFound = pyqtSignal(dict)
    scanFinished = pyqtSignal()

    @pyqtSlot()
    def start_scan(self):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()

        adapter_path = None
        for path, ifaces in objects.items():
            if 'org.bluez.Adapter1' in ifaces:
                adapter_path = path
                break
        if adapter_path is None:
            self.scanFinished.emit()
            return

        adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path), 'org.bluez.Adapter1')
        try:
            adapter.StartDiscovery()
        except dbus.DBusException:
            self.scanFinished.emit()
            return

        QtCore.QThread.sleep(10)  # brief discovery period

        try:
            adapter.StopDiscovery()
        except dbus.DBusException:
            pass

        objects = mgr.GetManagedObjects()
        for path, ifaces in objects.items():
            if 'org.bluez.Device1' in ifaces:
                p = ifaces['org.bluez.Device1']
                address = p.get('Address', '')
                name = p.get('Name', address)
                self.devicesFound.emit({address: name})

        self.scanFinished.emit()

class PairWorker(QtCore.QObject):
    pairingResult = pyqtSignal(bool, str)

    def __init__(self, device_address):
        super().__init__()
        self.device_address = device_address

    @pyqtSlot()
    def pair(self):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()

        device_path = None
        for path, ifaces in objects.items():
            if 'org.bluez.Device1' in ifaces:
                p = ifaces['org.bluez.Device1']
                if p.get('Address') == self.device_address:
                    device_path = path
                    break
        if not device_path:
            self.pairingResult.emit(False, "Device not found")
            return

        device = dbus.Interface(bus.get_object('org.bluez', device_path), 'org.bluez.Device1')
        props = dbus.Interface(bus.get_object('org.bluez', device_path), 'org.freedesktop.DBus.Properties')
        try:
            props.Set('org.bluez.Device1', 'Trusted', True)
        except dbus.DBusException:
            pass

        try:
            device.Pair()
            QtCore.QThread.sleep(2)
            device.Connect()
            self.pairingResult.emit(True, "Pairing and connection successful")
        except dbus.DBusException as e:
            if getattr(e, "get_dbus_name", lambda: "")() == 'org.bluez.Error.AlreadyExists':
                try:
                    device.Connect()
                    self.pairingResult.emit(True, "Device already paired and connected")
                except dbus.DBusException as conn_e:
                    self.pairingResult.emit(False, f"Already paired, but failed to connect: {conn_e}")
            else:
                self.pairingResult.emit(False, str(e))

class UnpairWorker(QtCore.QObject):
    unpairingResult = pyqtSignal(bool, str)

    def __init__(self, device_address):
        super().__init__()
        self.device_address = device_address

    @pyqtSlot()
    def unpair(self):
        bus = dbus.SystemBus()
        mgr = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = mgr.GetManagedObjects()

        adapter_path = None
        device_path = None
        for path, ifaces in objects.items():
            if 'org.bluez.Adapter1' in ifaces:
                adapter_path = path
            if 'org.bluez.Device1' in ifaces:
                p = ifaces['org.bluez.Device1']
                if p.get('Address') == self.device_address:
                    device_path = path
                    break
        if not device_path or not adapter_path:
            self.unpairingResult.emit(False, "Device not found")
            return

        adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path), 'org.bluez.Adapter1')
        try:
            adapter.RemoveDevice(device_path)
            self.unpairingResult.emit(True, "Unpairing successful")
        except dbus.DBusException as e:
            self.unpairingResult.emit(False, str(e))
