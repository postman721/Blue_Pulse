# -*- coding: utf-8 -*-
import re, sys
import logging
from .qt_compat import QProcess
sys.dont_write_bytecode = True
logging.disable(logging.CRITICAL)
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# -------- pactl helpers (fast) --------
def run_pactl_command(args):
    """Run a pactl command using QProcess and return its output (UTF-8)."""
    process = QProcess()
    process.start("pactl", args)
    if process.waitForFinished(3000):
        return bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
    logging.error("pactl command timed out: " + " ".join(args))
    return ""

def _parse_default_from_info(info_txt: str, label: str) -> str:
    for line in info_txt.splitlines():
        if line.startswith(label + ":"):
            return line.split(":", 1)[1].strip()
    return ""

def _parse_devices_with_state(text: str, kind: str):
    """
    Parse 'pactl list sinks|sources' capturing name, description, per-block volume% and mute.
    Returns (items, state_map) where state_map[name] = {'volume': int, 'mute': bool}
    """
    items = []
    state_map = {}
    current = {}
    cur_vol = None
    cur_mute = None

    header = f"{kind.capitalize()} #"

    def _commit():
        nonlocal current, cur_vol, cur_mute
        if current.get("name"):
            items.append(current)
            state_map[current["name"]] = {
                "volume": int(cur_vol) if cur_vol is not None else 0,
                "mute": bool(cur_mute) if cur_mute is not None else False,
            }
        current = {}
        cur_vol = None
        cur_mute = None

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(header):
            _commit()
        elif line.startswith("Name:"):
            current["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            current["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("Volume:"):
            m = re.search(r"(\d+)%", line)
            if m:
                cur_vol = int(m.group(1))
        elif line.startswith("Mute:"):
            cur_mute = (line.split(":", 1)[1].strip().lower() == "yes")

    _commit()
    return items, state_map

def get_audio_snapshot():
    """
    Return a single snapshot:
    {
      'defaults': {'sink': str, 'source': str},
      'sinks':   [{'name','description'}, ...],
      'sources': [{'name','description'}, ...],
      'sink_map':   {name: {'volume': int, 'mute': bool}},
      'source_map': {name: {'volume': int, 'mute': bool}},
    }
    """
    info_txt  = run_pactl_command(['info'])
    sinks_txt = run_pactl_command(['list', 'sinks'])
    srcs_txt  = run_pactl_command(['list', 'sources'])

    defaults = {
        "sink":   _parse_default_from_info(info_txt, "Default Sink"),
        "source": _parse_default_from_info(info_txt, "Default Source"),
    }
    sinks, sink_map   = _parse_devices_with_state(sinks_txt,  kind="sink")
    sources, src_map  = _parse_devices_with_state(srcs_txt,   kind="source")

    # PipeWire sometimes says "pipewire" as default
    if defaults["sink"].lower() == "pipewire" and sinks:
        defaults["sink"] = sinks[0]["name"]
    if defaults["source"].lower() == "pipewire" and sources:
        defaults["source"] = sources[0]["name"]

    return {
        "defaults": defaults,
        "sinks": sinks,
        "sources": sources,
        "sink_map": sink_map,
        "source_map": src_map,
    }

# Thin wrappers kept for direct control actions
def set_default_sink_cmd(sink_name):   run_pactl_command(['set-default-sink',   sink_name])
def set_default_source_cmd(src_name):  run_pactl_command(['set-default-source', src_name])
def set_sink_volume_cmd(sink_name, v): run_pactl_command(['set-sink-volume',    sink_name, f"{v}%"])
def set_source_volume_cmd(src_name, v):run_pactl_command(['set-source-volume',  src_name, f"{v}%"])
def get_sink_mute_cmd(sink_name):      return 'yes' in run_pactl_command(['get-sink-mute', sink_name]).lower()
def get_source_mute_cmd(src_name):     return 'yes' in run_pactl_command(['get-source-mute', src_name]).lower()
def set_sink_mute_cmd(sink_name, m):   run_pactl_command(['set-sink-mute',      sink_name, '1' if m else '0'])
def set_source_mute_cmd(src_name, m):  run_pactl_command(['set-source-mute',    src_name, '1' if m else '0'])

# Cards/profile (for Bluetooth A2DP)
def list_cards_text():                  return run_pactl_command(['list', 'cards'])

def get_card_for_device(address):
    txt = list_cards_text()
    expected = f'bluez_card.{address.replace(":", "_").lower()}'
    current_card = None
    for raw in txt.splitlines():
        line = raw.strip()
        if line.startswith("Card #"):
            current_card = line.split("#")[1].rstrip(":")
        elif line.startswith("Name:") and current_card:
            name = line.split(":", 1)[1].strip()
            if name.startswith(expected):
                return name
    return None

def set_card_profile(card_name, profile): run_pactl_command(['set-card-profile', card_name, profile])
