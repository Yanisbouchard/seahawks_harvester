from flask import Flask, render_template, jsonify, send_file, request
from flask_socketio import SocketIO
import nmap
import socket
import psutil
from ping3 import ping
from datetime import datetime
import threading
import time
import json
import os
import base64
from mss import mss
from io import BytesIO


app = Flask(__name__)
socketio = SocketIO(app)

VERSION = "1.0.0"
SCAN_RESULTS_DIR = "scan_results"
COMMON_PORTS = "21-23,25,53,80,110,139,443,445,1433,3306,3389,5900,8080"

# Créer le dossier pour les résultats s'il n'existe pas
if not os.path.exists(SCAN_RESULTS_DIR):
    os.makedirs(SCAN_RESULTS_DIR)

def get_system_info():
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

def get_service_name(port, protocol):
    try:
        service = socket.getservbyport(int(port), protocol)
        return service
    except:
        return "unknown"

def capture_screen():
    """Capture l'écran et retourne l'image en base64"""
    with mss() as sct:
        # Capture le moniteur principal
        screenshot = sct.shot(output=None)  # Retourne les bytes de l'image PNG
        return base64.b64encode(screenshot).decode()

def save_scan_results(results):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Capture d'écran
    screenshot = capture_screen()
    results['screenshot'] = screenshot
    
    # Sauvegarde dans un fichier JSON
    filename = f"scan_{timestamp}.json"
    filepath = os.path.join(SCAN_RESULTS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    return filename

def scan_network():
    nm = nmap.PortScanner()
    network = "192.168.1.0/24"
    
    socketio.emit('scan_status', {'status': 'En cours...'})
    
    try:
        nm.scan(hosts=network, arguments=f'-T4 -p{COMMON_PORTS} --min-rate 1000')
        
        results = {
            'hosts': [],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'network': network
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
                                service_name = get_service_name(port, 'tcp')
                            
                            open_ports.append({
                                'port': port,
                                'service': service_name,
                                'version': nm[host]['tcp'][port].get('version', ''),
                                'protocol': 'tcp'
                            })
                
                if 'udp' in nm[host]:
                    for port in nm[host]['udp']:
                        if nm[host]['udp'][port]['state'] == 'open':
                            service_name = nm[host]['udp'][port]['name']
                            if service_name == '':
                                service_name = get_service_name(port, 'udp')
                            
                            open_ports.append({
                                'port': port,
                                'service': service_name,
                                'version': nm[host]['udp'][port].get('version', ''),
                                'protocol': 'udp'
                            })
                
                results['hosts'].append({
                    'ip': host,
                    'hostname': hostname,
                    'ports': open_ports
                })
        
        # Sauvegarder les résultats avec la capture d'écran
        filename = save_scan_results(results)
        results['filename'] = filename
        
        socketio.emit('scan_results', results)
    except Exception as e:
        socketio.emit('scan_error', {'error': str(e)})

def monitor_wan_latency():
    while True:
        latency = ping('8.8.8.8', timeout=2)
        if latency is not None:
            latency = round(latency * 1000, 2)
        else:
            latency = -1
        
        socketio.emit('wan_latency', {'latency': latency})
        time.sleep(5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/system_info')
def system_info():
    return jsonify(get_system_info())

@app.route('/api/scan', methods=['POST'])
def receive_scan():
    """Endpoint pour recevoir les résultats du scan avec capture d'écran"""
    try:
        data = request.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scan_{timestamp}.json"
        filepath = os.path.join(SCAN_RESULTS_DIR, filename)
        
        # Sauvegarde des données
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return jsonify({
            'status': 'success',
            'message': 'Données reçues et sauvegardées',
            'filename': filename
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/scans')
def list_scans():
    """Liste tous les scans disponibles"""
    scans = []
    for filename in os.listdir(SCAN_RESULTS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(SCAN_RESULTS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                scans.append({
                    'filename': filename,
                    'timestamp': data['timestamp'],
                    'host_count': len(data['hosts']),
                    'has_screenshot': 'screenshot' in data
                })
    return jsonify(scans)

@app.route('/api/scans/<filename>')
def get_scan(filename):
    """Récupère les résultats d'un scan spécifique"""
    filepath = os.path.join(SCAN_RESULTS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='application/json')
    return jsonify({'error': 'Scan non trouvé'}), 404

@app.route('/api/latest_scan')
def get_latest_scan():
    """Récupère le dernier scan effectué"""
    scans = os.listdir(SCAN_RESULTS_DIR)
    if not scans:
        return jsonify({'error': 'Aucun scan disponible'}), 404
    
    latest_scan = max(scans, key=lambda x: os.path.getctime(os.path.join(SCAN_RESULTS_DIR, x)))
    return get_scan(latest_scan)

@socketio.on('start_scan')
def handle_scan_request():
    thread = threading.Thread(target=scan_network)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    latency_thread = threading.Thread(target=monitor_wan_latency)
    latency_thread.daemon = True
    latency_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
