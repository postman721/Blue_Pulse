# Blue Pulse — Fast Audio + Bluetooth Controller (PyQt6 / PyQt5)

<img width="2154" height="604" alt="Image" src="https://github.com/user-attachments/assets/8e6ae059-0964-4694-bfb4-4655b30c4e11" />

**Blue Pulse** is a Linux GUI for quickly controlling output/input volume, switching default audio devices, and pairing/unpairing Bluetooth devices. It also includes a **Profiles (Power)** tab to switch **card profiles** (e.g., A2DP vs. HFP/HSP) and to hard‑power an audio card **off** by setting profile `off`, similar to pavucontrol’s “Off”.

- **Audio backends:** PipeWire (via the PulseAudio compatibility layer) or PulseAudio — commands go through `pactl`.  
- **UI:** PyQt6 first (falls back to PyQt5).  
- **Bluetooth:** BlueZ over D‑Bus with a GLib main loop for reliable events.  
- **Theme:** warm dark background, **all text forced to white** for readability.

Released under **GPL v2**. Use at your own responsibility.  
Author: **JJ Posti** <techtimejourney.net>, 2024–2025.

---

## What’s inside (features)

### 1) Default (Merged I/O)
- **Output (sink):** pick device → *Set as Default* → *Mute / Unmute*  
- **Input (source):** pick device → *Set as Default* → *Mute / Unmute*  
- Uses single‑shot queries to keep the UI responsive and correct.

### 2) Profiles (Power)
- Pick any **audio card** → choose a **profile** → *Apply*  
- **Turn Off / On:** switches the card profile to `off` (hard power off) and back to your last non‑off profile.  
- **Non‑blocking verification:** profile changes are verified with a short polling window to avoid false “failed” messages on Bluetooth devices that temporarily re‑enumerate.

### 3) Bluetooth integration (BlueZ)
- **Scan**, **Pair**, **Unpair**; double‑click to set a paired BT device as default I/O.  
- Automatically switches to **A2DP** profile after pairing when available.

### 4) Quality of life
- Fast startup (UI paints first; heavy work deferred).  
- All text is white; readable on the dark theme.  
- Optional “no bytecode” runs (see Usage).

---

## Requirements

- **Linux with BlueZ** (Bluetooth) and **PipeWire (recommended)** or **PulseAudio**.  
- `pactl` must be available (provided by PulseAudio client tools; PipeWire uses a PulseAudio‑compatible layer).

> On **PipeWire systems**, make sure the PulseAudio compatibility shim is installed and active (see distro notes below).

---

## Install dependencies

### Debian / Ubuntu (example)

**PyQt6:**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3-pyqt6 \
  python3-dbus \
  python3-gi gir1.2-glib-2.0 \
  bluez \
  pulseaudio-utils
  pipewire-pulse
```

**PyQt5 (fallback):**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3-pyqt5 \
  python3-dbus \
  python3-gi gir1.2-glib-2.0 \
  bluez \
  pulseaudio-utils
  pipewire-pulse
```

> `pulseaudio-utils` provides `pactl` on Debian/Ubuntu.

##### pipewire-pulse is used as a replacement of Pulseaudio. If you use Pulseaudio and are happy with it then it is fine to not install pipewire-pulse. 

<b> See pipewire_install.sh if you want to switch from Pulseaudio to Pipewire on Debian based systems. </b>

---

### Arch Linux (best-effort package list)

```bash
sudo pacman -S --needed \
  python-pyqt6 python-dbus python-gobject \
  bluez libpulse pipewire-pulse
# (Optional fallback)
# sudo pacman -S python-pyqt5
```

- **PyQt6 / PyQt5:** `python-pyqt6` and `python-pyqt5` are in *extra*.
- **D‑Bus bindings:** `python-dbus`.
- **PyGObject (GLib/DBus main loop):** `python-gobject`.
- **Bluetooth:** `bluez` (optionally `bluez-utils` for `bluetoothctl`).
- **`pactl`:** provided by **`libpulse`** on Arch (`/usr/bin/pactl`).
- **PipeWire PA layer:** `pipewire-pulse` (PulseAudio replacement).

---

### Fedora (best-effort package list)

```bash
sudo dnf install -y \
  python3-pyqt6 python3-dbus python3-gobject-base \
  bluez pulseaudio-utils pipewire-pulseaudio
# (Optional fallback)
# sudo dnf install -y python3-qt5
```

- **PyQt6 / PyQt5:** `python3-pyqt6` and `python3-qt5`.
- **D‑Bus bindings:** `python3-dbus`.
- **PyGObject (base):** `python3-gobject-base` (sufficient for GLib loop; no GTK needed).
- **Bluetooth:** `bluez`.
- **`pactl`:** `pulseaudio-utils`.
- **PipeWire PA layer:** `pipewire-pulseaudio`.

---

## Optional

- **Add your user to the bluetooth group** (not always required; distro policies vary):
```bash
sudo usermod -aG bluetooth $USER
```

## Install & Run

### Run from the source tree (module form)
From the parent folder (the folder containing the `blue_pulse` folder):

```
PYTHONDONTWRITEBYTECODE=1 python3 -m blue_pulse
# or
python3 -B -m blue_pulse
```

Again: If you see “`No module named blue_pulse`”, ensure you’re running **from the parent directory** of the `blue_pulse/` (not from inside the folder of blue_pulse itself).


## Usage overview
**Main Window:** Sound controls, input and output selection, scan, pairing and unpairing functionalities.

**Profiles/power:**
- **Default tab:** pick output/input, set defaults, mute/unmute.  
- **Profiles (Power) tab:** select a card, choose a profile or turn off, *Apply* 

---


## Tested devices (examples)

- **Bluetooth:** PS4/PS5 controllers, JBL Bluetooth headset  
- **Wired:** gaming headset, PS5 DualSense (USB)  
- **Recording:** Skype (web)

> Note: occasionally, headsets need a re-pair or profile toggle to land on **A2DP** for best quality.

Please notice that this program does not run on background. This means that you may need to open it to get your sound devices working. In the future tray and systemd integrations are coming.
