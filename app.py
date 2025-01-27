from flask import Flask, render_template, jsonify, send_file, request
from flask_socketio import SocketIO
import nmap
import socket
import psutil
from ping3 import ping
from datetime import datetime
import threading
import time
import os
import base64
from mss import mss
from io import BytesIO
from dicttoxml import dicttoxml
from xml.dom.minidom import parseString
import xml.etree.ElementTree as ET
from ftplib import FTP

app = Flask(__name__)
socketio = SocketIO(app)

VERSION = "1.0.0"
SCAN_RESULTS_DIR = "scan_results"
COMMON_PORTS = "21-23,25,53,80,110,139,443,445,1433,3306,3389,5900,8080"

# Configuration FTP
FTP_HOST = "192.168.1.101"
FTP_PATH = "/var/www/html/scan_recep/"

# Créer le dossier pour les résultats s'il n'existe pas
if not os.path.exists(SCAN_RESULTS_DIR):
    os.makedirs(SCAN_RESULTS_DIR)

def capture_screen():
    """Capture l'écran et retourne l'image en base64"""
    with mss() as sct:
        screenshot = sct.shot(output=None)
        return base64.b64encode(screenshot).decode()

def save_scan_results(results):
    """Sauvegarde les résultats en XML et les envoie par FTP"""
    # Format: scan_YYYYMMDD.xml
    timestamp = datetime.now().strftime("%Y%m%d")
    
    # Capture d'écran
    try:
        screenshot = capture_screen()
    except Exception as e:
        print(f"Erreur lors de la capture d'écran: {e}")
        screenshot = ""
    
    # Préparation des données pour XML
    xml_data = {
        'scan': {
            'metadata': {
                'date': datetime.now().strftime("%d/%m/%Y"),
                'network': results.get('network', 'unknown')
            },
            'screenshot': screenshot,
            'hosts': results.get('hosts', [])
        }
    }
    
    # Création du fichier XML
    xml_filename = f"scan_{timestamp}.xml"
    xml_filepath = os.path.join(SCAN_RESULTS_DIR, xml_filename)
    
    try:
        # Conversion en XML avec une structure personnalisée
        xml = dicttoxml(xml_data, custom_root='network_scan', attr_type=False)
        # Formatage du XML pour le rendre plus lisible
        dom = parseString(xml)
        
        # Sauvegarde locale
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            f.write(dom.toprettyxml())
        
        # Envoi FTP
        try:
            ftp = FTP(FTP_HOST)
            ftp.login()  # Connexion anonyme
            
            # Vérifier si le répertoire existe, sinon le créer
            try:
                ftp.cwd(FTP_PATH)
            except:
                # Si le répertoire n'existe pas, on essaie de le créer
                dirs = FTP_PATH.split('/')
                current_dir = ""
                for d in dirs:
                    if d:
                        current_dir += "/" + d
                        try:
                            ftp.cwd(current_dir)
                        except:
                            try:
                                ftp.mkd(current_dir)
                                ftp.cwd(current_dir)
                            except:
                                pass
            
            # Envoi du fichier
            with open(xml_filepath, 'rb') as file:
                ftp.storbinary(f'STOR {xml_filename}', file)
            
            ftp.quit()
            print(f"Fichier envoyé avec succès via FTP à {FTP_HOST}{FTP_PATH}")
            
        except Exception as e:
            print(f"Erreur lors de l'envoi FTP: {e}")
        
        return xml_filename
    except Exception as e:
        print(f"Erreur lors de la sauvegarde XML: {e}")
        return None

def xml_to_dict(xml_file):
    """Convertit un fichier XML en dictionnaire pour l'interface web"""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Extraction des données
    scan = root.find('.//scan')
    metadata = scan.find('metadata')
    hosts = scan.find('hosts')
    
    return {
        'date': metadata.find('date').text,
        'network': metadata.find('network').text,
        'hosts': [
            {
                'ip': host.find('ip').text,
                'hostname': host.find('hostname').text,
                'ports': [
                    {
                        'port': int(port.find('port').text),
                        'service': port.find('service').text,
                        'version': port.find('version').text if port.find('version').text else '',
                        'protocol': port.find('protocol').text
                    }
                    for port in host.find('ports').findall('item')
                ]
            }
            for host in hosts.findall('item')
        ]
    }

def scan_network():
    nm = nmap.PortScanner()
    network = "192.168.1.0/24"
    
    try:
        # Scan avec nmap
        nm.scan(hosts=network, arguments=f'-T4 -p{COMMON_PORTS}')
        
        results = {
            'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'network': network,
            'hosts': []
        }
        
        for host in nm.all_hosts():
            if nm[host].state() == 'up':
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except:
                    hostname = "Inconnu"
                
                open_ports = []
                if 'tcp' in nm[host]:
                    for port in nm[host]['tcp']:
                        if nm[host]['tcp'][port]['state'] == 'open':
                            service_name = nm[host]['tcp'][port]['name']
                            if service_name == '':
                                service_name = "unknown"
                            
                            open_ports.append({
                                'port': port,
                                'service': service_name,
                                'version': nm[host]['tcp'][port].get('version', ''),
                                'protocol': 'tcp'
                            })
                
                results['hosts'].append({
                    'ip': host,
                    'hostname': hostname,
                    'ports': open_ports
                })
        
        try:
            # Sauvegarde en XML
            filename = save_scan_results(results)
            if filename:
                print(f"Scan sauvegardé dans {filename}")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du scan: {e}")
        
        # Envoi des résultats à l'interface web
        socketio.emit('scan_results', results)
        
    except Exception as e:
        error_msg = f"Erreur lors du scan: {str(e)}"
        print(error_msg)
        socketio.emit('scan_error', {'error': error_msg})

def get_system_info():
    """Récupère les informations système"""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "Non disponible"
    return {
        "hostname": hostname,
        "ip": ip,
        "version": VERSION
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scans')
def list_scans():
    """Liste tous les scans disponibles"""
    scans = []
    for filename in os.listdir(SCAN_RESULTS_DIR):
        if filename.endswith('.xml'):
            filepath = os.path.join(SCAN_RESULTS_DIR, filename)
            data = xml_to_dict(filepath)
            scans.append({
                'filename': filename,
                'date': data['date'],
                'host_count': len(data['hosts'])
            })
    return jsonify(scans)

@app.route('/api/scans/<filename>')
def get_scan(filename):
    """Récupère les résultats d'un scan"""
    filepath = os.path.join(SCAN_RESULTS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='application/xml')
    return jsonify({'error': 'Scan non trouvé'}), 404

@app.route('/api/latest_scan')
def get_latest_scan():
    """Récupère le dernier scan effectué"""
    scans = [f for f in os.listdir(SCAN_RESULTS_DIR) if f.endswith('.xml')]
    if not scans:
        return jsonify({'error': 'Aucun scan disponible'}), 404
    
    latest_scan = max(scans, key=lambda x: os.path.getctime(os.path.join(SCAN_RESULTS_DIR, x)))
    return get_scan(latest_scan)

@app.route('/system_info')
def system_info():
    """Endpoint pour récupérer les informations système"""
    return jsonify(get_system_info())

@socketio.on('start_scan')
def handle_scan_request():
    thread = threading.Thread(target=scan_network)
    thread.daemon = True
    thread.start()

def monitor_wan_latency():
    while True:
        latency = ping('8.8.8.8', timeout=2)
        if latency is not None:
            latency = round(latency * 1000, 2)
        else:
            latency = -1
        
        socketio.emit('wan_latency', {'latency': latency})
        time.sleep(5)

if __name__ == '__main__':
    latency_thread = threading.Thread(target=monitor_wan_latency)
    latency_thread.daemon = True
    latency_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
