# -*- coding: utf-8 -*-

"""
Blue Pulse — Fast Audio & Bluetooth Controller
PyQt6-first (fallback to PyQt5), PipeWire/PulseAudio (via pactl), BlueZ over D-Bus.

- Faster startup: UI paints first, heavy work deferred
- Single-shot pactl snapshot for defaults, sinks, sources, volume & mute
- Warm dark (coffee/cocoa) theme

This program comes with ABSOLUTELY NO WARRANTY.
GPL v2 — JJ Posti <techtimejourney.net>
"""

import sys
import threading
import logging
sys.dont_write_bytecode = True
from .qt_compat import QtWidgets, USING_QT6
from .controller import VolumeController

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from .agent import Agent

logging.disable(logging.CRITICAL)

def main():
    # Route D-Bus to GLib
    DBusGMainLoop(set_as_default=True)

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Run GLib main loop (for dbus) in a background thread
    g_loop = GLib.MainLoop()
    g_thread = threading.Thread(target=g_loop.run, daemon=True)
    g_thread.start()

    # Register BlueZ Agent
    bus = dbus.SystemBus()
    agent_path = "/blue/pulse/agent"
    agent = Agent(bus, agent_path)
    am = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1")
    try:
        am.RegisterAgent(agent_path, "NoInputNoOutput")
    except dbus.DBusException as e:
        if getattr(e, "get_dbus_name", lambda: "")() != 'org.bluez.Error.AlreadyExists':
            raise
    try:
        am.RequestDefaultAgent(agent_path)
    except dbus.DBusException as e:
        if getattr(e, "get_dbus_name", lambda: "")() != 'org.bluez.Error.AlreadyExists':
            raise

    # Show main controller
    w = VolumeController()
    w.show()

    # Enter Qt loop
    ret = app.exec() if USING_QT6 else app.exec_()

    # Cleanup
    try:
        am.UnregisterAgent(agent_path)
    except dbus.DBusException:
        pass
    g_loop.quit()
    sys.exit(ret)
