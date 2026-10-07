import concurrent.futures
import ipaddress
import os
import re
import socket
import subprocess
import time
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
    """Discover the active local IPv4 address and detected network CIDR (e.g. 10.10.0.0/22 or 192.168.1.0/24)."""
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to public DNS to find default outgoing network interface
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        return "127.0.0.1", "192.168.1.0/24"

    mask = "255.255.255.0"
    if os.name == "nt":
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            out = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=2,
                startupinfo=startupinfo,
                creationflags=creationflags
            ).stdout
            m = re.search(re.escape(local_ip) + r"[\s\S]*?Subnet Mask[ .:]+([0-9\.]+)", out)
            if m:
                mask = m.group(1).strip()
        except Exception:
            pass

    try:
        net = ipaddress.IPv4Network(f"{local_ip}/{mask}", strict=False)
        return local_ip, str(net)
    except Exception:
        parts = local_ip.split(".")
        return local_ip, f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


def resolve_scan_targets(subnet_input: Optional[str], default_ip: str, default_network: str) -> List[str]:
    """Parse user subnet input (CIDR, legacy dot-prefix, or plain IP) into a list of host IPs."""
    raw = (subnet_input or "").strip()
    if not raw:
        raw = default_network

    # 1. CIDR notation (e.g. 10.10.0.0/22 or 192.168.1.0/24)
    if "/" in raw:
        try:
            net = ipaddress.IPv4Network(raw, strict=False)
            if net.num_addresses > 2048:
                # Cap scanning at /21 (2048 IPs) to prevent unintentional massive sweeps
                subnets = list(net.subnets(new_prefix=22))
                return [str(h) for h in subnets[0].hosts()]
            return [str(h) for h in net.hosts()]
        except Exception:
            pass

    # 2. Legacy prefix with trailing dot (e.g. "192.168.1." or "10.10.1.")
    if raw.endswith("."):
        parts = [p for p in raw.split(".") if p]
        if len(parts) == 3:
            return [f"{raw}{i}" for i in range(1, 255)]
        elif len(parts) == 2:
            return [f"{parts[0]}.{parts[1]}.0.{i}" for i in range(1, 255)] + [f"{parts[0]}.{parts[1]}.1.{i}" for i in range(1, 255)]

    # 3. Direct IP or partial network without slash (e.g. 10.10.1.50 or 10.10.1.0)
    try:
        if "." in raw:
            parts = [p for p in raw.split(".") if p]
            if len(parts) == 4:
                if parts[3] == "0":
                    net = ipaddress.IPv4Network(f"{raw}/24", strict=False)
                    return [str(h) for h in net.hosts()]
                else:
                    ipaddress.IPv4Address(raw)
                    return [raw]
    except Exception:
        pass

    try:
        net = ipaddress.IPv4Network(default_network, strict=False)
        return [str(h) for h in net.hosts()]
    except Exception:
        return [f"192.168.1.{i}" for i in range(1, 255)]


_ACTIVE_SCAN_WORKERS: Set["NetworkScannerWorker"] = set()


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
        priority_endpoints: Optional[List[str]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.adb = adb
        self.subnet_prefix = subnet_prefix
        # Default to standard ADB port 5555 to prevent 4x traffic explosion on enterprise networks
        self.scan_ports = scan_ports or [5555]
        self.priority_endpoints = priority_endpoints or []
        self._running = True
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

    def start_scanning(self):
        """Start thread safely and register in global reference set to prevent premature destruction."""
        _ACTIVE_SCAN_WORKERS.add(self)
        self.finished.connect(lambda: _ACTIVE_SCAN_WORKERS.discard(self))
        self.start()

    def run(self):
        discovered: List[DiscoveredWirelessDevice] = []
        already_connected_serials: Set[str] = set()

        if not self._running:
            return

        try:
            connected = self.adb.list_devices()
            for d in connected:
                already_connected_serials.add(d.serial)
        except Exception:
            pass

        if not self._running:
            return

        found_endpoints: Set[str] = set()

        # 0. Immediate Priority Probe (Pinned & Recent Devices)
        # Check known devices with a higher timeout & retries to wake phone Wi-Fi chips (DTIM) and resolve ARP
        if self.priority_endpoints:
            for ep_str in self.priority_endpoints:
                if not self._running:
                    return
                try:
                    if ":" in ep_str:
                        p_ip, p_port_str = ep_str.split(":", 1)
                        p_port = int(p_port_str)
                    else:
                        p_ip = ep_str
                        p_port = 5555

                    res = self._check_socket(p_ip, p_port, timeout=0.6, retries=2)
                    if res and self._running:
                        found_ip, found_port = res
                        found_ep = f"{found_ip}:{found_port}"
                        if found_ep not in found_endpoints:
                            found_endpoints.add(found_ep)
                            dev = DiscoveredWirelessDevice(
                                ip=found_ip,
                                port=found_port,
                                hostname="",
                                is_already_connected=(found_ep in already_connected_serials)
                            )
                            discovered.append(dev)
                            self.device_found.emit(dev)
                except Exception:
                    pass

        if not self._running:
            return

        # 1. Check ADB mDNS discovery (Android 11+ Wireless Debugging)
        mdns_devices = self._scan_mdns()
        for dev in mdns_devices:
            if not self._running:
                return
            if dev.endpoint not in found_endpoints:
                found_endpoints.add(dev.endpoint)
                dev.is_already_connected = (dev.endpoint in already_connected_serials)
                discovered.append(dev)
                self.device_found.emit(dev)

        if not self._running:
            return

        # 2. Subnet port sweep (Support CIDR ranges like /22, /24, and custom subnets)
        local_ip, def_network = get_local_ip_and_subnet()
        host_ips = resolve_scan_targets(self.subnet_prefix, local_ip, def_network)

        # Build list of (ip, port) targets, excluding already discovered priority endpoints
        targets: List[Tuple[str, int]] = []

        for ip in host_ips:
            for p in self.scan_ports:
                ep = f"{ip}:{p}"
                if ep not in found_endpoints:
                    targets.append((ip, p))

        total = len(targets)
        completed = 0

        # Scan targets in parallel with paced worker pool to avoid triggering enterprise AP SYN-flood filters
        workers = min(75, max(30, len(targets) // 4)) if targets else 30
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        try:
            future_to_target = {
                self._executor.submit(self._check_socket, ip, port, 0.5, 1): (ip, port)
                for (ip, port) in targets
            }

            for future in concurrent.futures.as_completed(future_to_target):
                if not self._running:
                    break
                completed += 1
                if completed % 10 == 0 or completed == total:
                    if self._running:
                        self.progress.emit(completed, total)

                try:
                    res = future.result()
                except Exception:
                    res = None

                if res and self._running:
                    ip, port = res
                    ep = f"{ip}:{port}"
                    if ep not in found_endpoints:
                        found_endpoints.add(ep)
                        dev = DiscoveredWirelessDevice(
                            ip=ip,
                            port=port,
                            hostname="",
                            is_already_connected=(ep in already_connected_serials)
                        )
                        discovered.append(dev)
                        if self._running:
                            self.device_found.emit(dev)
        finally:
            if self._executor:
                try:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
                self._executor = None

        if self._running:
            self.scan_finished.emit(discovered)

    def _check_socket(self, ip: str, port: int, timeout: float = 0.5, retries: int = 1) -> Optional[Tuple[str, int]]:
        """Probe TCP socket with adaptive timeout and retry for Wi-Fi DTIM sleep and ARP discovery."""
        if not self._running:
            return None
        for attempt in range(retries + 1):
            if not self._running:
                return None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return ip, port
            except Exception:
                pass
            if attempt < retries and self._running:
                time.sleep(0.04)
        return None

    def _scan_mdns(self) -> List[DiscoveredWirelessDevice]:
        """Query adb mdns services for Android 11+ wireless debugging services."""
        devices = []
        try:
            code, out, _ = self.adb._run_cmd(["mdns", "services"], timeout=3)
            if code == 0 and out:
                for line in out.splitlines():
                    if not self._running:
                        break
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
                                hostname=""
                            ))
        except Exception:
            pass
        return devices

    def stop(self):
        self._running = False
        if self._executor:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._executor = None
        self.quit()
