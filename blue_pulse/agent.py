# -*- coding: utf-8 -*-
import dbus,sys
import dbus.service
sys.dont_write_bytecode = True
class Agent(dbus.service.Object):
    """
    Minimal BlueZ agent: 'NoInputNoOutput' – accepts defaults and returns 0000 pin when asked.
    """

    def __init__(self, bus, path):
        super().__init__(bus, path)

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device): return "0000"

    @dbus.service.method('org.bluez.Agent1', in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode): pass

    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey): return

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device): return

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self): pass
