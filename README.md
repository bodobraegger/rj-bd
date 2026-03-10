# 🌊 Balneabilidade Rio

A small, fast website showing real-time beach water quality in Rio de Janeiro.

## Features

- ☆ **Interactive Map**: Color-coded beaches based on water quality
- ☆ **Sortable List**: View beaches alphabetically, by status, or favorites
- ☆ **Favorites**: Save your preferred beaches (localStorage)
- ☆ **Weather Alerts**: Warnings when storms may affect water quality
- ☆ **Ultra-Fast**: <50KB bundle, pure vanilla JS, no framework overhead

## Development:

```bash
# Serve locally (Python)
python -m http.server 8000

# Or use any static server
npx serve .
```

Visit `http://localhost:8000`

## Data Sources

### Current Implementation
The app currently uses mock data. To integrate real APIs:

### 1. INEA Balneability Data
Rio's environmental institute publishes weekly beach water quality reports:

**Option A: Official INEA API** (if available)
```javascript
// In app.js, replace fetchBeachData():
async function fetchBeachData() {
    const response = await fetch('http://www.inea.rj.gov.br/api/balneabilidade');
    const data = await response.json();
    beachData = transformIneaData(data);
    updateMapMarkers();
}
```

**Option B: Data.Rio Portal**
Check https://www.data.rio/ for open datasets:
```javascript
const response = await fetch('https://api.data.rio/datasets/balneabilidade');
```

**Option C: Prefeitura Rio APIs**
Explore repositories at https://github.com/prefeitura-rio for potential APIs:
- `queries-rj-iplanrio` - Data queries
- `pipelines_rj_iplanrio` - Data pipelines
- Check their documentation for available endpoints

### 2. Weather Data
For storm impact warnings:

**Option A: OpenWeatherMap** (Free tier)
```javascript
async function checkWeatherAlert() {
    const API_KEY = 'your-key';
    const response = await fetch(
        `https://api.openweathermap.org/data/2.5/weather?lat=-22.9711&lon=-43.2044&appid=${API_KEY}`
    );
    const data = await response.json();
    
    // Check for heavy rain in last 48h
    const hasHeavyRain = data.rain && data.rain['1h'] > 10;
    if (hasHeavyRain) {
        document.getElementById('weatherAlert').classList.add('show');
    }
}
```

**Option B: INMET (Brazil's National Weather Service)**
```javascript
const response = await fetch('https://apitempo.inmet.gov.br/estacao/dados/...');
```

## File Structure

```
/
├── index.html      # Main HTML (8KB with inline CSS)
├── app.js          # Core logic (15KB)
├── README.md       # Documentation
└── api.js          # API integration (optional, 3KB)
```

## Size Budget

- HTML + inline CSS: ~8KB
- JavaScript (app.js): ~15KB  
- Leaflet CDN: External (doesn't count)
- **Total Bundle: ~23KB** ✅ (<50KB target)

## Integration TODO

1. **Find Real API Endpoint**
   - Check INEA website for API docs
   - Explore Data.Rio portal
   - Contact Prefeitura Rio for API access

2. **API Integration**
   - Replace `BEACHES_DATA` constant
   - Implement `transformApiData()` function
   - Add error handling for failed requests

3. **Weather Integration**
   - Get OpenWeatherMap or INMET API key
   - Implement rainfall detection logic
   - Set appropriate thresholds (e.g., >10mm in 48h)

4. **Enhancements**
   - Add service worker for offline support
   - Implement data caching
   - Add historical trend view

## API Data Format

Expected format for beach data:
```javascript
{
    id: number,
    name: string,
    lat: number,
    lng: number,
    status: 'proper' | 'warning' | 'improper' | 'unknown',
    zone: string,
    lastUpdate: ISO_DATE_STRING
}
```

## Performance Optimizations

- ✅ No build step required
- ✅ CSS inlined in HTML
- ✅ External libraries loaded from CDN
- ✅ LocalStorage for favorites (no backend needed)
- ✅ Debounced scroll/resize events
- ✅ Lazy popup rendering
- ✅ GPU-accelerated CSS transforms

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers (iOS Safari, Chrome Mobile)
- ES6+ JavaScript required

## Contributing

1. Fork the repository
2. Integrate real API endpoints
3. Test thoroughly
4. Submit pull request

## License

MIT

## Resources

- INEA: http://www.inea.rj.gov.br/
- Data.Rio: https://www.data.rio/
- Prefeitura Rio GitHub: https://github.com/prefeitura-rio
- Leaflet.js: https://leafletjs.com/
