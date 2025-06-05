## Installation

1. Create a virtual environment:
```bash
python -m venv nuclear_app_env
source nuclear_app_env/bin/activate  # On Windows: nuclear_app_env\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Save the HTML content as 'nuclear_site_app.html' in the same directory as app.py

## Running the Application

```bash
python app.py
```

Then open your browser to: http://localhost:5000

## API Endpoints

### POST /api/analyze_site
Analyze a nuclear plant site location
```json
{
  "latitude": 46.8,
  "longitude": 74.5
}
```

### GET /api/historical_evaluations
Get list of previous site evaluations

### POST /api/update_criteria_weights
Update scoring criteria weights
```json
{
  "population_access": 0.15,
  "water_supply": 0.12,
  "seismic_safety": 0.10
}
```

### GET /api/export_evaluation/<id>
Export detailed evaluation report

## Features

### Interactive Map
- Click anywhere in Kazakhstan to evaluate site
- Switch between Standard, Satellite, and Terrain views
- Real-time visualization of major cities, water sources, and exclusion zones

### Comprehensive Scoring
- 10 detailed criteria based on nuclear site selection best practices
- Weighted scoring system with customizable weights
- Real-time calculations using geographic data

### Visualizations
- Overall site suitability score with gauge chart
- Criteria breakdown pie chart
- Comparative analysis bar chart
- Risk assessment indicators

### Data Integration
- Geographic distance calculations
- Population and industrial data
- Water source reliability metrics
- Seismic risk zone mapping
- Environmental exclusion zone checking

### Database Storage
- SQLite database for storing evaluations
- Historical evaluation tracking
- Criteria weight customization
- Export functionality for detailed reports

## Advanced Features

### Real-time Calculations
- Haversine formula for precise distance calculations
- Multi-factor scoring algorithms
- Economic viability modeling
- Construction cost estimation

### Professional UI
- Modern Tailwind CSS design
- Responsive layout for all devices
- Interactive charts using Chart.js
- Professional color schemes and animations

### Extensibility
- Modular scoring system
- Easy to add new criteria
- API-first architecture
- Database-backed configuration

## Technical Architecture

### Frontend
- HTML5 with Tailwind CSS
- Leaflet.js for interactive mapping
- Chart.js for data visualization
- Vanilla JavaScript for interactivity

### Backend
- Flask web framework
- SQLite database
- RESTful API design
- Real-time data processing

### Integration
- OpenStreetMap for base mapping
- External elevation API
- Geographic data calculations
- Multi-source data aggregation

This application provides a comprehensive tool for nuclear power plant site selection specifically tailored for Kazakhstan, incorporating all the criteria discussed in your research while providing an intuitive and professional user interface.
