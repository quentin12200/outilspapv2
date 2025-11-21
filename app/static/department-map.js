/**
 * Department Map Module
 * Adds an interactive Leaflet map to department detail modals
 */

class DepartmentMap {
    constructor() {
        this.map = null;
        this.markers = [];
        this.currentDept = null;
    }

    /**
     * Initialize the map when a department modal is opened
     */
    init(deptCode, companies) {
        // Create map container if it doesn't exist
        const modalContent = document.querySelector('[x-show="selectedDeptInscrits !== null"] .p-6');
        if (!modalContent) return;

        // Check if map container already exists
        let mapContainer = document.getElementById('dept-map-container');
        if (!mapContainer) {
            mapContainer = document.createElement('div');
            mapContainer.id = 'dept-map-container';
            mapContainer.className = 'mb-6';
            mapContainer.innerHTML = `
        <h4 class="text-lg font-bold text-gray-900 mb-3 flex items-center">
          <i class="fas fa-map-marked-alt text-cgt-red mr-2"></i>
          Localisation des établissements
        </h4>
        <div id="dept-map" style="height: 400px; width: 100%; border-radius: 8px; border: 2px solid #e5e7eb;"></div>
      `;

            // Insert at the beginning of modal content
            modalContent.insertBefore(mapContainer, modalContent.firstChild);
        }

        // Initialize or reset the map
        this.createMap(deptCode, companies);
    }

    /**
     * Create the Leaflet map
     */
    createMap(deptCode, companies) {
        // Destroy existing map if any
        if (this.map) {
            this.map.remove();
            this.map = null;
        }

        // Clear existing markers
        this.markers = [];

        // Create new map centered on France
        this.map = L.map('dept-map').setView([46.603354, 1.888334], 6);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(this.map);

        // Get department center coordinates (approximate)
        const deptCenter = this.getDepartmentCenter(deptCode);
        if (deptCenter) {
            this.map.setView(deptCenter, 9);
        }

        // Add markers for companies
        if (companies && companies.length > 0) {
            this.addCompanyMarkers(companies, deptCode);
        } else {
            // Show message if no companies
            const messageDiv = document.createElement('div');
            messageDiv.className = 'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white p-4 rounded-lg shadow-lg z-[1000] text-center';
            messageDiv.innerHTML = `
        <i class="fas fa-info-circle text-gray-400 text-3xl mb-2"></i>
        <p class="text-gray-600">Aucune entreprise à afficher sur la carte</p>
      `;
            document.getElementById('dept-map').appendChild(messageDiv);
        }
    }

    /**
     * Add markers for companies on the map
     */
    async addCompanyMarkers(companies, deptCode) {
        const bounds = [];

        for (const company of companies) {
            // Try to get coordinates from city name
            const coords = await this.geocodeCity(company.ville, deptCode);

            if (coords) {
                // Create custom icon
                const icon = L.divIcon({
                    className: 'custom-marker',
                    html: `
            <div style="background-color: #d5001c; color: white; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
              ${this.formatNumber(company.inscrits / 1000)}k
            </div>
          `,
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                });

                // Create marker
                const marker = L.marker(coords, { icon }).addTo(this.map);

                // Create popup
                const popupContent = `
          <div style="min-width: 200px;">
            <h5 style="font-weight: bold; margin-bottom: 8px; color: #1f2937;">${company.raison_sociale}</h5>
            <div style="font-size: 13px; color: #6b7280;">
              <p style="margin: 4px 0;"><i class="fas fa-map-marker-alt" style="width: 16px;"></i> ${company.ville}</p>
              <p style="margin: 4px 0;"><i class="fas fa-id-card" style="width: 16px;"></i> ${company.siret}</p>
              <p style="margin: 4px 0;"><i class="fas fa-users" style="width: 16px;"></i> <strong style="color: #d5001c;">${this.formatNumber(company.inscrits)}</strong> inscrits</p>
              <p style="margin: 4px 0;"><i class="fas fa-sync-alt" style="width: 16px;"></i> Cycle ${company.cycle}</p>
            </div>
          </div>
        `;
                marker.bindPopup(popupContent);

                this.markers.push(marker);
                bounds.push(coords);
            }
        }

        // Fit map to show all markers
        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [50, 50] });
        }
    }

    /**
     * Geocode a city name to get coordinates
     * Uses Nominatim API (free, no API key required)
     */
    async geocodeCity(cityName, deptCode) {
        try {
            // Use a simple cache to avoid repeated requests
            const cacheKey = `${cityName}_${deptCode}`;
            if (this.geocodeCache && this.geocodeCache[cacheKey]) {
                return this.geocodeCache[cacheKey];
            }

            // Initialize cache if needed
            if (!this.geocodeCache) {
                this.geocodeCache = {};
            }

            // Call Nominatim API
            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?` +
                `city=${encodeURIComponent(cityName)}&` +
                `countrycodes=fr&` +
                `format=json&` +
                `limit=1`,
                {
                    headers: {
                        'User-Agent': 'OutilsPAP/1.0'
                    }
                }
            );

            const data = await response.json();

            if (data && data.length > 0) {
                const coords = [parseFloat(data[0].lat), parseFloat(data[0].lon)];
                this.geocodeCache[cacheKey] = coords;
                return coords;
            }

            return null;
        } catch (error) {
            console.error('Geocoding error:', error);
            return null;
        }
    }

    /**
     * Get approximate center coordinates for a department
     */
    getDepartmentCenter(deptCode) {
        // Approximate centers for French departments
        const centers = {
            '01': [46.2, 5.23], '02': [49.57, 3.62], '03': [46.34, 3.34], '04': [44.09, 6.24],
            '05': [44.66, 6.08], '06': [43.95, 7.27], '07': [44.75, 4.60], '08': [49.77, 4.72],
            '09': [42.96, 1.60], '10': [48.30, 4.08], '11': [43.21, 2.35], '12': [44.35, 2.57],
            '13': [43.53, 5.01], '14': [49.18, -0.37], '15': [45.04, 2.61], '16': [45.65, 0.16],
            '17': [45.75, -0.64], '18': [47.08, 2.40], '19': [45.27, 1.77], '21': [47.32, 4.86],
            '22': [48.51, -2.76], '23': [46.17, 2.06], '24': [45.18, 0.72], '25': [47.24, 6.02],
            '26': [44.73, 5.04], '27': [49.09, 0.88], '28': [48.45, 1.49], '29': [48.20, -4.10],
            '2A': [41.92, 8.74], '2B': [42.55, 9.15], '30': [43.96, 4.09], '31': [43.60, 1.44],
            '32': [43.65, 0.59], '33': [44.84, -0.58], '34': [43.61, 3.88], '35': [48.11, -1.68],
            '36': [46.81, 1.69], '37': [47.39, 0.69], '38': [45.27, 5.59], '39': [46.75, 5.76],
            '40': [43.89, -0.50], '41': [47.59, 1.33], '42': [45.44, 4.39], '43': [45.04, 3.88],
            '44': [47.22, -1.55], '45': [47.90, 2.33], '46': [44.65, 1.57], '47': [44.40, 0.62],
            '48': [44.52, 3.50], '49': [47.47, -0.55], '50': [49.12, -1.31], '51': [49.05, 4.03],
            '52': [48.11, 5.14], '53': [48.07, -0.77], '54': [48.69, 6.18], '55': [49.16, 5.38],
            '56': [47.75, -2.76], '57': [49.12, 6.68], '58': [47.22, 3.52], '59': [50.63, 3.06],
            '60': [49.42, 2.42], '61': [48.65, 0.09], '62': [50.51, 2.38], '63': [45.78, 3.08],
            '64': [43.30, -0.37], '65': [43.23, 0.08], '66': [42.70, 2.89], '67': [48.58, 7.75],
            '68': [47.75, 7.33], '69': [45.76, 4.84], '70': [47.63, 6.16], '71': [46.67, 4.56],
            '72': [48.01, 0.20], '73': [45.56, 6.38], '74': [46.06, 6.36], '75': [48.86, 2.35],
            '76': [49.54, 0.89], '77': [48.61, 2.89], '78': [48.80, 1.82], '79': [46.67, -0.41],
            '80': [49.89, 2.30], '81': [43.78, 2.15], '82': [44.02, 1.36], '83': [43.47, 6.24],
            '84': [44.06, 5.13], '85': [46.67, -1.43], '86': [46.58, 0.33], '87': [45.83, 1.26],
            '88': [48.18, 6.45], '89': [47.80, 3.57], '90': [47.64, 6.86], '91': [48.63, 2.30],
            '92': [48.89, 2.23], '93': [48.91, 2.45], '94': [48.79, 2.48], '95': [49.04, 2.24]
        };

        return centers[deptCode] || null;
    }

    /**
     * Format number with thousands separator
     */
    formatNumber(num) {
        return Math.round(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }

    /**
     * Clean up when modal is closed
     */
    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
        this.markers = [];

        const container = document.getElementById('dept-map-container');
        if (container) {
            container.remove();
        }
    }
}

// Initialize the department map module
const departmentMap = new DepartmentMap();

// Watch for changes in selectedDeptInscrits to show/hide map
if (typeof Alpine !== 'undefined') {
    document.addEventListener('alpine:init', () => {
        // Hook into Alpine.js reactivity
        Alpine.effect(() => {
            // Wait for the modal to be rendered
            setTimeout(() => {
                const modal = document.querySelector('[x-show="selectedDeptInscrits !== null"]');
                if (modal && modal.style.display !== 'none') {
                    // Get the current department data from Alpine
                    const appData = Alpine.$data(document.querySelector('[x-data]'));
                    if (appData && appData.selectedDeptInscrits) {
                        departmentMap.init(
                            appData.selectedDeptInscrits.dept,
                            appData.selectedDeptInscrits.cibles_1000plus || []
                        );
                    }
                } else {
                    // Modal is closed, clean up
                    departmentMap.destroy();
                }
            }, 100);
        });
    });
}

// Export for use in other modules
window.DepartmentMap = departmentMap;
