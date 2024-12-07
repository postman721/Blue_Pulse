#!/bin/bash

# Switch from PulseAudio to PipeWire on Debian Bookworm
set -e

echo "Updating package list..."
sudo apt update

echo "Installing PipeWire and required components..."
sudo apt install -y pipewire pipewire-audio-client-libraries libspa-0.2-bluetooth pipewire-pulse 

echo "Disabling and stopping PulseAudio services..."
systemctl --user stop pulseaudio.service pulseaudio.socket || echo "PulseAudio service not running"
systemctl --user disable pulseaudio.service pulseaudio.socket || echo "PulseAudio service not enabled"
systemctl --user mask pulseaudio || echo "PulseAudio already masked"

echo "Enabling and starting PipeWire services..."
systemctl --user enable pipewire pipewire-pulse
systemctl --user start pipewire pipewire-pulse

echo "Verifying PipeWire installation..."
if pactl info | grep -q "PulseAudio (on PipeWire)"; then
    echo "PipeWire is successfully managing audio."
else
    echo "PipeWire setup might have an issue. Please check manually."
fi

echo "Removing PulseAudio..."
sudo apt remove -y pulseaudio || echo "PulseAudio is not installed or already removed."

echo "We want to keep pactl onboard - keeping pulseaudio-utils"
sudo apt install pulseaudio-utils -y

echo "Setup complete! You may want to reboot your system to ensure all changes take effect."
echo "Check if system is using pipewire with: pactl info  -> After the reboot"
