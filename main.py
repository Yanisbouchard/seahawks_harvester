import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import nmap
import socket
import psutil
from ping3 import ping
import json
from datetime import datetime

VERSION = "1.0.0"

class NetworkScanner(QThread):
    scan_complete = pyqtSignal(dict)
    
    def run(self):
        nm = nmap.PortScanner()
        # Scan le réseau local
        network = "192.168.1.0/24"  # À adapter selon le réseau
        nm.scan(hosts=network, arguments='-sn')
        
        results = {
            'hosts': [],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for host in nm.all_hosts():
            if nm[host].state() == 'up':
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except:
                    hostname = "Unknown"
                    
                results['hosts'].append({
                    'ip': host,
                    'hostname': hostname
                })
                
        self.scan_complete.emit(results)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seahawks Harvester")
        self.setMinimumSize(800, 600)
        
        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        
        # Informations système
        self.system_info = QLabel()
        self.update_system_info()
        layout.addWidget(self.system_info)
        
        # Bouton de scan
        scan_button = QPushButton("Lancer un scan réseau")
        scan_button.clicked.connect(self.start_network_scan)
        layout.addWidget(scan_button)
        
        # Zone de résultats
        self.results_area = QTextEdit()
        self.results_area.setReadOnly(True)
        layout.addWidget(self.results_area)
        
        main_widget.setLayout(layout)
        
        # Scanner
        self.scanner = NetworkScanner()
        self.scanner.scan_complete.connect(self.display_scan_results)
    
    def update_system_info(self):
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        info_text = f"""
        Informations système:
        - Nom de la machine: {hostname}
        - Adresse IP: {ip}
        - Version de l'application: {VERSION}
        """
        self.system_info.setText(info_text)
    
    def start_network_scan(self):
        self.results_area.append("Scan en cours...")
        self.scanner.start()
    
    def display_scan_results(self, results):
        self.results_area.clear()
        self.results_area.append(f"Scan effectué le: {results['timestamp']}\n")
        self.results_area.append(f"Machines détectées: {len(results['hosts'])}\n\n")
        
        for host in results['hosts']:
            self.results_area.append(f"IP: {host['ip']}")
            self.results_area.append(f"Hostname: {host['hostname']}\n")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
