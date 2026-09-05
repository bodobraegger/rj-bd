const MAP_BOUNDS = [
    [-23.15, -43.8], // Southwest
    [-22.75, -43.0]  // Northeast
];
const DEFAULT_VIEW = { lat: -22.9711, lng: -43.2044, zoom: 12 };
const DATA_STALE_AFTER_MS = 60 * 60 * 1000;

const STATUS_COLORS = {
    proper: '#51cf66',
    attention: '#ffd43b',
    improper: '#ff6b6b',
    unknown: '#868e96'
};
const STATUS_TEXTS = {
    proper: 'Própria',
    attention: 'Atenção',
    improper: 'Imprópria',
    unknown: 'Sem dados'
};

const BRAND_COLOR = '#667eea';

// Fixed label sides so neighboring beaches' labels don't overlap;
// beaches missing here fall back to a side derived from their id
const LABEL_SIDES = {
    'Glória': 'right', 'Flamengo': 'bottom', 'Botafogo': 'left', 'Urca': 'right', 'Vermelha': 'right',
    'Leme': 'left', 'Copacabana': 'right', 'Diabo': 'right', 'Arpoador': 'top',
    'Ipanema': 'bottom', 'Leblon': 'top', 'Vidigal': 'bottom', 'São Conrado': 'top', 'Pepino': 'bottom',
    'Barra da Tijuca': 'left', 'Barra da Tijuca II': 'bottom', 'Joatinga': 'top',
    'Recreio/Reserva': 'bottom', 'Recreio': 'top', 'Pontal de Sernambetiba': 'bottom',
    'Prainha': 'top', 'Grumari': 'bottom', 'Barra de Guaratiba': 'top',
    'Gragoatá': 'left', 'Flechas': 'top', 'Boa Viagem': 'bottom', 'Icaraí': 'right',
    'São Francisco': 'right', 'Charitas': 'bottom', 'Adão': 'left', 'Eva': 'bottom', 'Jurujuba': 'top',
    'Piratininga': 'left', 'Camboinhas': 'bottom', 'Sossego': 'top', 'Itaipu': 'bottom', 'Itacoatiara': 'right',

};

const IS_DESKTOP = window.innerWidth > 768;
// Mobile needs one more zoom level before labels fit its smaller viewport
const LABEL_MIN_ZOOM = IS_DESKTOP ? 12 : 13;
const LABEL_ENLARGE_ZOOM = 13;

// State management
let map;
let markersByBeachId = {};
let userMarker = null;
let currentSort = 'favorites';
let favorites = JSON.parse(localStorage.getItem('favoriteBeaches') || '[]');
let beachData = [];
let hiddenStatuses = new Set(['unknown']); // Hide 'unknown' by default
let lastFetchedAt = 0;

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    await fetchBeachData();
    // Mobile first visit: without a saved position, frame all visible beaches;
    // desktop keeps DEFAULT_VIEW so labels are visible from the start
    if (!IS_DESKTOP && !localStorage.getItem('mapPosition')) {
        fitMapToVisibleBeaches();
    }
    initEventListeners();
    initLegendFilters();
    
    setTimeout(() => {
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
            }
        }, 250);
    });

    // The bulletin updates about once a day; instead of polling, refetch
    // when the user returns to a tab whose data has gone stale
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible'
                && Date.now() - lastFetchedAt > DATA_STALE_AFTER_MS) {
            fetchBeachData();
        }
    });
    
    if (map) {
        map.on('zoomend', syncBeachLabels);
    }
});

// Show/hide/resize map labels based on platform and zoom
function syncBeachLabels() {
    const zoom = map.getZoom();
    const show = zoom >= LABEL_MIN_ZOOM;

    map.getContainer().classList.toggle('labels-large', zoom >= LABEL_ENLARGE_ZOOM);

    Object.values(markersByBeachId).forEach(marker => {
        if (show) {
            marker.openTooltip();
            const tooltip = marker.getTooltip();
            // Labels are bound with the hidden class to avoid a flash at bind
            // time, but Leaflet measures them as 0x0 while hidden, which breaks
            // direction placement; unhide, then update() to re-measure
            tooltip.getElement()?.classList.remove('beach-label-hidden');
            tooltip.update();
        } else {
            marker.closeTooltip();
        }
    });
}

// Initialize Leaflet map
function initMap() {
    // Get saved map position or use defaults
    const savedPosition = JSON.parse(localStorage.getItem('mapPosition') || '{}');
    const initialLat = savedPosition.lat || DEFAULT_VIEW.lat;
    const initialLng = savedPosition.lng || DEFAULT_VIEW.lng;
    const initialZoom = savedPosition.zoom || DEFAULT_VIEW.zoom;

    map = L.map('map', {
        zoomControl: true,
        attributionControl: false,
        maxBounds: MAP_BOUNDS,
        maxBoundsViscosity: 1.0,
        minZoom: 10
    }).setView([initialLat, initialLng], initialZoom);

    // Esri's dark gray canvas (free, no API key), split into a base layer
    // and a label overlay. CartoDB's dark_all tiles now watermark
    // "API KEY REQUIRED" over the map unless a paid key is supplied.
    L.tileLayer('https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
    }).addTo(map);
    L.tileLayer('https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
    }).addTo(map);
    
    // Save map position when user moves the map
    map.on('moveend', () => {
        const center = map.getCenter();
        const zoom = map.getZoom();
        localStorage.setItem('mapPosition', JSON.stringify({
            lat: center.lat,
            lng: center.lng,
            zoom: zoom
        }));
    });
}

// Fetch beach data from JSON file (generated from INEA bulletins)
async function fetchBeachData() {
    try {
        const response = await fetch('./data/beachData.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        beachData = data.beaches || [];
        lastFetchedAt = Date.now();
        
        // Update the last update date display
        if (data.lastUpdate) {
            const updateDisplay = document.getElementById('updateDisplay');
            if (updateDisplay) {
                const date = new Date(data.lastUpdate);
                const formattedDate = date.toLocaleDateString('pt-BR', { 
                    day: '2-digit', 
                    month: '2-digit' 
                }).replace(/\//g, '.');
                updateDisplay.textContent = `data: ${formattedDate}`;
            }
        }
        
        syncUnknownLegendItem();
        updateMapMarkers();
        renderBeachList();
    } catch (error) {
        console.error('Error fetching beach data:', error);
        // Show error to user
        document.getElementById('weatherAlert').innerHTML = 
            '⚠️ Erro ao carregar dados. Por favor, tente novamente mais tarde.';
        document.getElementById('weatherAlert').classList.add('show');
    }
}

// While any beach lacks data, the 'Sem dados' legend entry replaces the bbo.do link
function syncUnknownLegendItem() {
    const hasUnknown = beachData.some(beach => beach.status === 'unknown');
    document.querySelector('.legend-item[data-status="unknown"]')
        .classList.toggle('display-none', !hasUnknown);
    document.querySelector('.home-link').classList.toggle('display-none', hasUnknown);
}

// Beaches not hidden by the legend filters
function visibleBeaches() {
    return beachData.filter(beach => !hiddenStatuses.has(beach.status));
}

// Fit map bounds to visible beaches only
function fitMapToVisibleBeaches() {
    const beaches = visibleBeaches();
    if (beaches.length > 0) {
        const bounds = L.latLngBounds(beaches.map(beach => [beach.lat, beach.lng]));
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Escape data-derived text before interpolating it into HTML
function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = value ?? '';
    return element.innerHTML;
}

// Update map markers
function updateMapMarkers() {
    Object.values(markersByBeachId).forEach(marker => map.removeLayer(marker));
    markersByBeachId = {};

    visibleBeaches().forEach(beach => {
        const marker = L.circleMarker([beach.lat, beach.lng], {
            radius: 8,
            fillColor: getStatusColor(beach.status),
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
        }).addTo(map);

        const direction = LABEL_SIDES[beach.name] || (beach.id % 2 === 0 ? 'top' : 'bottom');
        const offset = { top: [0, -10], bottom: [0, 10], left: [-10, 0], right: [10, 0] }[direction];

        // Add permanent tooltip that shows on zoom
        marker.bindTooltip(escapeHtml(beach.name), {
            permanent: true,
            direction: direction,
            className: 'beach-label beach-label-hidden',
            offset: offset,
            opacity: 1
        });

        // Build popup content with monitoring points
        let popupContent = `
            <div class="popup-name">${escapeHtml(beach.name)}</div>
            <div class="popup-status">
                <strong>Status:</strong> ${getStatusText(beach.status)}<br>
                <strong>Zona:</strong> ${escapeHtml(beach.zone)}
            </div>
        `;

        // Add monitoring points if available
        if (beach.monitoringPoints && beach.monitoringPoints.length > 0) {
            popupContent += `<div class="popup-points"><strong>Pontos de Monitoramento:</strong><ul>`;
            beach.monitoringPoints.forEach(point => {
                const pointStatusText = getStatusText(point.status);
                const pointIcon = point.status === 'proper' ? '✓' : (point.status === 'improper' ? '✗' : '⚠');
                popupContent += `<li><span class="point-${point.status}">${pointIcon} ${escapeHtml(point.code || 'N/A')}</span> - ${pointStatusText}`;
                if (point.location) {
                    popupContent += `<br><span class="popup-point-location">${escapeHtml(point.location)}</span>`;
                }
                popupContent += `</li>`;
            });
            popupContent += `</ul></div>`;
        }

        marker.bindPopup(popupContent);

        marker.on('click', () => {
            highlightBeach(beach.id);
        });

        marker.on('popupclose', () => {
            // Clear highlight when popup closes
            if (currentHighlightedBeachId === beach.id) {
                clearBeachHighlight();
            }
        });

        markersByBeachId[beach.id] = marker;
    });

    syncBeachLabels();
}

// Render beach list
function renderBeachList() {
    const sortedBeaches = sortBeaches(visibleBeaches(), currentSort);

    const listHtml = sortedBeaches.map(beach => {
        const isFavorite = favorites.includes(beach.id);
        const statusClass = `status-${beach.status}`;
        
        // Build monitoring points summary
        let pointsSummary = '';
        if (beach.monitoringPoints && beach.monitoringPoints.length > 0) {
            const pointCodes = beach.monitoringPoints.map(p => {
                const statusClass = `point-${p.status}`;
                return `<span class="point-code ${statusClass}">${escapeHtml(p.code)}</span>`;
            }).join(' ');
            pointsSummary = `<div class="beach-points">${pointCodes}</div>`;
        }
        
        return `
            <div class="beach-item" data-id="${beach.id}" onclick="focusBeach(${beach.id})">
                <div class="beach-header">
                    <div class="beach-name">${escapeHtml(beach.name)}</div>
                    ${pointsSummary}
                    <button class="fav-btn ${isFavorite ? 'active' : ''}" onclick="toggleFavorite(event, ${beach.id})"></button>
                </div>
                <div class="beach-status">
                    <div class="status-indicator ${statusClass}"></div>
                    <span>${getStatusText(beach.status)}</span>
                </div>
            </div>
        `;
    }).join('');

    document.getElementById('beachList').innerHTML = listHtml;
}

// Sort beaches
function sortBeaches(beaches, sortType) {
    const sorted = [...beaches];
    
    // Define zone/city priority: Rio zones first, then Niterói
    const zonePriority = {
        'Zona Sul': 1,
        'Zona Oeste': 2,
        'Niterói': 3
    };
    
    const compareByZone = (a, b) => {
        const aPriority = zonePriority[a.zone] || 99;
        const bPriority = zonePriority[b.zone] || 99;
        return aPriority - bPriority;
    };
    
    switch(sortType) {
        case 'favorites':
            sorted.sort((a, b) => {
                const aFav = favorites.includes(a.id) ? 1 : 0;
                const bFav = favorites.includes(b.id) ? 1 : 0;
                if (aFav !== bFav) return bFav - aFav;
                
                // Then by zone
                const zoneDiff = compareByZone(a, b);
                if (zoneDiff !== 0) return zoneDiff;
                
                return a.name.localeCompare(b.name);
            });
            break;
        case 'status':
            const statusOrder = { improper: 0, attention: 1, unknown: 1, proper: 2 };
            sorted.sort((a, b) => {
                const diff = statusOrder[a.status] - statusOrder[b.status];
                if (diff !== 0) return diff;
                
                // Then by zone
                const zoneDiff = compareByZone(a, b);
                if (zoneDiff !== 0) return zoneDiff;
                
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
        // Use higher zoom and better centering
        map.setView([beach.lat, beach.lng], 16, { animate: true });

        // Find and open the marker popup
        if (markersByBeachId[beachId]) {
            markersByBeachId[beachId].openPopup();
        }
    }
}

// Highlight beach in list
let currentHighlightedBeachId = null;

function clearBeachHighlight() {
    document.querySelectorAll('.beach-item.highlighted').forEach(item => {
        item.classList.remove('highlighted');
    });
    currentHighlightedBeachId = null;
}

function highlightBeach(beachId) {
    // Don't toggle off - always keep highlighted when marker is clicked
    clearBeachHighlight();

    const item = document.querySelector(`[data-id="${beachId}"]`);
    if (item) {
        item.classList.add('highlighted');
        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        currentHighlightedBeachId = beachId;
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
                fillColor: BRAND_COLOR,
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
    return STATUS_COLORS[status] || STATUS_COLORS.attention;
}

function getStatusText(status) {
    return STATUS_TEXTS[status] || STATUS_TEXTS.unknown;
}
