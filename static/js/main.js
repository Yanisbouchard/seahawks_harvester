const socket = io();
let latencyChart;
const maxDataPoints = 50;
const latencyData = {
    labels: [],
    datasets: [{
        label: 'Latence (ms)',
        data: [],
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1
    }]
};

// Initialisation du graphique
function initChart() {
    const ctx = document.getElementById('latencyChart').getContext('2d');
    latencyChart = new Chart(ctx, {
        type: 'line',
        data: latencyData,
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            animation: {
                duration: 0
            }
        }
    });
}

// Chargement des informations système
async function loadSystemInfo() {
    try {
        const response = await fetch('/system_info');
        const data = await response.json();
        document.getElementById('system-info').innerHTML = `
            <p>Nom de la machine: ${data.hostname}</p>
            <p>Adresse IP: ${data.ip}</p>
            <p>Version: ${data.version}</p>
        `;
    } catch (error) {
        console.error('Erreur lors du chargement des informations système:', error);
    }
}

// Formater les ports pour l'affichage
function formatPorts(ports) {
    if (!ports || ports.length === 0) return '<p class="text-gray-500">Aucun port ouvert détecté</p>';
    
    return `<div class="mt-2">
        <p class="font-semibold">Ports ouverts:</p>
        <div class="grid grid-cols-1 gap-1 mt-1">
            ${ports.map(port => `
                <div class="bg-gray-50 p-2 rounded">
                    <span class="font-medium">${port.protocol.toUpperCase()}/${port.port}</span>
                    <span class="text-gray-600"> - ${port.service}</span>
                    ${port.version ? `<span class="text-gray-500 text-sm"> (${port.version})</span>` : ''}
                </div>
            `).join('')}
        </div>
    </div>`;
}

// Gestion du scan
function startScan() {
    const button = document.getElementById('start-scan');
    const spinner = document.getElementById('scan-spinner');
    const status = document.getElementById('scan-status');
    
    // Désactiver le bouton et afficher le spinner
    button.disabled = true;
    button.classList.add('opacity-50', 'cursor-not-allowed');
    spinner.classList.remove('hidden');
    status.classList.remove('hidden');
    
    document.getElementById('scan-results').innerHTML = '';
}

function endScan() {
    const button = document.getElementById('start-scan');
    const spinner = document.getElementById('scan-spinner');
    const status = document.getElementById('scan-status');
    
    // Réactiver le bouton et cacher le spinner
    button.disabled = false;
    button.classList.remove('opacity-50', 'cursor-not-allowed');
    spinner.classList.add('hidden');
    status.classList.add('hidden');
}

// Gestionnaire du bouton de scan
document.getElementById('start-scan').addEventListener('click', function() {
    socket.emit('start_scan');
    startScan();
});

// Écouteurs Socket.IO
socket.on('scan_status', function(data) {
    document.getElementById('scan-status').textContent = data.status;
});

socket.on('scan_error', function(data) {
    endScan();
    document.getElementById('scan-results').innerHTML = `
        <div class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4">
            <p class="font-bold">Erreur lors du scan</p>
            <p>${data.error}</p>
        </div>
    `;
});

socket.on('scan_results', function(data) {
    endScan();
    
    let resultsHtml = `
        <div class="bg-green-100 border-l-4 border-green-500 text-green-700 p-4 mb-4">
            <p class="font-bold">Scan terminé avec succès</p>
            <p>Scan effectué le: ${data.timestamp}</p>
            <p>Machines détectées: ${data.hosts.length}</p>
        </div>
        <div class="space-y-4">
    `;
    
    data.hosts.forEach(host => {
        resultsHtml += `
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="font-bold text-lg">${host.hostname}</p>
                        <p class="text-gray-600">IP: ${host.ip}</p>
                    </div>
                </div>
                ${formatPorts(host.ports)}
            </div>
        `;
    });
    
    resultsHtml += '</div>';
    document.getElementById('scan-results').innerHTML = resultsHtml;
});

socket.on('wan_latency', function(data) {
    const latencyElement = document.getElementById('wan-latency');
    if (data.latency === -1) {
        latencyElement.textContent = 'Timeout';
        latencyElement.className = 'text-2xl font-bold text-center text-red-500';
    } else {
        latencyElement.textContent = `${data.latency} ms`;
        latencyElement.className = 'text-2xl font-bold text-center ' + 
            (data.latency < 100 ? 'text-green-500' : 
             data.latency < 200 ? 'text-yellow-500' : 'text-red-500');
    }
    
    // Mise à jour du graphique
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    
    latencyData.labels.push(timeStr);
    latencyData.datasets[0].data.push(data.latency === -1 ? null : data.latency);
    
    if (latencyData.labels.length > maxDataPoints) {
        latencyData.labels.shift();
        latencyData.datasets[0].data.shift();
    }
    
    latencyChart.update();
});

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    loadSystemInfo();
    initChart();
});
