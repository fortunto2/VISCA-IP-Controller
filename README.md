# VISCA-IP-Controller

Python library for controlling PTZ cameras using VISCA protocol over IP networks.

## Features

- **UDP Camera** (`Camera`) - Standard VISCA-over-IP protocol with UDP transport
- **TCP Camera** (`TcpCamera`) - Raw VISCA protocol over TCP for cameras behind network proxies
- Pan, tilt, zoom control with speed and position support
- Focus control (auto/manual modes)
- Preset management (save/recall)
- Position queries for closed-loop control

## Installation

```bash
pip install visca-over-ip
```

Or with uv:

```bash
uv add visca-over-ip
```

For development:

```bash
git clone https://github.com/fortunto2/VISCA-IP-Controller
cd VISCA-IP-Controller
uv sync --extra dev
```

## Quick Start

### UDP Connection (Standard VISCA-over-IP)

Most PTZ cameras use UDP with VISCA-over-IP protocol headers:

```python
from visca_over_ip import Camera

# Connect to camera
cam = Camera('192.168.1.100', port=52381)

# Get current position
pan, tilt = cam.get_pantilt_position()
zoom = cam.get_zoom_position()
print(f"Position: pan={pan}, tilt={tilt}, zoom={zoom}")

# Move camera
cam.pantilt(pan_speed=5, tilt_speed=0)   # Pan right
cam.pantilt(pan_speed=-5, tilt_speed=0)  # Pan left
cam.pantilt(pan_speed=0, tilt_speed=5)   # Tilt up
cam.pantilt(pan_speed=0, tilt_speed=0)   # Stop

# Zoom
cam.zoom(speed=3)   # Zoom in
cam.zoom(speed=-3)  # Zoom out
cam.zoom(speed=0)   # Stop

# Go to home position
cam.pantilt_home()

# Presets
cam.save_preset(1)
cam.recall_preset(1)

# Close connection
cam.close_connection()
```

### TCP Connection (Raw VISCA)

Some setups require raw VISCA commands over TCP (e.g., cameras behind network proxies):

```python
from visca_over_ip import TcpCamera

# Connect to camera via TCP
cam = TcpCamera('192.168.1.100', port=5678)
cam.connect()

# Same API as UDP camera
pan, tilt = cam.get_pantilt_position()
print(f"Position: pan={pan}, tilt={tilt}")

# Move camera
cam.pantilt(pan_speed=8, tilt_speed=0)  # Pan right at speed 8
import time
time.sleep(1)
cam.pantilt_stop()

# Get new position (real-time feedback!)
pan, tilt = cam.get_pantilt_position()
print(f"New position: pan={pan}, tilt={tilt}")

cam.close_connection()
```

### Context Manager

TcpCamera supports context manager for automatic cleanup:

```python
from visca_over_ip import TcpCamera

with TcpCamera('192.168.1.100', 5678) as cam:
    pan, tilt = cam.get_pantilt_position()
    cam.pantilt(pan_speed=5, tilt_speed=0)
    # Connection automatically closed
```

## API Reference

### Movement Control

| Method | Description |
|--------|-------------|
| `pantilt(pan_speed, tilt_speed)` | Continuous movement (-24 to 24) |
| `pantilt(pan_speed, tilt_speed, pan_position, tilt_position)` | Move to absolute position |
| `pantilt(pan_speed, tilt_speed, pan_position, tilt_position, relative=True)` | Relative movement |
| `pantilt_stop()` | Stop all movement |
| `pantilt_home()` | Go to home position |
| `pantilt_reset()` | Reset to default position |

### Zoom Control

| Method | Description |
|--------|-------------|
| `zoom(speed)` | Continuous zoom (-7 to 7) |
| `zoom_to(position)` | Zoom to position (0.0-1.0) |
| `zoom_stop()` | Stop zooming |

### Focus Control

| Method | Description |
|--------|-------------|
| `set_focus_mode(mode)` | Set mode: 'auto', 'manual', etc. |
| `manual_focus(speed)` | Manual focus (-7 to 7) |
| `get_focus_mode()` | Get current mode |

### Position Queries

| Method | Description |
|--------|-------------|
| `get_pantilt_position()` | Returns (pan, tilt) tuple |
| `get_zoom_position()` | Returns zoom value |

### Presets

| Method | Description |
|--------|-------------|
| `save_preset(num)` | Save position (0-255) |
| `recall_preset(num)` | Recall position (0-255) |

## When to Use UDP vs TCP

| Protocol | Use Case |
|----------|----------|
| **UDP** (`Camera`) | Direct connection to camera on local network |
| **TCP** (`TcpCamera`) | Camera behind proxy, firewall, or network bridge |

## Running Tests

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
pytest

# Run with coverage
pytest --cov=visca_over_ip
```

## Documentation

Full documentation: https://visca-over-ip.readthedocs.io

## Related Projects

- [VISCA IP Controller GUI](https://github.com/misterhay/VISCA-IP-Controller-GUI) - Graphical interface
- [Visca Joystick](https://github.com/International-Anglican-Church/visca-joystick) - Hardware joystick control

## License

MIT License
