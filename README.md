## Blue Pulse: A Volume Controller with Bluetooth Pairing Integration PyQt5 or PyQT6

<img width="989" height="612" alt="Image" src="https://github.com/user-attachments/assets/c2c0a3d0-b6a1-4d5d-8a1c-c66477638cfc" />

A Python application that provides a graphical interface to control system volume, manage input/output audio devices, and pair/unpair Bluetooth devices on Linux systems. This application requires PipeWire.


Refer to pipewire_install.sh for installation instructions, for Debian/Ubuntu.

Released under GPL v2. Use at your own responsibility.

Author: JJ Posti <techtimejourney.net>, 2024


PYQt6: Install the required dependencies, run the following command:

		sudo apt-get update
		sudo apt-get install -y \
		python3-pyqt6 \
		python3-dbus \
		python3-gi gir1.2-glib-2.0 \
		bluez \
		pulseaudio-utils


PYQt5: Install the required dependencies, run the following command:

		sudo apt-get update
		sudo apt-get install -y \
		python3-pyqt5 \
		python3-dbus \
		python3-gi gir1.2-glib-2.0 \
		bluez \
		pulseaudio-utils



### Optional: Add User to Bluetooth Group

If your user is not already in the standard Bluetooth group, add it with:

		sudo usermod -aG bluetooth $USER

### Optional dependency: pavucontrol: If you need to fine-tune or disable/enable audio sources.

### Usage

Make the script executable:

		chmod +x blue_pulse.py

Run the application:

		python3 blue_pulse.py

<b> Note: The program does not run as a daemon in the background. You must open it at least once per session to connect all your devices.</b>

### Features

Volume Control

    Adjust Output Volume:
        Use the output volume bar to set the system's output volume.
        The label above the bar displays the current volume percentage.

    Adjust Input Volume:
        Use the input volume bar to set the system's input volume (microphone).
        The label above the bar displays the current volume percentage.

Audio Device Selection

    Select Output Device:
        Choose from the available output devices in the "Output Device" dropdown menu.
        The selected device becomes the system's default output device.

    Select Input Device:
        Choose from the available input devices in the "Input Device" dropdown menu.
        The selected device becomes the system's default input device.

#### Bluetooth Management

Scanning for Devices

    Click the "Scan" button under the "Bluetooth Devices" section.
    The application will search for nearby Bluetooth devices for approximately 5 seconds.
    Discovered devices will appear in the list below the "Scan" button.

Pairing a Device

    Select a device from the list of discovered Bluetooth devices.
    Click the "Pair" button.
    The application will attempt to pair and connect to the selected device.
    Upon success:
        The device will be added to the audio device selectors.
        It can be used immediately.
    A message box will inform you of the pairing result.

Unpairing a Device

    Select a paired device from the list.
    Click the "Unpair" button.
    The application will remove the device from your system.
    A message box will inform you of the unpairing result.

Tested Devices and Notes

    Bluetooth Devices Tested With:
        PS4 controller
        PS5 DualSense controller
        JBL Bluetooth headset

    Wired Devices Tested With:
        Wired gaming headset and PS5 DualSense controller
		
    Recording Tested With:
        Skype web version

Note: Occasionally, Bluetooth headsets may need to be paired again to enable the better-sounding audio profile.
