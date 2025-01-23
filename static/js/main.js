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

// Gestionnaire du bouton de scan
document.getElementById('start-scan').addEventListener('click', function() {
    socket.emit('start_scan');
    document.getElementById('scan-results').innerHTML = '<p class="text-blue-600">Scan en cours...</p>';
    document.getElementById('start-scan').disabled = true;
});

// Écouteurs Socket.IO
socket.on('scan_results', function(data) {
    let resultsHtml = `
        <div class="space-y-4">
            <p class="font-bold">Scan effectué le: ${data.timestamp}</p>
            <p>Machines détectées: ${data.hosts.length}</p>
            <div class="mt-4 space-y-4">
    `;
    
    data.hosts.forEach(host => {
        resultsHtml += `
            <div class="p-4 bg-gray-50 rounded-lg">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="font-bold">IP: ${host.ip}</p>
                        <p class="text-gray-600">Hostname: ${host.hostname}</p>
                    </div>
                </div>
                ${formatPorts(host.ports)}
            </div>
        `;
    });
    
    resultsHtml += '</div></div>';
    document.getElementById('scan-results').innerHTML = resultsHtml;
    document.getElementById('start-scan').disabled = false;
});

socket.on('scan_error', function(data) {
    document.getElementById('scan-results').innerHTML = `
        <div class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4">
            <p class="font-bold">Erreur lors du scan</p>
            <p>${data.error}</p>
        </div>
    `;
    document.getElementById('start-scan').disabled = false;
});

socket.on('wan_latency', function(data) {
    const latencyElement = document.getElementById('wan-latency');
    if (data.latency === -1) {
        latencyElement.textContent = 'Timeout';
        latencyElement.className = 'text-2xl font-bold text-center text-red-500';
    } else {
        latencyElement.textContent = `${data.latency} ms`;
        latencyElement.className = 'text-2xl font-bold text-center text-green-500';
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
