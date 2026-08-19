import concurrent.futures
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Callable, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, QThread, Signal

from core.adb_manager import AdbManager


@dataclass
class DiscoveredWirelessDevice:
    ip: str
    port: int
    hostname: str = ""
    service_name: str = ""
    is_already_connected: bool = False

    @property
    def endpoint(self) -> str:
        return f"{self.ip}:{self.port}"


def get_local_ip_and_subnet() -> Tuple[str, str]:
    """Discover the active local IPv4 address and default /24 subnet prefix."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to public DNS to find default outgoing network interface
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        subnet_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
        return local_ip, subnet_prefix
    except Exception:
        return "127.0.0.1", "192.168.1."


class NetworkScannerWorker(QThread):
    """Multi-threaded asynchronous network scanner for wireless ADB endpoints."""

    device_found = Signal(object)  # DiscoveredWirelessDevice
    progress = Signal(int, int)  # current, total
    scan_finished = Signal(list)  # List[DiscoveredWirelessDevice]

    def __init__(
        self,
        adb: AdbManager,
        subnet_prefix: Optional[str] = None,
        scan_ports: Optional[List[int]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.adb = adb
        self.subnet_prefix = subnet_prefix
        self.scan_ports = scan_ports or [5555, 5556, 5557, 5558]
        self._running = True

    def run(self):
        discovered: List[DiscoveredWirelessDevice] = []
        already_connected_serials: Set[str] = set()

        try:
            connected = self.adb.list_devices()
            for d in connected:
                already_connected_serials.add(d.serial)
        except Exception:
            pass

        # 1. First, check ADB mDNS discovery (Android 11+ Wireless Debugging)
        mdns_devices = self._scan_mdns()
        for dev in mdns_devices:
            dev.is_already_connected = (dev.endpoint in already_connected_serials)
            discovered.append(dev)
            self.device_found.emit(dev)

        # 2. Subnet port sweep (Port 5555 & common ports across all 254 subnet hosts)
        if not self.subnet_prefix:
            _, self.subnet_prefix = get_local_ip_and_subnet()

        # Build list of (ip, port) targets
        targets: List[Tuple[str, int]] = []
        found_endpoints = {d.endpoint for d in discovered}

        for i in range(1, 255):
            ip = f"{self.subnet_prefix}{i}"
            for p in self.scan_ports:
                ep = f"{ip}:{p}"
                if ep not in found_endpoints:
                    targets.append((ip, p))

        total = len(targets)
        completed = 0

        # Scan targets in parallel using 80 threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
            future_to_target = {
                executor.submit(self._check_socket, ip, port): (ip, port)
                for (ip, port) in targets
            }

            for future in concurrent.futures.as_completed(future_to_target):
                if not self._running:
                    break
                completed += 1
                if completed % 10 == 0 or completed == total:
                    self.progress.emit(completed, total)

                res = future.result()
                if res:
                    ip, port = res
                    ep = f"{ip}:{port}"
                    if ep not in found_endpoints:
                        found_endpoints.add(ep)
                        hostname = self._get_hostname(ip)
                        dev = DiscoveredWirelessDevice(
                            ip=ip,
                            port=port,
                            hostname=hostname,
                            is_already_connected=(ep in already_connected_serials)
                        )
                        discovered.append(dev)
                        self.device_found.emit(dev)

        self.scan_finished.emit(discovered)

    def _check_socket(self, ip: str, port: int, timeout: float = 0.35) -> Optional[Tuple[str, int]]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return ip, port
        except Exception:
            pass
        return None

    def _scan_mdns(self) -> List[DiscoveredWirelessDevice]:
        """Query adb mdns services for Android 11+ wireless debugging services."""
        devices = []
        try:
            code, out, _ = self.adb._run_cmd(["mdns", "services"], timeout=5)
            if code == 0 and out:
                # Output format: <service_name> <service_type> <ip:port>
                for line in out.splitlines():
                    line = line.strip()
                    if not line or "List of discovered" in line:
                        continue
                    parts = line.split()
                    for token in parts:
                        match = re.match(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)$", token)
                        if match:
                            ip = match.group(1)
                            port = int(match.group(2))
                            name = parts[0] if parts else "mDNS Android Device"
                            devices.append(DiscoveredWirelessDevice(
                                ip=ip,
                                port=port,
                                service_name=name,
                                hostname=self._get_hostname(ip)
                            ))
        except Exception:
            pass
        return devices

    def _get_hostname(self, ip: str) -> str:
        try:
            return socket.gethostbyaddr(ip)[0]
        except Exception:
            return ""

    def stop(self):
        self._running = False
        self.wait(1000)
