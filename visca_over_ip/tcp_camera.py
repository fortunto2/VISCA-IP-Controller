"""
TCP Camera - VISCA over TCP (raw protocol without IP headers)

Some camera setups (e.g., through network proxies) require raw VISCA
commands over TCP instead of the standard VISCA-over-IP UDP protocol.

This module provides TcpCamera class that sends raw VISCA commands
over a TCP connection.
"""

import socket
import time
from typing import Optional, Tuple

from visca_over_ip.exceptions import ViscaException


class TcpCamera:
    """
    Controls a camera using raw VISCA protocol over TCP.

    Unlike the standard Camera class which uses UDP with VISCA-over-IP
    headers, this class sends raw VISCA commands directly over TCP.
    This is useful for cameras accessed through network proxies that
    only forward TCP connections.

    Example usage:
        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        pan, tilt = cam.get_pantilt_position()
        cam.pantilt(pan_speed=5, tilt_speed=0)  # pan right
        cam.close_connection()
    """

    def __init__(self, ip: str, port: int = 5678, timeout: float = 2.0):
        """
        Initialize TCP camera connection parameters.

        :param ip: Camera IP address or hostname
        :param port: VISCA TCP port
        :param timeout: Socket timeout in seconds
        """
        self._ip = ip
        self._port = port
        self._timeout = timeout
        self._sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """
        Establish TCP connection to camera.

        :return: True if connected successfully
        :raises ConnectionError: if connection fails
        """
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self._timeout)
            self._sock.connect((self._ip, self._port))
            return True
        except Exception as e:
            self._sock = None
            raise ConnectionError(f"Failed to connect to {self._ip}:{self._port}: {e}")

    def close_connection(self):
        """Close TCP connection to camera."""
        if self._sock:
            try:
                self._sock.close()
            except:
                pass
            self._sock = None

    def _flush_input(self):
        """Flush any pending data in the receive buffer."""
        if not self._sock:
            return
        self._sock.setblocking(False)
        try:
            while True:
                data = self._sock.recv(1024)
                if not data:
                    break
        except (BlockingIOError, socket.error):
            pass
        finally:
            self._sock.setblocking(True)
            self._sock.settimeout(self._timeout)

    def _send_command(self, command_hex: str, query: bool = False) -> Optional[bytes]:
        """
        Send raw VISCA command and receive response.

        :param command_hex: Command body as hex string (e.g., "06 12" for pan/tilt inquiry)
        :param query: True for inquiry commands (81 09 ...), False for action commands (81 01 ...)
        :return: Response payload (without header/terminator) or None
        :raises ViscaException: if camera returns an error
        :raises ConnectionError: if not connected
        """
        if not self._sock:
            raise ConnectionError("Not connected. Call connect() first.")

        # Flush any stale data before sending new command
        self._flush_input()

        # Build VISCA command: 81 [09|01] [command] FF
        preamble = '81 09' if query else '81 01'
        full_command = f"{preamble} {command_hex} FF"
        command_bytes = bytes.fromhex(full_command.replace(' ', ''))

        # Send command
        self._sock.send(command_bytes)

        # Small delay for response
        time.sleep(0.1)

        # Receive response
        try:
            response = self._sock.recv(1024)
        except socket.timeout:
            return None

        if not response:
            return None

        # Check for error response (90 6X XX FF)
        if len(response) >= 3 and (response[1] & 0xF0) == 0x60:
            raise ViscaException(response)

        # For queries, return the data portion (skip 90 50, remove FF)
        if query and len(response) > 3:
            return response[2:-1]  # Skip header (90 50) and terminator (FF)

        # For action commands, just confirm we got ACK/completion
        return response

    # ==================== Pan/Tilt ====================

    def pantilt(self, pan_speed: int, tilt_speed: int,
                pan_position: int = None, tilt_position: int = None,
                relative: bool = False):
        """
        Control camera pan and tilt.

        For continuous movement, only specify speeds (position=None).
        For absolute/relative positioning, specify both position parameters.

        :param pan_speed: -24 to 24 (negative=left, 0=stop, positive=right)
        :param tilt_speed: -24 to 24 (negative=down, 0=stop, positive=up)
        :param pan_position: Target pan position (optional)
        :param tilt_position: Target tilt position (optional)
        :param relative: If True, positions are relative offsets
        """
        if abs(pan_speed) > 24 or abs(tilt_speed) > 24:
            raise ValueError('Speeds must be between -24 and 24')

        pan_speed_hex = f'{abs(pan_speed):02x}'
        tilt_speed_hex = f'{abs(tilt_speed):02x}'

        if pan_position is not None and tilt_position is not None:
            # Absolute or relative positioning
            def encode_position(pos: int) -> str:
                """Encode position as 4 nibbles with 0 padding."""
                pos_bytes = pos.to_bytes(2, 'big', signed=True)
                return ' '.join(f'0{b >> 4:x} 0{b & 0xf:x}' for b in pos_bytes)

            mode = '03' if relative else '02'
            cmd = f"06 {mode} {pan_speed_hex} {tilt_speed_hex} {encode_position(pan_position)} {encode_position(tilt_position)}"
        else:
            # Continuous movement
            def direction(speed: int) -> str:
                if speed < 0: return '01'  # left/down
                if speed > 0: return '02'  # right/up
                return '03'  # stop

            cmd = f"06 01 {pan_speed_hex} {tilt_speed_hex} {direction(pan_speed)} {direction(tilt_speed)}"

        self._send_command(cmd)

    def pantilt_stop(self):
        """Stop all pan/tilt movement."""
        self.pantilt(0, 0)

    def pantilt_home(self):
        """Move camera to home position."""
        self._send_command('06 04')

    def pantilt_reset(self):
        """Reset pan/tilt to default position."""
        self._send_command('06 05')

    def get_pantilt_position(self) -> Tuple[int, int]:
        """
        Get current pan and tilt position.

        :return: Tuple of (pan, tilt) as signed integers
        """
        response = self._send_command('06 12', query=True)

        if not response or len(response) < 8:
            raise ViscaException(b"Invalid pan/tilt response")

        # Response: 0p 0q 0r 0s 0t 0u 0v 0w (pan=pqrs, tilt=tuvw)
        def decode_position(data: bytes) -> int:
            """Decode 4 nibble-padded bytes to signed int."""
            value = (data[0] & 0x0F) << 12 | (data[1] & 0x0F) << 8 | \
                    (data[2] & 0x0F) << 4 | (data[3] & 0x0F)
            if value >= 0x8000:
                value -= 0x10000
            return value

        pan = decode_position(response[0:4])
        tilt = decode_position(response[4:8])
        return pan, tilt

    # ==================== Zoom ====================

    def zoom(self, speed: int):
        """
        Zoom in or out at given speed.

        :param speed: -7 to 7 (negative=out, 0=stop, positive=in)
        """
        if abs(speed) > 7:
            raise ValueError('Zoom speed must be between -7 and 7')

        speed_hex = f'{abs(speed):x}'

        if speed == 0:
            direction = '0'
        elif speed > 0:
            direction = '2'  # zoom in
        else:
            direction = '3'  # zoom out

        self._send_command(f'04 07 {direction}{speed_hex}')

    def zoom_stop(self):
        """Stop zooming."""
        self.zoom(0)

    def zoom_to(self, position: float):
        """
        Zoom to absolute position.

        :param position: 0.0 to 1.0 (0=wide, 1=tele)
        """
        pos_int = round(position * 16384)
        pos_hex = f'{pos_int:04x}'
        encoded = ' '.join(f'0{c}' for c in pos_hex)
        self._send_command(f'04 47 {encoded}')

    def get_zoom_position(self) -> int:
        """
        Get current zoom position.

        :return: Zoom position as unsigned integer (0-16384 typical)
        """
        response = self._send_command('04 47', query=True)

        if not response or len(response) < 4:
            raise ViscaException(b"Invalid zoom response")

        # Response: 0p 0q 0r 0s
        return (response[0] & 0x0F) << 12 | (response[1] & 0x0F) << 8 | \
               (response[2] & 0x0F) << 4 | (response[3] & 0x0F)

    # ==================== Focus ====================

    def set_focus_mode(self, mode: str):
        """
        Set focus mode.

        :param mode: 'auto', 'manual', 'auto/manual', 'one push trigger', or 'infinity'
        """
        modes = {
            'auto': '38 02',
            'manual': '38 03',
            'auto/manual': '38 10',
            'one push trigger': '18 01',
            'infinity': '18 02'
        }

        mode_lower = mode.lower()
        if mode_lower not in modes:
            raise ValueError(f'Invalid mode: {mode}. Valid: {list(modes.keys())}')

        self._send_command(f'04 {modes[mode_lower]}')

    def manual_focus(self, speed: int):
        """
        Manual focus control.

        :param speed: -7 to 7 (negative=far, 0=stop, positive=near)
        """
        if abs(speed) > 7:
            raise ValueError('Focus speed must be between -7 and 7')

        speed_hex = f'{abs(speed):x}'

        if speed == 0:
            direction = '0'
        elif speed > 0:
            direction = '3'  # near
        else:
            direction = '2'  # far

        self._send_command(f'04 08 {direction}{speed_hex}')

    def get_focus_mode(self) -> str:
        """
        Get current focus mode.

        :return: 'auto' or 'manual'
        """
        response = self._send_command('04 38', query=True)

        if response and len(response) >= 1:
            if response[-1] == 0x02:
                return 'auto'
            elif response[-1] == 0x03:
                return 'manual'

        return 'unknown'

    # ==================== Presets ====================

    def save_preset(self, preset_num: int):
        """
        Save current position to preset.

        :param preset_num: Preset number 0-255
        """
        if not 0 <= preset_num <= 255:
            raise ValueError('Preset number must be 0-255')
        self._send_command(f'04 3F 01 {preset_num:02x}')

    def recall_preset(self, preset_num: int):
        """
        Recall saved preset.

        :param preset_num: Preset number 0-255
        """
        if not 0 <= preset_num <= 255:
            raise ValueError('Preset number must be 0-255')
        self._send_command(f'04 3F 02 {preset_num:02x}')

    # ==================== Power ====================

    def set_power(self, power_on: bool):
        """
        Turn camera power on or off.

        :param power_on: True to power on, False to standby
        """
        cmd = '04 00 02' if power_on else '04 00 03'
        self._send_command(cmd)

    def get_power_status(self) -> bool:
        """
        Get camera power status.

        :return: True if on, False if standby
        """
        response = self._send_command('04 00', query=True)

        if response and len(response) >= 1:
            return response[-1] == 0x02

        return False

    # ==================== Context Manager ====================

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()
        return False
