import sys
import re
import serial
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QLabel
)

from PyQt5.QtCore import QTimer


PORT = "COM9"
BAUD = 115200


class SnifferWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.packet_count = 0
        self.nodes = {}

        self.rssi_history = []
        self.noise_history = []

        self.setWindowTitle("Mesh RF Survey Tool")
        self.resize(1700, 1000)

        main_layout = QHBoxLayout()

        # =====================================
        # LEFT SIDE
        # =====================================

        left_layout = QVBoxLayout()

        # =====================================
        # FILTERS
        # =====================================

        filter_layout = QHBoxLayout()

        self.msg_filter = QCheckBox("MSG")
        self.grp_filter = QCheckBox("GRP")
        self.adv_filter = QCheckBox("ADV")
        self.path_filter = QCheckBox("PATH")
        self.ack_filter = QCheckBox("ACK")
        self.req_filter = QCheckBox("REQ")

        filters = [
            self.msg_filter,
            self.grp_filter,
            self.adv_filter,
            self.path_filter,
            self.ack_filter,
            self.req_filter
        ]

        for f in filters:

            f.setChecked(True)

            f.setStyleSheet("""
                color: #FFFFFF;
                background-color: #111111;
                font-size: 12pt;
                padding: 4px;
            """)

            filter_layout.addWidget(f)

        left_layout.addLayout(filter_layout)

        # =====================================
        # RSSI GRAPH
        # =====================================

        left_layout.addWidget(
            QLabel("RSSI")
        )

        self.rssi_graph = pg.PlotWidget()

        self.rssi_graph.setBackground("#111111")

        self.rssi_graph.showGrid(x=True, y=True)

        self.rssi_graph.setLabel(
            "left",
            "RSSI"
        )

        self.rssi_graph.setLabel(
            "bottom",
            "Packets"
        )

        self.rssi_curve = self.rssi_graph.plot(
            pen="#00FF66"
        )

        left_layout.addWidget(
            self.rssi_graph,
            1
        )

        # =====================================
        # NOISE FLOOR GRAPH
        # =====================================

        left_layout.addWidget(
            QLabel("Noise Floor")
        )

        self.noise_graph = pg.PlotWidget()

        self.noise_graph.setBackground("#111111")

        self.noise_graph.showGrid(x=True, y=True)

        self.noise_graph.setLabel(
            "left",
            "Noise"
        )

        self.noise_graph.setLabel(
            "bottom",
            "Samples"
        )

        self.noise_curve = self.noise_graph.plot(
            pen="#FFAA00"
        )

        left_layout.addWidget(
            self.noise_graph,
            1
        )

        # =====================================
        # CONSOLE
        # =====================================

        self.console = QTextEdit()

        self.console.setReadOnly(True)

        self.console.setLineWrapMode(
            QTextEdit.NoWrap
        )

        self.console.setStyleSheet("""
            background-color: #0D0D0D;
            color: #FFFFFF;
            font-family: Consolas;
            font-size: 13pt;
            border: 1px solid #333333;
        """)

        left_layout.addWidget(
            self.console,
            3
        )

        # =====================================
        # NODE TABLE
        # =====================================

        self.node_table = QTableWidget()

        self.node_table.setColumnCount(4)

        self.node_table.setHorizontalHeaderLabels([
            "Node",
            "Last Seen",
            "RSSI",
            "Packets"
        ])

        self.node_table.horizontalHeader().setStretchLastSection(True)

        self.node_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.node_table.setStyleSheet("""
            QTableWidget {
                background-color: #111111;
                color: #FFFFFF;
                gridline-color: #333333;
                font-family: Consolas;
                font-size: 11pt;
                border: 1px solid #333333;
            }

            QHeaderView::section {
                background-color: #222222;
                color: #00FFAA;
                padding: 6px;
                border: 1px solid #333333;
                font-weight: bold;
            }
        """)

        # =====================================
        # MAIN LAYOUT
        # =====================================

        main_layout.addLayout(left_layout, 5)
        main_layout.addWidget(self.node_table, 2)

        self.setLayout(main_layout)

        # =====================================
        # SERIAL
        # =====================================

        self.ser = serial.Serial(PORT, BAUD)

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.read_serial
        )

        self.timer.start(10)

    # =====================================
    # FILTERS
    # =====================================

    def packet_allowed(self, packet_type):

        if packet_type == "MSG":
            return self.msg_filter.isChecked()

        elif packet_type == "GRP_MSG":
            return self.grp_filter.isChecked()

        elif packet_type == "ADV":
            return self.adv_filter.isChecked()

        elif packet_type == "PATH":
            return self.path_filter.isChecked()

        elif packet_type == "ACK":
            return self.ack_filter.isChecked()

        elif packet_type == "REQ":
            return self.req_filter.isChecked()

        return True

    # =====================================
    # SERIAL READER
    # =====================================

    def read_serial(self):

        while self.ser.in_waiting:

            try:

                line = self.ser.readline().decode(
                    errors="ignore"
                ).strip()

                if not line:
                    continue

                # =================================
                # NOISE FLOOR
                # =================================

                if "noise_floor" in line:

                    noise_match = re.search(
                        r"noise_floor = (-?\d+)",
                        line
                    )

                    if noise_match:

                        noise = int(
                            noise_match.group(1)
                        )

                        self.noise_history.append(
                            noise
                        )

                        if len(self.noise_history) > 100:
                            self.noise_history.pop(0)

                        self.noise_curve.setData(
                            self.noise_history
                        )

                    continue

                # =================================
                # HIDE NOISE
                # =================================

                if "DEBUG:" in line:
                    continue

                if "RAW:" in line:
                    continue

                if "TX BLOCKED" in line:
                    continue

                if "RX," in line:

                    type_match = re.search(
                        r"type=(\d+)",
                        line
                    )

                    rssi_match = re.search(
                        r"RSSI=(-?\d+)",
                        line
                    )

                    snr_match = re.search(
                        r"SNR=(-?\d+)",
                        line
                    )

                    length_match = re.search(
                        r"len=(\d+)",
                        line
                    )

                    packet_type = "UNKNOWN"

                    if type_match:

                        t = type_match.group(1)

                        if t == "0":
                            packet_type = "REQ"

                        elif t == "1":
                            packet_type = "RESP"

                        elif t == "2":
                            packet_type = "MSG"

                        elif t == "3":
                            packet_type = "ACK"

                        elif t == "4":
                            packet_type = "ADV"

                        elif t == "5":
                            packet_type = "GRP_MSG"

                        elif t == "8":
                            packet_type = "PATH"

                    if not self.packet_allowed(packet_type):
                        continue

                    self.console.append(
                        '<span style="color:#444444">'
                        + "─" * 90 +
                        "</span>"
                    )

                    self.packet_count += 1

                    self.setWindowTitle(
                        f"Mesh RF Survey Tool - Packets: {self.packet_count}"
                    )

                    rssi = "?"
                    snr = "?"
                    length = "?"

                    if rssi_match:
                        rssi = rssi_match.group(1)

                    if snr_match:
                        snr = snr_match.group(1)

                    if length_match:
                        length = length_match.group(1)

                    # =================================
                    # RSSI GRAPH
                    # =================================

                    try:

                        self.rssi_history.append(
                            int(rssi)
                        )

                        if len(self.rssi_history) > 100:
                            self.rssi_history.pop(0)

                        self.rssi_curve.setData(
                            self.rssi_history
                        )

                    except:
                        pass

                    # =================================
                    # RF QUALITY ANALYSIS
                    # =================================

                    quality = "UNKNOWN"

                    try:

                        rssi_val = int(rssi)
                        snr_val = int(snr)

                        noise_floor = -100

                        if len(self.noise_history) > 0:
                            noise_floor = self.noise_history[-1]

                        signal_margin = (
                            rssi_val - noise_floor
                        )

                        score = 0

                        score += signal_margin * 2
                        score += snr_val * 3
                        score += (100 + abs(noise_floor))

                        if score > 180:
                            quality = "EXCELLENT"

                        elif score > 130:
                            quality = "GOOD"

                        elif score > 80:
                            quality = "MEDIUM"

                        else:
                            quality = "BAD"

                    except:

                        signal_margin = 0
                        quality = "UNKNOWN"
                        noise_floor = -100

                    # =================================
                    # COLORS
                    # =================================

                    color = "#FFFFFF"

                    if quality == "EXCELLENT":
                        color = "#00FF66"

                    elif quality == "GOOD":
                        color = "#AAFF00"

                    elif quality == "MEDIUM":
                        color = "#FFD700"

                    elif quality == "BAD":
                        color = "#FF4444"

                    summary = (
                        f"[{packet_type}]  "
                        f"RSSI:{rssi}  "
                        f"SNR:{snr}  "
                        f"NOISE:{noise_floor}  "
                        f"MARGIN:{signal_margin}  "
                        f"LEN:{length}  "
                        f"{quality}"
                    )

                    self.console.append(
                        f'<span style="color:{color};">'
                        f'{summary}'
                        '</span>'
                    )

            except Exception as e:

                self.console.append(
                    f'<span style="color:red">{str(e)}</span>'
                )


app = QApplication(sys.argv)

window = SnifferWindow()

window.show()

sys.exit(app.exec_())