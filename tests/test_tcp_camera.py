"""Tests for TcpCamera class."""

import pytest
from unittest.mock import patch, MagicMock

from visca_over_ip import TcpCamera


class TestTcpCameraInit:
    """Test TcpCamera initialization."""

    def test_init_default_timeout(self):
        cam = TcpCamera('192.168.1.100', 5678)
        assert cam._ip == '192.168.1.100'
        assert cam._port == 5678
        assert cam._timeout == 2.0
        assert cam._sock is None

    def test_init_custom_timeout(self):
        cam = TcpCamera('10.0.0.1', 1234, timeout=5.0)
        assert cam._timeout == 5.0


class TestTcpCameraConnection:
    """Test connection management."""

    @patch('socket.socket')
    def test_connect_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        result = cam.connect()

        assert result is True
        mock_sock.settimeout.assert_called_with(2.0)
        mock_sock.connect.assert_called_with(('192.168.1.100', 5678))

    @patch('socket.socket')
    def test_connect_failure(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)

        with pytest.raises(ConnectionError):
            cam.connect()

    @patch('socket.socket')
    def test_close_connection(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.close_connection()

        mock_sock.close.assert_called_once()
        assert cam._sock is None


class TestTcpCameraCommands:
    """Test VISCA command building and sending."""

    def _create_mock_socket(self, recv_value=b'\x90\x41\xff\x90\x51\xff'):
        """Create a properly configured mock socket."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [BlockingIOError(), recv_value]
        return mock_sock

    @patch('socket.socket')
    def test_pantilt_right(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.pantilt(pan_speed=5, tilt_speed=0)

        # Check command was sent: 81 01 06 01 05 00 02 03 FF
        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('81010601050002 03FF'.replace(' ', ''))

    @patch('socket.socket')
    def test_pantilt_left(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.pantilt(pan_speed=-5, tilt_speed=0)

        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('8101060105000103FF')

    @patch('socket.socket')
    def test_pantilt_stop(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.pantilt_stop()

        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('8101060100000303FF')

    @patch('socket.socket')
    def test_zoom_in(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.zoom(speed=3)

        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('8101040723FF')

    @patch('socket.socket')
    def test_zoom_out(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.zoom(speed=-3)

        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('8101040733FF')

    @patch('socket.socket')
    def test_pantilt_home(self, mock_socket_class):
        mock_sock = self._create_mock_socket()
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        cam.pantilt_home()

        call_args = mock_sock.send.call_args[0][0]
        assert call_args == bytes.fromhex('81010604FF')


class TestTcpCameraQueries:
    """Test VISCA inquiry commands."""

    def _create_mock_socket(self, recv_value):
        """Create a properly configured mock socket."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [BlockingIOError(), recv_value]
        return mock_sock

    @patch('socket.socket')
    def test_get_pantilt_position(self, mock_socket_class):
        # Response: 90 50 0p 0q 0r 0s 0t 0u 0v 0w FF
        # Pan = 0x0123 = 291, Tilt = 0xFE50 = -432 (two's complement)
        mock_sock = self._create_mock_socket(bytes.fromhex('9050000102030F0E0500FF'))
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        pan, tilt = cam.get_pantilt_position()

        assert pan == 0x0123  # 291
        assert tilt == -432  # 0xFE50 as signed

    @patch('socket.socket')
    def test_get_zoom_position(self, mock_socket_class):
        # Response: 90 50 0p 0q 0r 0s FF (4 nibble-padded bytes)
        # Zoom = 0x1234
        mock_sock = self._create_mock_socket(bytes.fromhex('905001020304FF'))
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        zoom = cam.get_zoom_position()

        assert zoom == 0x1234  # 4660

    @patch('socket.socket')
    def test_get_focus_mode_auto(self, mock_socket_class):
        mock_sock = self._create_mock_socket(bytes.fromhex('905002FF'))
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        mode = cam.get_focus_mode()

        assert mode == 'auto'

    @patch('socket.socket')
    def test_get_focus_mode_manual(self, mock_socket_class):
        mock_sock = self._create_mock_socket(bytes.fromhex('905003FF'))
        mock_socket_class.return_value = mock_sock

        cam = TcpCamera('192.168.1.100', 5678)
        cam.connect()
        mode = cam.get_focus_mode()

        assert mode == 'manual'


class TestTcpCameraValidation:
    """Test input validation."""

    def test_pantilt_speed_out_of_range(self):
        cam = TcpCamera('192.168.1.100', 5678)
        cam._sock = MagicMock()  # Fake connected

        with pytest.raises(ValueError):
            cam.pantilt(pan_speed=25, tilt_speed=0)

    def test_zoom_speed_out_of_range(self):
        cam = TcpCamera('192.168.1.100', 5678)
        cam._sock = MagicMock()

        with pytest.raises(ValueError):
            cam.zoom(speed=8)

    def test_preset_out_of_range(self):
        cam = TcpCamera('192.168.1.100', 5678)
        cam._sock = MagicMock()

        with pytest.raises(ValueError):
            cam.save_preset(256)

    def test_focus_invalid_mode(self):
        cam = TcpCamera('192.168.1.100', 5678)
        cam._sock = MagicMock()

        with pytest.raises(ValueError):
            cam.set_focus_mode('invalid')


class TestTcpCameraContextManager:
    """Test context manager support."""

    @patch('socket.socket')
    def test_context_manager(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = BlockingIOError()
        mock_socket_class.return_value = mock_sock

        with TcpCamera('192.168.1.100', 5678) as cam:
            assert cam._sock is not None

        mock_sock.close.assert_called()
