# -*- coding: utf-8 -*-
"""
BluePulse — Default (merged I/O) + Profiles (Power)

Tab "Default":
  - Output (sink): pick device, Set as Default, Toggle Mute
  - Input  (source): pick device, Set as Default, Toggle Mute

Tab "Profiles (Power)":
  - Choose any audio card, pick a profile and Apply
  - Turn Off/On by switching the card's profile to 'off'
"""

from __future__ import annotations
import os, sys
import re
import shutil
import subprocess
sys.dont_write_bytecode = True

from .qt_compat import QtCore, QtWidgets, Qt, USING_QT6, qt_align_center

__all__ = ["DefaultPane", "ProfilesPane", "ProfilesWindow"]

# ============================== pactl backend ==============================

PACTL_PATH = shutil.which("pactl")
LAST_PROFILE: dict[str, str] = {}   # remember last non-off profile per card

def _run_pactl(args, parent: QtWidgets.QWidget | None = None, show_errors: bool = False):
    """
    Run pactl with LC_ALL=C. Returns (rc, stdout, stderr).
    If show_errors and rc!=0, optionally shows a dialog.
    """
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    if not PACTL_PATH:
        if show_errors and parent:
            QtWidgets.QMessageBox.critical(
                parent, "pactl not found",
                "Could not find 'pactl' in PATH.\nInstall PulseAudio/PipeWire tools or add pactl to PATH."
            )
        return 127, "", "pactl not found"

    try:
        p = subprocess.run([PACTL_PATH] + list(args),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, env=env)
        if show_errors and p.returncode != 0 and parent:
            QtWidgets.QMessageBox.warning(
                parent, "Command failed",
                f"pactl {' '.join(args)}\n\nExit code: {p.returncode}\n{p.stderr.strip() or '(no stderr)'}"
            )
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        if show_errors and parent:
            QtWidgets.QMessageBox.critical(parent, "Error running pactl", str(e))
        return 1, "", str(e)

def _parse_blocks(text: str, header: str):
    blocks, cur = [], []
    for raw in text.splitlines():
        if raw.strip().startswith(header):
            if cur:
                blocks.append("\n".join(cur))
            cur = [raw]
        else:
            cur.append(raw)
    if cur:
        blocks.append("\n".join(cur))
    return blocks

# ---- info/defaults ----
def pactl_info(parent=None):
    return _run_pactl(["info"], parent=parent, show_errors=True)

def get_defaults(parent=None):
    rc, info, _ = pactl_info(parent=parent)
    out = {"sink": "", "source": ""}
    if rc == 0:
        for line in info.splitlines():
            if line.startswith("Default Sink:"):
                out["sink"] = line.split(":", 1)[1].strip()
            elif line.startswith("Default Source:"):
                out["source"] = line.split(":", 1)[1].strip()
    return out

# ---- sinks/sources (names, mute) ----
def list_sinks(parent=None):
    rc, txt, _ = _run_pactl(["list", "sinks"], parent=parent, show_errors=True)
    if rc != 0:
        return []
    out = []
    for b in _parse_blocks(txt, "Sink #"):
        name = desc = ""
        muted = False
        for raw in b.splitlines():
            line = raw.strip()
            if line.startswith("Name:"):          name = line.split(":", 1)[1].strip()
            elif line.startswith("Description:"):  desc = line.split(":", 1)[1].strip()
            elif line.startswith("Mute:"):         muted = (line.split(":", 1)[1].strip().lower() == "yes")
        if name:
            out.append({"name": name, "description": desc or name, "muted": muted})
    return out

def list_sources(parent=None):
    rc, txt, _ = _run_pactl(["list", "sources"], parent=parent, show_errors=True)
    if rc != 0:
        return []
    out = []
    for b in _parse_blocks(txt, "Source #"):
        name = desc = ""
        muted = False
        for raw in b.splitlines():
            line = raw.strip()
            if line.startswith("Name:"):          name = line.split(":", 1)[1].strip()
            elif line.startswith("Description:"):  desc = line.split(":", 1)[1].strip()
            elif line.startswith("Mute:"):         muted = (line.split(":", 1)[1].strip().lower() == "yes")
        if name:
            out.append({"name": name, "description": desc or name, "muted": muted})
    return out

def set_default_sink(name, parent=None):
    rc, _, _ = _run_pactl(["set-default-sink", name], parent=parent, show_errors=True)
    return rc == 0

def set_default_source(name, parent=None):
    rc, _, _ = _run_pactl(["set-default-source", name], parent=parent, show_errors=True)
    return rc == 0

def get_sink_mute(name, parent=None):
    rc, out, _ = _run_pactl(["get-sink-mute", name], parent=parent, show_errors=True)
    return (rc == 0 and "yes" in out.lower())

def get_source_mute(name, parent=None):
    rc, out, _ = _run_pactl(["get-source-mute", name], parent=parent, show_errors=True)
    return (rc == 0 and "yes" in out.lower())

def set_sink_mute(name, mute, parent=None):
    rc, _, _ = _run_pactl(["set-sink-mute", name, "1" if mute else "0"], parent=parent, show_errors=True)
    return rc == 0

def set_source_mute(name, mute, parent=None):
    rc, _, _ = _run_pactl(["set-source-mute", name, "1" if mute else "0"], parent=parent, show_errors=True)
    return rc == 0

# ---- cards & profiles (power via profile=off) ----
def list_cards(parent=None):
    rc, txt, _ = _run_pactl(["list", "cards"], parent=parent, show_errors=True)
    if rc != 0:
        return {}
    cards = {}
    cur = None
    cur_name = None
    in_profiles = False
    for raw in txt.splitlines():
        line = raw.strip()
        if line.startswith("Card #"):
            if cur and cur_name:
                cards[cur_name] = cur
            cur = {"profiles": {}, "active": "", "description": ""}
            cur_name = None
            in_profiles = False
        elif line.startswith("Name:"):
            cur_name = line.split(":", 1)[1].strip()
        elif line.startswith("Profiles:"):
            in_profiles = True
        elif line.startswith("Active Profile:"):
            cur["active"] = line.split(":", 1)[1].strip().split()[0]
            in_profiles = False
        elif in_profiles:
            m = re.match(r"([A-Za-z0-9:_\.\-]+)\s*:\s*(.+)", line)
            if m:
                k, t = m.group(1), m.group(2)
                cur["profiles"][k] = t
        elif line.startswith("device.description") or line.startswith("device.product.name"):
            try:
                _, v = line.split("=", 1)
                cur["description"] = v.strip().strip('"')
            except Exception:
                pass
    if cur and cur_name:
        cards[cur_name] = cur
    return cards

def get_card_active(card_name, parent=None):
    info = list_cards(parent).get(card_name)
    if not info:
        return False, ""  # not present (e.g., during BT re-enumeration)
    return True, info.get("active", "")

def set_card_profile_command(card_name, profile_key, parent=None):
    """Fire-and-forget command; verification is handled asynchronously in UI."""
    rc, _, _ = _run_pactl(["set-card-profile", card_name, profile_key], parent=parent, show_errors=True)
    return rc == 0

def card_supports_off(card_name, parent=None):
    return "off" in list_cards(parent).get(card_name, {}).get("profiles", {})

# ============================== UI widgets ==============================

class DefaultPane(QtWidgets.QWidget):
    """
    One tab for *both* Output (sink) and Input (source):
      - choose device
      - Set as Default
      - Toggle Mute
    """
    changed = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.defaults = {"sink": "", "source": ""}
        self.sinks = []
        self.sources = []
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        # ---- Output row ----
        self.out_combo = QtWidgets.QComboBox()
        self.out_set_btn = QtWidgets.QPushButton("Set Output as Default")
        self.out_mute_btn = QtWidgets.QPushButton("Mute Output")
        self.out_status = QtWidgets.QLabel("—")

        self.out_set_btn.clicked.connect(self._set_default_output)
        self.out_mute_btn.clicked.connect(self._toggle_mute_output)

        layout.addWidget(QtWidgets.QLabel("Output device:"), 0, 0)
        layout.addWidget(self.out_combo, 0, 1, 1, 3)
        layout.addWidget(self.out_set_btn, 0, 4)
        layout.addWidget(self.out_mute_btn, 0, 5)
        layout.addWidget(self.out_status, 1, 1, 1, 5)

        # ---- Input row ----
        self.in_combo = QtWidgets.QComboBox()
        self.in_set_btn = QtWidgets.QPushButton("Set Input as Default")
        self.in_mute_btn = QtWidgets.QPushButton("Mute Input")
        self.in_status = QtWidgets.QLabel("—")

        self.in_set_btn.clicked.connect(self._set_default_input)
        self.in_mute_btn.clicked.connect(self._toggle_mute_input)

        layout.addWidget(QtWidgets.QLabel("Input device:"), 2, 0)
        layout.addWidget(self.in_combo, 2, 1, 1, 3)
        layout.addWidget(self.in_set_btn, 2, 4)
        layout.addWidget(self.in_mute_btn, 2, 5)
        layout.addWidget(self.in_status, 3, 1, 1, 5)

        # Bottom: refresh button
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(self.btn_refresh, 4, 5)

        # Style (simple, warm)
        self.setStyleSheet("""
            QLabel { color:#F0E6DC; }
            QComboBox, QPushButton {
                background:#1B120D; color:#F7F0E8;
                border:1px solid #3B2A22; border-radius:8px; padding:6px 10px; font-weight:600;
            }
            QPushButton:hover, QComboBox:hover { border-color:#5A3F31; }
            QPushButton:pressed { background:#1A120E; border-color:#734E38; }
        """)

    # ---- helpers ----
    def _decorate(self, kind, name, text):
        cur = self.defaults.get(kind, "")
        return f"{text}  (default)" if (name and name == cur) else text

    def refresh(self):
        self.defaults = get_defaults(parent=self)
        self.sinks = list_sinks(parent=self)
        self.sources = list_sources(parent=self)

        # Remember current selections
        out_name = self._current(self.out_combo)
        in_name = self._current(self.in_combo)

        # Fill outputs
        self.out_combo.blockSignals(True)
        self.out_combo.clear()
        for s in self.sinks:
            lbl = self._decorate("sink", s["name"], f"{s['description']}  [{s['name']}]")
            self.out_combo.addItem(lbl, s["name"])
        self.out_combo.blockSignals(False)
        self._reselect(self.out_combo, out_name)

        # Fill inputs
        self.in_combo.blockSignals(True)
        self.in_combo.clear()
        for s in self.sources:
            lbl = self._decorate("source", s["name"], f"{s['description']}  [{s['name']}]")
            self.in_combo.addItem(lbl, s["name"])
        self.in_combo.blockSignals(False)
        self._reselect(self.in_combo, in_name)

        # Update statuses + button texts
        self._refresh_status_labels()

    def _refresh_status_labels(self):
        # Output
        out_name = self._current(self.out_combo)
        o = next((x for x in self.sinks if x["name"] == out_name), None)
        if o:
            self.out_mute_btn.setText("Unmute Output" if o["muted"] else "Mute Output")
            self.out_status.setText(f"Output muted: {'yes' if o['muted'] else 'no'}")
        else:
            self.out_mute_btn.setText("Mute Output")
            self.out_status.setText("—")
        # Input
        in_name = self._current(self.in_combo)
        i = next((x for x in self.sources if x["name"] == in_name), None)
        if i:
            self.in_mute_btn.setText("Unmute Input" if i["muted"] else "Mute Input")
            self.in_status.setText(f"Input muted: {'yes' if i['muted'] else 'no'}")
        else:
            self.in_mute_btn.setText("Mute Input")
            self.in_status.setText("—")

    @staticmethod
    def _current(combo: QtWidgets.QComboBox):
        ix = combo.currentIndex()
        return combo.itemData(ix) if ix >= 0 else None

    @staticmethod
    def _reselect(combo: QtWidgets.QComboBox, name: str | None):
        idx = 0
        if name:
            for i in range(combo.count()):
                if combo.itemData(i) == name:
                    idx = i
                    break
        combo.setCurrentIndex(idx)

    # ---- actions ----
    def _set_default_output(self):
        name = self._current(self.out_combo)
        if not name:
            return
        ok = set_default_sink(name, parent=self)
        if not ok:
            QtWidgets.QMessageBox.information(
                self, "Default not changed",
                "The server refused to change the default output (a policy manager may override it)."
            )
        QtCore.QTimer.singleShot(350, lambda: (self.refresh(), self.changed.emit()))

    def _set_default_input(self):
        name = self._current(self.in_combo)
        if not name:
            return
        ok = set_default_source(name, parent=self)
        if not ok:
            QtWidgets.QMessageBox.information(
                self, "Default not changed",
                "The server refused to change the default input (a policy manager may override it)."
            )
        QtCore.QTimer.singleShot(350, lambda: (self.refresh(), self.changed.emit()))

    def _toggle_mute_output(self):
        name = self._current(self.out_combo)
        if not name:
            return
        cur = get_sink_mute(name, parent=self)
        ok = set_sink_mute(name, not cur, parent=self)
        if not ok:
            QtWidgets.QMessageBox.information(self, "Mute toggle failed", "Output device did not change mute state.")
        QtCore.QTimer.singleShot(300, lambda: (self.refresh(), self.changed.emit()))

    def _toggle_mute_input(self):
        name = self._current(self.in_combo)
        if not name:
            return
        cur = get_source_mute(name, parent=self)
        ok = set_source_mute(name, not cur, parent=self)
        if not ok:
            QtWidgets.QMessageBox.information(self, "Mute toggle failed", "Input device did not change mute state.")
        QtCore.QTimer.singleShot(300, lambda: (self.refresh(), self.changed.emit()))

class ProfilesPane(QtWidgets.QWidget):
    """
    Cards (profiles) + power via profile off/on.
    Uses non-blocking polling to confirm changes (fixes BT false-failure).
    """
    changed = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.cards = {}
        self._build()
        self.refresh()

    def _build(self):
        g = QtWidgets.QGridLayout(self)
        g.setContentsMargins(12, 12, 12, 12)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)

        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.currentIndexChanged.connect(self._on_card_changed)
        g.addWidget(QtWidgets.QLabel("Card:"), 0, 0)
        g.addWidget(self.card_combo, 0, 1, 1, 4)

        self.profile_combo = QtWidgets.QComboBox()
        self.btn_apply = QtWidgets.QPushButton("Apply Profile")
        self.btn_apply.clicked.connect(self._apply_profile_clicked)
        g.addWidget(QtWidgets.QLabel("Profile:"), 1, 0)
        g.addWidget(self.profile_combo, 1, 1, 1, 3)
        g.addWidget(self.btn_apply, 1, 4)

        self.btn_off_on = QtWidgets.QPushButton("Turn Off (Profile)")
        self.btn_off_on.clicked.connect(self._toggle_off_on_clicked)
        g.addWidget(self.btn_off_on, 2, 0, 1, 5)

        self.status = QtWidgets.QLabel("—")
        self.status.setAlignment(qt_align_center())
        g.addWidget(self.status, 3, 0, 1, 5)

        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        g.addWidget(self.btn_refresh, 4, 4)

        self.setStyleSheet("""
            QLabel { color:#F0E6DC; }
            QComboBox, QPushButton {
                background:#1B120D; color:#F7F0E8;
                border:1px solid #3B2A22; border-radius:8px; padding:6px 10px; font-weight:600;
            }
            QPushButton:hover, QComboBox:hover { border-color:#5A3F31; }
            QPushButton:pressed { background:#1A120E; border-color:#734E38; }
        """)

    # ---------- polling helper (non-blocking) ----------
    def _wait_for_profile(self, card, expected, total_ms=6000, interval_ms=200, on_done=None):
        """
        Polls list_cards until card's active profile == expected, or timeout.
        Handles BT case where the card disappears temporarily.
        """
        tries = max(1, total_ms // interval_ms)

        def step():
            nonlocal tries
            tries -= 1
            present, active = get_card_active(card, parent=self)
            if present and active == expected:
                if on_done:
                    on_done(True, active)
                return
            if tries <= 0:
                # Don't call this a failure; it's likely still applying on some systems.
                if on_done:
                    on_done(False, active)
                return
            QtCore.QTimer.singleShot(interval_ms, step)

        QtCore.QTimer.singleShot(interval_ms, step)

    def _set_busy(self, busy: bool, applying_text: str | None = None):
        self.card_combo.setEnabled(not busy)
        self.profile_combo.setEnabled(not busy)
        self.btn_apply.setEnabled(not busy)
        self.btn_off_on.setEnabled(not busy)
        if busy and applying_text:
            self.status.setText(applying_text)

    # ---------- refresh / UI ----------
    def refresh(self):
        self.cards = list_cards(parent=self)
        cur = self._current_card()
        self.card_combo.blockSignals(True)
        self.card_combo.clear()
        for name, info in self.cards.items():
            desc = info.get("description", "")
            label = f"{name} — {desc}" if desc else name
            self.card_combo.addItem(label, name)
        self.card_combo.blockSignals(False)
        self._reselect(self.card_combo, cur)
        self._on_card_changed(self.card_combo.currentIndex())

    def _on_card_changed(self, index):
        card = self._current_card()
        self.profile_combo.clear()
        if not card or card not in self.cards:
            self.btn_off_on.setText("Turn Off (Profile)")
            self.status.setText("—")
            return
        info = self.cards[card]
        profiles = info.get("profiles", {})
        active = info.get("active", "")
        for key, title in profiles.items():
            self.profile_combo.addItem(title, key)
            if key == active:
                self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)
        self.btn_off_on.setText("Turn On (Profile)" if active == "off" else "Turn Off (Profile)")
        self.status.setText(f"Active: {active or '—'}  •  Profiles: {len(profiles)}")

    def _apply_profile_clicked(self):
        card = self._current_card()
        if not card:
            return
        key = self.profile_combo.currentData()
        if not key:
            return

        # remember for one-click Turn On
        if key != "off":
            LAST_PROFILE[card] = key

        ok = set_card_profile_command(card, key, parent=self)
        if not ok:
            return

        # Non-blocking verification (prevents false failure on BT)
        self._set_busy(True, applying_text="Applying profile…")
        self._wait_for_profile(
            card, key, total_ms=6000, interval_ms=200,
            on_done=lambda success, active: self._after_profile_change(card, key, success, active)
        )

    def _toggle_off_on_clicked(self):
        card = self._current_card()
        if not card:
            return
        info = self.cards.get(card, {})
        active = info.get("active", "")
        if active == "off":
            # turn ON: restore last or pick first non-off
            profiles = list(info.get("profiles", {}).keys())
            target = LAST_PROFILE.get(card, "")
            if not target or target not in profiles or target == "off":
                non_off = [k for k in profiles if k != "off"]
                if not non_off:
                    QtWidgets.QMessageBox.information(self, "Unavailable", "This card has no non-off profiles.")
                    return
                target = non_off[0]
            ok = set_card_profile_command(card, target, parent=self)
            if not ok:
                return
            self._set_busy(True, applying_text="Turning on…")
            self._wait_for_profile(
                card, target, total_ms=6000, interval_ms=200,
                on_done=lambda success, active2: self._after_profile_change(card, target, success, active2)
            )
        else:
            # turn OFF
            if not card_supports_off(card, parent=self):
                QtWidgets.QMessageBox.information(self, "Not supported", "This card does not offer profile 'off'.")
                return
            if active and active != "off":
                LAST_PROFILE[card] = active
            ok = set_card_profile_command(card, "off", parent=self)
            if not ok:
                return
            self._set_busy(True, applying_text="Turning off…")
            self._wait_for_profile(
                card, "off", total_ms=6000, interval_ms=200,
                on_done=lambda success, active2: self._after_profile_change(card, "off", success, active2)
            )

    def _after_profile_change(self, card, expected, success, active_now):
        # Re-enable UI and refresh; never show a false failure.
        self._set_busy(False)
        self.refresh()
        self.changed.emit()
        if not success:
            # Don't claim failure — on some systems it will still switch right after.
            QtWidgets.QMessageBox.information(
                self, "Profile change pending",
                "The profile change is still propagating. It often completes shortly on Bluetooth devices.\n"
                "If the UI hasn’t updated yet, try Refresh."
            )

    # ---------- utilities ----------
    def _current_card(self):
        i = self.card_combo.currentIndex()
        return self.card_combo.itemData(i) if i >= 0 else None

    @staticmethod
    def _reselect(combo: QtWidgets.QComboBox, value: str | None):
        idx = 0
        if value:
            for i in range(combo.count()):
                if combo.itemData(i) == value:
                    idx = i
                    break
        combo.setCurrentIndex(idx)

# ------------------------------- Window ----------------------------------

class ProfilesWindow(QtWidgets.QWidget):
    """
    Standalone window hosting the two panes on tabs.
    Safe to open from the main controller.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BluePulse — Defaults & Profiles")
        self.resize(880, 420)

        # Global style for this window: cocoa bg + ALL TEXT WHITE
        self.setStyleSheet("""
            QWidget { background-color:#140E0B; color:#F0E6DC; }
            QTabBar::tab { color:#F0E6DC; }
        """)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        self.default_pane = DefaultPane()
        self.profiles_pane = ProfilesPane()

        # Cross-refresh when something changes
        self.default_pane.changed.connect(self._refresh_all)
        self.profiles_pane.changed.connect(self._refresh_all)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self.default_pane, "Default")
        tabs.addTab(self.profiles_pane, "Profiles (Power)")
        v.addWidget(tabs)

        row = QtWidgets.QHBoxLayout()
        btn = QtWidgets.QPushButton("Refresh All")
        btn.clicked.connect(self._refresh_all)
        row.addStretch()
        row.addWidget(btn)
        v.addLayout(row)

        # Center on current screen
        if USING_QT6:
            scr = self.screen() or QtWidgets.QApplication.primaryScreen()
            geo = scr.availableGeometry()
        else:
            geo = QtWidgets.QDesktopWidget().availableGeometry()
        self.move(geo.x() + (geo.width() - self.width()) // 2,
                  geo.y() + (geo.height() - self.height()) // 2)

        # Optional: title suffix with server
        if PACTL_PATH:
            rc, info, _ = pactl_info(parent=self)
            if rc == 0:
                server = ""
                for line in info.splitlines():
                    if line.startswith("Server Name:"):
                        server = line.split(":", 1)[1].strip()
                        break
                if server:
                    self.setWindowTitle(f"BluePulse — Defaults & Profiles — {server}")

    def _refresh_all(self):
        self.default_pane.refresh()
        self.profiles_pane.refresh()
