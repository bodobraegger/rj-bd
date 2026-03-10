// Real beach data based on INEA monitoring points in Rio de Janeiro
// Data source: INEA Boletim de Balneabilidade
// This will be updated by fetching from beachData.json which can be generated from INEA bulletins
const BEACHES_DATA = [];

// State management
let map;
let markers = [];
let userMarker = null;
let currentSort = 'favorites';
let favorites = JSON.parse(localStorage.getItem('favoriteBeaches') || '[]');
let beachData = [];
let hiddenStatuses = new Set(['unknown']); // Hide 'unknown' by default

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    await fetchBeachData();
    await checkWeatherAlert();
    renderBeachList();
    initEventListeners();
    initLegendFilters();
    
    setTimeout(() => {
        document.getElementById('loading').style.display = 'none';
        // Invalidate map size after layout is complete (important for mobile)
        if (map) {
            map.invalidateSize();
        }
    }, 500);
    
    // Handle window resize for responsive layout
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (map) {
                map.invalidateSize();
                fitMapToVisibleBeaches();
            }
        }, 250);
    });
});

// Initialize Leaflet map
function initMap() {
    // Define bounds for Rio de Janeiro area
    const rioBounds = [
        [-23.15, -43.8], // Southwest coordinates
        [-22.75, -43.0]  // Northeast coordinates
    ];

    map = L.map('map', {
        zoomControl: true,
        attributionControl: false,
        maxBounds: rioBounds,
        maxBoundsViscosity: 1.0,
        minZoom: 10
    }).setView([-22.9711, -43.2044], 11);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
    }).addTo(map);

    // Add custom attribution
    L.control.attribution({
        position: 'bottomright',
        prefix: false
    }).addAttribution('Rio Batheability').addTo(map);
}

// Fetch beach data from JSON file (generated from INEA bulletins)
async function fetchBeachData() {
    try {
        const response = await fetch('beachData.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        beachData = data.beaches || [];
        updateMapMarkers();
        fitMapToVisibleBeaches();
    } catch (error) {
        console.error('Error fetching beach data:', error);
        // Show error to user
        document.getElementById('weatherAlert').innerHTML = 
            '⚠️ Erro ao carregar dados. Por favor, tente novamente mais tarde.';
        document.getElementById('weatherAlert').classList.add('show');
    }
}

// Fit map bounds to visible beaches only
function fitMapToVisibleBeaches() {
    const visibleBeaches = beachData.filter(beach => !hiddenStatuses.has(beach.status));
    
    if (visibleBeaches.length > 0) {
        const bounds = L.latLngBounds(visibleBeaches.map(beach => [beach.lat, beach.lng]));
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Check weather and show alert if needed
async function checkWeatherAlert() {
    // TODO: Replace with real weather API
    // Example using OpenWeatherMap or INMET:
    // const response = await fetch('weather-api-endpoint');
    // const weather = await response.json();
    
    // Mock: Simulate checking for heavy rain
    const hasHeavyRain = Math.random() > 0.7; // 30% chance for demo
    
    if (hasHeavyRain) {
        document.getElementById('weatherAlert').classList.add('show');
    }
}

// Update map markers
function updateMapMarkers() {
    // Clear existing markers
    markers.forEach(marker => {
        if (marker) {
            map.removeLayer(marker);
        }
    });
    markers = [];

    // Add new markers
    beachData.forEach(beach => {
        // Skip if status is hidden
        if (hiddenStatuses.has(beach.status)) {
            markers.push(null);
            return;
        }

        const color = getStatusColor(beach.status);
        
        const marker = L.circleMarker([beach.lat, beach.lng], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
        }).addTo(map);

        marker.bindPopup(`
            <div class="popup-name">${beach.name}</div>
            <div class="popup-status">
                <strong>Status:</strong> ${getStatusText(beach.status)}<br>
                <strong>Zona:</strong> ${beach.zone}<br>
                <strong>Atualizado:</strong> ${formatDate(beach.lastUpdate)}
            </div>
        `);

        marker.on('click', () => {
            highlightBeach(beach.id);
        });

        markers.push(marker);
    });
}

// Render beach list
function renderBeachList() {
    const sortedBeaches = sortBeaches(beachData, currentSort);
    const filteredBeaches = sortedBeaches.filter(beach => !hiddenStatuses.has(beach.status));
    
    const listHtml = filteredBeaches.map(beach => {
        const isFavorite = favorites.includes(beach.id);
        const statusClass = `status-${beach.status}`;
        
        return `
            <div class="beach-item" data-id="${beach.id}" onclick="focusBeach(${beach.id})">
                <div class="beach-header">
                    <div class="beach-name">${beach.name}</div>
                    <button class="fav-btn ${isFavorite ? 'active' : ''}" onclick="toggleFavorite(event, ${beach.id})">★</button>
                </div>
                <div class="beach-status">
                    <div class="status-indicator ${statusClass}"></div>
                    <span>${getStatusText(beach.status)}</span>
                </div>
                <div class="beach-updated">Atualizado: ${formatDate(beach.lastUpdate)}</div>
            </div>
        `;
    }).join('');

    document.getElementById('beachList').innerHTML = listHtml;
}

// Sort beaches
function sortBeaches(beaches, sortType) {
    const sorted = [...beaches];
    
    switch(sortType) {
        case 'favorites':
            sorted.sort((a, b) => {
                const aFav = favorites.includes(a.id) ? 1 : 0;
                const bFav = favorites.includes(b.id) ? 1 : 0;
                if (aFav !== bFav) return bFav - aFav;
                return a.name.localeCompare(b.name);
            });
            break;
        case 'name':
            sorted.sort((a, b) => a.name.localeCompare(b.name));
            break;
        case 'status':
            const statusOrder = { improper: 0, warning: 1, proper: 2, unknown: 3 };
            sorted.sort((a, b) => {
                const diff = statusOrder[a.status] - statusOrder[b.status];
                if (diff !== 0) return diff;
                return a.name.localeCompare(b.name);
            });
            break;
    }
    
    return sorted;
}

// Toggle favorite
function toggleFavorite(event, beachId) {
    event.stopPropagation();
    
    const index = favorites.indexOf(beachId);
    if (index > -1) {
        favorites.splice(index, 1);
    } else {
        favorites.push(beachId);
    }
    
    localStorage.setItem('favoriteBeaches', JSON.stringify(favorites));
    renderBeachList();
}

// Focus on beach
function focusBeach(beachId) {
    const beach = beachData.find(b => b.id === beachId);
    if (beach) {
        map.setView([beach.lat, beach.lng], 15, { animate: true });
        
        // Find and open the marker popup
        const markerIndex = beachData.findIndex(b => b.id === beachId);
        if (markers[markerIndex]) {
            markers[markerIndex].openPopup();
        }
    }
}

// Highlight beach in list
function highlightBeach(beachId) {
    document.querySelectorAll('.beach-item').forEach(item => {
        item.style.background = '';
    });
    
    const item = document.querySelector(`[data-id="${beachId}"]`);
    if (item) {
        item.style.background = 'rgba(102, 126, 234, 0.3)';
        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Event listeners
function initEventListeners() {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentSort = e.target.dataset.sort;
            renderBeachList();
        });
    });
}

// Initialize legend filters
function initLegendFilters() {
    document.querySelectorAll('.legend-item').forEach(item => {
        item.addEventListener('click', () => {
            const status = item.dataset.status;
            
            if (hiddenStatuses.has(status)) {
                hiddenStatuses.delete(status);
                item.classList.remove('hidden');
            } else {
                hiddenStatuses.add(status);
                item.classList.add('hidden');
            }
            
            renderBeachList();
            updateMapMarkers();
        });
    });
}

// Toggle sidebar (mobile)
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('closed');
}

// Locate user
// Locate user
function getUserLocation() {
    if (!navigator.geolocation) {
        alert('Geolocalização não é suportada pelo seu navegador');
        return;
    }

    const btn = document.getElementById('locateBtn');
    btn.classList.add('loading');
    btn.disabled = true;

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude } = position.coords;
            
            // Remove previous user marker
            if (userMarker) {
                map.removeLayer(userMarker);
            }
            
            // Add user location marker
            userMarker = L.circleMarker([latitude, longitude], {
                radius: 10,
                fillColor: '#667eea',
                color: '#fff',
                weight: 3,
                opacity: 1,
                fillOpacity: 0.9,
                className: 'user-marker'
            }).addTo(map);
            
            userMarker.bindPopup('📍 Você está aqui');
            
            // Pan to user location
            map.setView([latitude, longitude], 13, { animate: true });
            
            // Find nearest beach
            const nearest = findNearestBeach(latitude, longitude);
            if (nearest) {
                setTimeout(() => {
                    highlightBeach(nearest.id);
                    // Scroll to beach in sidebar
                    const beachItem = document.querySelector(`[data-id="${nearest.id}"]`);
                    if (beachItem) {
                        beachItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }, 1000);
            }
            
            btn.classList.remove('loading');
            btn.disabled = false;
        },
        (error) => {
            let message = 'Não foi possível obter sua localização';
            
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    message = 'Permissão de localização negada. Por favor, habilite nas configurações do navegador.';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message = 'Localização indisponível no momento.';
                    break;
                case error.TIMEOUT:
                    message = 'Tempo esgotado ao tentar obter localização.';
                    break;
            }
            
            alert(message);
            btn.classList.remove('loading');
            btn.disabled = false;
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// Find nearest beach to coordinates
function findNearestBeach(lat, lng) {
    if (beachData.length === 0) return null;
    
    let nearest = null;
    let minDistance = Infinity;
    
    beachData.forEach(beach => {
        const distance = getDistance(lat, lng, beach.lat, beach.lng);
        if (distance < minDistance) {
            minDistance = distance;
            nearest = beach;
        }
    });
    
    return nearest;
}

// Calculate distance between two coordinates (Haversine formula)
function getDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

function toRad(deg) {
    return deg * (Math.PI / 180);
}

// Utility functions
function getStatusColor(status) {
    const colors = {
        proper: '#51cf66',
        warning: '#ffd43b',
        improper: '#ff6b6b',
        unknown: '#868e96'
    };
    return colors[status] || colors.unknown;
}

function getStatusText(status) {
    const texts = {
        proper: 'Própria',
        warning: 'Atenção',
        improper: 'Imprópria',
        unknown: 'Desconhecido'
    };
    return texts[status] || texts.unknown;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Hoje';
    if (diffDays === 1) return 'Ontem';
    if (diffDays < 7) return `${diffDays} dias atrás`;
    
    return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

// Auto-refresh data every 5 minutes
setInterval(fetchBeachData, 5 * 60 * 1000);
