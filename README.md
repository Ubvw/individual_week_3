# Bataan Smart Route Optimizer

A web-based route optimization system for Bataan, Philippines that helps drivers avoid flood-prone areas while maintaining efficient path finding.

## Features

- **Real-time Route Optimization**: Uses OpenRouteService API for accurate road-based routing
- **Flood Risk Assessment**: Overlays flood zone data from Bataan shapefiles
- **Interactive Map Interface**: Leaflet.js map with click-to-select start/end points
- **Risk Scoring**: Color-coded routes based on flood intersection risk (Green/Yellow/Red)
- **Visual Feedback**: Real-time distance, ETA, and flood intersection warnings

## Quick Start

### Prerequisites

- Python 3.12+
- OpenRouteService API key (free tier available)
- Bataan flood zone data (GeoJSON format)

### Installation

1. **Clone and setup**:
```bash
git clone <repository-url>
cd week_3_indiv
uv sync
```

2. **Configure API key**:
Create a `.env` file in the project root:
```bash
ORS_API_KEY=your_openrouteservice_api_key_here
```

3. **Start the backend**:
```bash
uv run uvicorn app:app --reload
```

4. **Open the frontend**:
Open `index.html` in your browser or serve it statically.

## Usage

1. **Set Route Points**:
   - Click on the map to set start point, then end point
   - Or manually enter coordinates in the input fields

2. **Optimize Route**:
   - Click "Optimize Route" to calculate the best path
   - View results in the sidebar: distance, ETA, risk score, flood intersections

3. **Interpret Results**:
   - **Green Route** (0-3): Low risk, safe path
   - **Yellow Route** (4-6): Medium risk, caution advised
   - **Red Route** (7-10): High risk, alternative recommended

## API Endpoints

### `GET /health`
Returns system status and provider information.

### `GET /flood-zones`
Returns GeoJSON flood zone data for Bataan province.

### `POST /optimize-route`
Optimizes route between two points with flood risk assessment.

**Request**:
```json
{
  "start": {"lat": 14.4326, "lng": 120.4859},
  "end": {"lat": 14.6761, "lng": 120.5383}
}
```

**Response**:
```json
{
  "route_id": "uuid-string",
  "geometry": [...],
  "risk_score": 0.51,
  "flood_intersections": 3,
  "distance_km": 46.71,
  "estimated_time_minutes": 50,
  "warnings": ["Route passes through 3 flood-prone areas"],
  "alternative_available": false
}
```

## Technical Architecture

- **Backend**: FastAPI with Python
- **Routing Engine**: OpenRouteService API
- **Data Processing**: GeoPandas for flood zone analysis
- **Frontend**: HTML + Leaflet.js + Vanilla JavaScript
- **Risk Algorithm**: Intersection-based scoring with flood zone overlap

## Configuration

### Environment Variables

- `ORS_API_KEY`: OpenRouteService API key (required)

### Data Files

- `flood_prone.geojson`: Bataan flood zone polygons (EPSG:4326)
- `Bataan/`: Original shapefile data (converted to GeoJSON)

## Development

### Project Structure
```
week_3_indiv/
├── app.py                # FastAPI backend
├── index.html            # Frontend interface
├── main.py               # Shapefile to GeoJSON converter
├── flood_prone.geojson   # Flood zone data
├── pyproject.toml        # Dependencies
└── .env                  # API configuration
```

### Performance

- **Route Calculation**: < 3 seconds for typical Bataan routes
- **Concurrent Users**: Supports multiple simultaneous requests
- **Caching**: LRU cache reduces repeated ORS API calls

## Demo Scenario

Navigate from Mariveles Port (14.4167°N, 120.4833°E) to Bagac Town Center (14.6000°N, 120.4333°E) to see flood zone avoidance and risk assessment in action.


*Built with FastAPI, OpenRouteService, and Leaflet.js*
