from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import AdbManager
from core.config_manager import ConfigManager
from core.network_scanner import (
    DiscoveredWirelessDevice,
    NetworkScannerWorker,
    get_local_ip_and_subnet,
)


class WirelessDialog(QDialog):
    """Full-featured Wireless ADB Manager with automatic Network Scanner, IP connect, and pairing."""

    connection_successful = Signal(str)  # ip_port

    def __init__(self, adb: AdbManager, config: ConfigManager, selected_serial: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.config = config
        self.selected_serial = selected_serial
        self.scanner_worker: Optional[NetworkScannerWorker] = None
        self.discovered_devices: List[DiscoveredWirelessDevice] = []

        self.setWindowTitle("📶 Wireless ADB & Network Device Discovery")
        self.resize(580, 480)
        self.setMinimumSize(520, 420)
        self.setModal(True)
        self._setup_ui()
        # Automatically trigger a scan on open
        self._start_network_scan()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.tabs = QTabWidget()

        # ==========================================
        # --- TAB 1: 🔍 NETWORK AUTO-SCANNER ---
        # ==========================================
        tab_scanner = QWidget()
        l_scan = QVBoxLayout(tab_scanner)
        l_scan.setContentsMargins(10, 10, 10, 10)
        l_scan.setSpacing(10)

        # Header controls
        ctrl_box = QHBoxLayout()
        ctrl_box.setSpacing(8)

        local_ip, def_subnet = get_local_ip_and_subnet()
        self.edit_subnet = QLineEdit(def_subnet)
        self.edit_subnet.setPlaceholderText("192.168.1.")
        self.edit_subnet.setFixedWidth(120)
        self.edit_subnet.setToolTip("Subnet prefix to scan (e.g. 192.168.1.)")

        lbl_sub = QLabel("Subnet:")
        lbl_sub.setStyleSheet("color: #94A3B8; font-weight: 500;")
        ctrl_box.addWidget(lbl_sub)
        ctrl_box.addWidget(self.edit_subnet)

        lbl_pc_ip = QLabel(f"(PC: {local_ip})")
        lbl_pc_ip.setStyleSheet("color: #64748B; font-size: 11px;")
        ctrl_box.addWidget(lbl_pc_ip)

        ctrl_box.addStretch(1)

        self.btn_scan = QPushButton("🔍 Scan Network")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self._start_network_scan)
        ctrl_box.addWidget(self.btn_scan)

        l_scan.addLayout(ctrl_box)

        # Progress bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1A1D26; border: 1px solid #2B303E; border-radius: 7px; text-align: center; color: #FFFFFF; font-size: 10px; font-weight: bold; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8); border-radius: 6px; }"
        )
        l_scan.addWidget(self.progress_bar)

        self.lbl_scan_status = QLabel("Ready to scan local network for wireless devices.")
        self.lbl_scan_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
        l_scan.addWidget(self.lbl_scan_status)

        # Discovered Devices Table
        self.table_devs = QTableWidget()
        self.table_devs.setColumnCount(4)
        self.table_devs.setHorizontalHeaderLabels(["Endpoint", "Host / Device", "Status", "Action"])
        self.table_devs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_devs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_devs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_devs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_devs.verticalHeader().setVisible(False)
        self.table_devs.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_devs.setStyleSheet("""
            QTableWidget {
                background-color: #0E1015;
                border: 1px solid #232732;
                border-radius: 6px;
                gridline-color: #1F222B;
            }
            QHeaderView::section {
                background-color: #181A22;
                color: #94A3B8;
                border: none;
                padding: 6px;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        l_scan.addWidget(self.table_devs, 1)

        self.tabs.addTab(tab_scanner, "🔍 Network Scanner")

        # ==========================================
        # --- TAB 2: 🌐 MANUAL IP CONNECT ---
        # ==========================================
        tab_connect = QWidget()
        l_conn = QVBoxLayout(tab_connect)
        l_conn.setContentsMargins(10, 10, 10, 10)
        l_conn.setSpacing(10)

        info_lbl = QLabel("Connect directly to an Android IP and Port already listening on TCP/IP.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_conn.addWidget(info_lbl)

        form_c = QFormLayout()
        form_c.setSpacing(10)

        self.combo_recent = QComboBox()
        self.combo_recent.setEditable(True)
        recent_ips = self.config.get("recent_wireless_ips", [])
        if recent_ips:
            self.combo_recent.addItems(recent_ips)
        self.combo_recent.setPlaceholderText("192.168.1.100:5555")
        form_c.addRow("IP : Port:", self.combo_recent)

        l_conn.addLayout(form_c)

        self.lbl_conn_status = QLabel("")
        self.lbl_conn_status.setStyleSheet("font-weight: 500; font-size: 11px;")
        l_conn.addWidget(self.lbl_conn_status)

        l_conn.addStretch(1)

        btn_row_c = QHBoxLayout()
        self.btn_connect = QPushButton("⚡ Connect")
        self.btn_connect.setObjectName("primaryBtn")
        self.btn_connect.clicked.connect(self._do_connect)
        btn_row_c.addWidget(self.btn_connect, 1)

        self.btn_disconnect = QPushButton("🔌 Disconnect")
        self.btn_disconnect.clicked.connect(self._do_disconnect)
        btn_row_c.addWidget(self.btn_disconnect)

        l_conn.addLayout(btn_row_c)
        self.tabs.addTab(tab_connect, "🌐 Manual Connect")

        # ==========================================
        # --- TAB 3: 🔌 USB TO WIRELESS ---
        # ==========================================
        tab_switch = QWidget()
        l_switch = QVBoxLayout(tab_switch)
        l_switch.setContentsMargins(10, 10, 10, 10)
        l_switch.setSpacing(10)

        desc_s = QLabel(
            "1. Connect phone via USB cable\n"
            "2. Ensure phone & PC are on the same Wi-Fi network\n"
            "3. Click 'Enable TCP/IP Mode' below to switch to wireless"
        )
        desc_s.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_switch.addWidget(desc_s)

        form_s = QFormLayout()
        self.edit_tcp_port = QLineEdit("5555")
        form_s.addRow("TCP Port:", self.edit_tcp_port)
        l_switch.addLayout(form_s)

        self.lbl_switch_status = QLabel("")
        self.lbl_switch_status.setStyleSheet("font-weight: 500; font-size: 11px;")
        l_switch.addWidget(self.lbl_switch_status)

        l_switch.addStretch(1)

        self.btn_enable_tcp = QPushButton("🔄 Enable TCP/IP & Auto-Connect")
        self.btn_enable_tcp.setObjectName("primaryBtn")
        self.btn_enable_tcp.clicked.connect(self._do_enable_tcp)
        l_switch.addWidget(self.btn_enable_tcp)

        self.tabs.addTab(tab_switch, "🔌 USB to Wireless")

        # ==========================================
        # --- TAB 4: 🔢 ANDROID 11+ PAIRING ---
        # ==========================================
        tab_pair = QWidget()
        l_pair = QVBoxLayout(tab_pair)
        l_pair.setContentsMargins(10, 10, 10, 10)
        l_pair.setSpacing(10)

        desc_p = QLabel(
            "On Phone: Settings → Developer options → Wireless debugging → 'Pair device with pairing code'"
        )
        desc_p.setWordWrap(True)
        desc_p.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l_pair.addWidget(desc_p)

        form_p = QFormLayout()
        form_p.setSpacing(8)

        self.edit_pair_ip_port = QLineEdit()
        self.edit_pair_ip_port.setPlaceholderText("192.168.1.100:37891")
        form_p.addRow("Pairing IP:Port:", self.edit_pair_ip_port)

        self.edit_pair_code = QLineEdit()
        self.edit_pair_code.setPlaceholderText("6-digit code (e.g. 123456)")
        form_p.addRow("Pairing Code:", self.edit_pair_code)

        l_pair.addLayout(form_p)

        self.lbl_pair_status = QLabel("")
        self.lbl_pair_status.setStyleSheet("font-weight: 500; font-size: 11px;")
        l_pair.addWidget(self.lbl_pair_status)

        l_pair.addStretch(1)

        self.btn_pair = QPushButton("🔗 Pair Device")
        self.btn_pair.setObjectName("primaryBtn")
        self.btn_pair.clicked.connect(self._do_pair)
        l_pair.addWidget(self.btn_pair)

        self.tabs.addTab(tab_pair, "🔢 Wireless Pairing (A11+)")

        layout.addWidget(self.tabs)

        # Bottom Close Button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)

    def _start_network_scan(self):
        if self.scanner_worker and self.scanner_worker.isRunning():
            return

        subnet = self.edit_subnet.text().strip()
        if not subnet.endswith("."):
            subnet += "."

        self.discovered_devices.clear()
        self.table_devs.setRowCount(0)

        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("⏳ Scanning...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_scan_status.setText(f"Scanning subnet {subnet}0/24 on port 5555 and mDNS...")
        self.lbl_scan_status.setStyleSheet("color: #38BDF8;")

        self.scanner_worker = NetworkScannerWorker(self.adb, subnet_prefix=subnet, parent=None)
        self.scanner_worker.device_found.connect(self._on_device_discovered)
        self.scanner_worker.progress.connect(self._on_scan_progress)
        self.scanner_worker.scan_finished.connect(self._on_scan_finished)
        self.scanner_worker.start_scanning()

    def _on_scan_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        if total > 0:
            pct = int((current / total) * 100)
            self.btn_scan.setText(f"⏳ Scanning ({pct}%)...")

    def _on_device_discovered(self, dev: DiscoveredWirelessDevice):
        row = self.table_devs.rowCount()
        self.table_devs.insertRow(row)

        # Endpoint
        item_ep = QTableWidgetItem(f"📶 {dev.endpoint}")
        item_ep.setForeground(Qt.white)
        self.table_devs.setItem(row, 0, item_ep)

        # Hostname / Service
        info_str = dev.service_name or dev.hostname or "Android Wireless Device"
        item_info = QTableWidgetItem(info_str)
        item_info.setForeground(Qt.lightGray)
        self.table_devs.setItem(row, 1, item_info)

        # Status
        status_str = "🟢 Connected" if dev.is_already_connected else "🔵 Open Port"
        item_status = QTableWidgetItem(status_str)
        self.table_devs.setItem(row, 2, item_status)

        # Action Button (Disconnect if already connected, else Connect)
        if dev.is_already_connected:
            btn_action = QPushButton("🔌 Disconnect")
            btn_action.setFixedHeight(26)
            btn_action.setStyleSheet("font-size: 11px; padding: 4px 8px; color: #EF4444;")
            btn_action.clicked.connect(lambda _, ep=dev.endpoint: self._disconnect_from_endpoint(ep))
        else:
            btn_action = QPushButton("⚡ Connect")
            btn_action.setFixedHeight(26)
            btn_action.setObjectName("primaryBtn")
            btn_action.clicked.connect(lambda _, ep=dev.endpoint: self._connect_to_endpoint(ep))

        self.table_devs.setCellWidget(row, 3, btn_action)

    def _on_scan_finished(self, discovered_list: List[DiscoveredWirelessDevice]):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍 Scan Network")
        self.progress_bar.setVisible(False)

        count = len(discovered_list)
        if count == 0:
            self.lbl_scan_status.setText(
                "Scan complete. No open wireless ADB endpoints found on this subnet.\n"
                "Tip: Enable Wireless Debugging in Developer Options on your phone."
            )
            self.lbl_scan_status.setStyleSheet("color: #F59E0B;")
        else:
            self.lbl_scan_status.setText(f"Scan complete! Found {count} wireless device(s).")
            self.lbl_scan_status.setStyleSheet("color: #10B981;")

    def _connect_to_endpoint(self, endpoint: str):
        self.lbl_scan_status.setText(f"Connecting to {endpoint}...")
        self.lbl_scan_status.setStyleSheet("color: #38BDF8;")
        self.repaint()

        ok, msg = self.adb.connect_wireless(endpoint)
        if ok:
            self.lbl_scan_status.setText(f"Successfully connected to {endpoint}!")
            self.lbl_scan_status.setStyleSheet("color: #10B981;")
            self.config.add_recent_ip(endpoint)
            self.connection_successful.emit(endpoint)
            self._mark_endpoint_connected(endpoint, True)
        else:
            self.lbl_scan_status.setText(f"Failed to connect to {endpoint}: {msg}")
            self.lbl_scan_status.setStyleSheet("color: #EF4444;")

    def _disconnect_from_endpoint(self, endpoint: str):
        self.lbl_scan_status.setText(f"Disconnecting from {endpoint}...")
        self.lbl_scan_status.setStyleSheet("color: #38BDF8;")
        self.repaint()

        ok, msg = self.adb.disconnect_wireless(endpoint)
        self.lbl_scan_status.setText(f"Disconnected {endpoint}")
        self.lbl_scan_status.setStyleSheet("color: #94A3B8;")
        self.connection_successful.emit(endpoint)
        self._mark_endpoint_connected(endpoint, False)

    def _mark_endpoint_connected(self, endpoint: str, connected: bool):
        """Update status item and action button in-place without re-scanning."""
        for row in range(self.table_devs.rowCount()):
            item_ep = self.table_devs.item(row, 0)
            if item_ep and endpoint in item_ep.text():
                # Status Column (2)
                item_status = QTableWidgetItem("🟢 Connected" if connected else "🔵 Open Port")
                self.table_devs.setItem(row, 2, item_status)

                # Action Column (3)
                if connected:
                    btn = QPushButton("🔌 Disconnect")
                    btn.setFixedHeight(26)
                    btn.setStyleSheet("font-size: 11px; padding: 4px 8px; color: #EF4444;")
                    btn.clicked.connect(lambda _, ep=endpoint: self._disconnect_from_endpoint(ep))
                else:
                    btn = QPushButton("⚡ Connect")
                    btn.setFixedHeight(26)
                    btn.setObjectName("primaryBtn")
                    btn.clicked.connect(lambda _, ep=endpoint: self._connect_to_endpoint(ep))

                self.table_devs.setCellWidget(row, 3, btn)
                break

    def _do_connect(self):
        target = self.combo_recent.currentText().strip()
        if not target:
            self.lbl_conn_status.setText("Please enter an IP:Port")
            return

        if ":" not in target:
            target += ":5555"

        self.lbl_conn_status.setText("Connecting...")
        self.lbl_conn_status.setStyleSheet("color: #38BDF8;")
        self.repaint()

        ok, msg = self.adb.connect_wireless(target)
        if ok:
            self.lbl_conn_status.setText(f"Connected: {msg}")
            self.lbl_conn_status.setStyleSheet("color: #10B981;")
            self.config.add_recent_ip(target)
            self.connection_successful.emit(target)
        else:
            self.lbl_conn_status.setText(f"Failed: {msg}")
            self.lbl_conn_status.setStyleSheet("color: #EF4444;")

    def _do_disconnect(self):
        target = self.combo_recent.currentText().strip()
        ok, msg = self.adb.disconnect_wireless(target)
        self.lbl_conn_status.setText(f"Disconnected: {msg}")
        self.lbl_conn_status.setStyleSheet("color: #94A3B8;")

    def _do_enable_tcp(self):
        if not self.selected_serial:
            self.lbl_switch_status.setText("No USB device selected.")
            self.lbl_switch_status.setStyleSheet("color: #EF4444;")
            return

        port = self.edit_tcp_port.text().strip() or "5555"
        self.lbl_switch_status.setText(f"Enabling TCP/IP on port {port}...")
        self.lbl_switch_status.setStyleSheet("color: #38BDF8;")
        self.repaint()

        ok, msg = self.adb.enable_tcpip(self.selected_serial, int(port))
        if not ok:
            self.lbl_switch_status.setText(f"TCP/IP mode error: {msg}")
            self.lbl_switch_status.setStyleSheet("color: #EF4444;")
            return

        ip = self.adb.get_device_ip(self.selected_serial)
        if ip:
            target = f"{ip}:{port}"
            self.lbl_switch_status.setText(f"Discovered IP {ip}. Connecting to {target}...")
            c_ok, c_msg = self.adb.connect_wireless(target)
            if c_ok:
                self.lbl_switch_status.setText(f"Successfully switched to wireless: {target}")
                self.lbl_switch_status.setStyleSheet("color: #10B981;")
                self.config.add_recent_ip(target)
                self.connection_successful.emit(target)
            else:
                self.lbl_switch_status.setText(f"TCP/IP enabled, connect manually: {target}")
                self.combo_recent.setCurrentText(target)
        else:
            self.lbl_switch_status.setText(f"TCP/IP enabled on port {port}. Please enter device IP on 'Connect' tab.")
            self.lbl_switch_status.setStyleSheet("color: #F59E0B;")

    def _do_pair(self):
        ip_port = self.edit_pair_ip_port.text().strip()
        code = self.edit_pair_code.text().strip()

        if not ip_port or not code:
            self.lbl_pair_status.setText("Enter both Pairing IP:Port and Pairing Code.")
            self.lbl_pair_status.setStyleSheet("color: #EF4444;")
            return

        self.lbl_pair_status.setText("Pairing device...")
        self.lbl_pair_status.setStyleSheet("color: #38BDF8;")
        self.repaint()

        ok, msg = self.adb.pair_wireless(ip_port, code)
        if ok:
            self.lbl_pair_status.setText("Device paired successfully! Now connect via Connect tab.")
            self.lbl_pair_status.setStyleSheet("color: #10B981;")
        else:
            self.lbl_pair_status.setText(f"Pairing failed: {msg}")
            self.lbl_pair_status.setStyleSheet("color: #EF4444;")

    def _cleanup_worker(self):
        worker = self.scanner_worker
        self.scanner_worker = None
        if worker:
            try:
                worker.device_found.disconnect()
            except Exception:
                pass
            try:
                worker.progress.disconnect()
            except Exception:
                pass
            try:
                worker.scan_finished.disconnect()
            except Exception:
                pass
            if worker.isRunning():
                worker.stop()

    def reject(self):
        self._cleanup_worker()
        super().reject()

    def accept(self):
        self._cleanup_worker()
        super().accept()

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)
