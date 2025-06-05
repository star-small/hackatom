from flask import Flask, request, jsonify, render_template_string
import math
import json
import requests
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'nuclear-site-selection-key-2025'

# Database setup
def init_db():
    conn = sqlite3.connect('nuclear_sites.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS site_evaluations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  latitude REAL,
                  longitude REAL,
                  overall_score INTEGER,
                  evaluation_data TEXT,
                  timestamp DATETIME)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS criteria_weights
                 (criterion_name TEXT PRIMARY KEY,
                  weight REAL,
                  description TEXT)''')
    
    # Insert default weights if not exists
    default_weights = [
        ('population_access', 0.15, 'Distance to major population centers'),
        ('water_supply', 0.12, 'Proximity to reliable water sources'),
        ('seismic_safety', 0.10, 'Geological stability and earthquake risk'),
        ('environmental', 0.08, 'Environmental protection requirements'),
        ('grid_integration', 0.10, 'Electrical grid connectivity'),
        ('transportation', 0.08, 'Road and rail infrastructure'),
        ('industrial_demand', 0.12, 'Industrial electricity demand'),
        ('economic_viability', 0.10, 'Construction and operational costs'),
        ('public_acceptance', 0.05, 'Community support levels'),
        ('emergency_preparedness', 0.10, 'Emergency response capabilities')
    ]
    
    for criterion, weight, desc in default_weights:
        c.execute('INSERT OR IGNORE INTO criteria_weights VALUES (?, ?, ?)', 
                 (criterion, weight, desc))
    
    conn.commit()
    conn.close()

# Geographic data
MAJOR_CITIES = [
    {"name": "Almaty", "lat": 43.2220, "lng": 76.8512, "population": 2000000, "industrial_factor": 0.8},
    {"name": "Nur-Sultan", "lat": 51.1694, "lng": 71.4491, "population": 1200000, "industrial_factor": 0.6},
    {"name": "Shymkent", "lat": 42.3417, "lng": 69.5901, "population": 1000000, "industrial_factor": 0.7},
    {"name": "Aktobe", "lat": 50.2839, "lng": 57.1670, "population": 500000, "industrial_factor": 0.5},
    {"name": "Taraz", "lat": 42.9000, "lng": 71.3667, "population": 400000, "industrial_factor": 0.4},
    {"name": "Pavlodar", "lat": 52.2856, "lng": 76.9749, "population": 350000, "industrial_factor": 0.6},
    {"name": "Ust-Kamenogorsk", "lat": 49.9483, "lng": 82.6283, "population": 300000, "industrial_factor": 0.5},
    {"name": "Karaganda", "lat": 49.8047, "lng": 73.1094, "population": 500000, "industrial_factor": 0.9},
    {"name": "Aktau", "lat": 43.6500, "lng": 51.2000, "population": 200000, "industrial_factor": 0.8},
    {"name": "Atyrau", "lat": 47.1164, "lng": 51.8830, "population": 300000, "industrial_factor": 0.7}
]

WATER_SOURCES = [
    {"name": "Lake Balkhash", "lat": 46.8, "lng": 74.5, "type": "Large Lake", "reliability": 95, "flow_rate": 1000},
    {"name": "Caspian Sea", "lat": 44.0, "lng": 51.0, "type": "Sea", "reliability": 100, "flow_rate": 10000},
    {"name": "Lake Alakol", "lat": 46.2, "lng": 81.5, "type": "Lake", "reliability": 80, "flow_rate": 200},
    {"name": "Irtysh River", "lat": 50.0, "lng": 82.0, "type": "River", "reliability": 85, "flow_rate": 500},
    {"name": "Ishim River", "lat": 51.5, "lng": 71.0, "type": "River", "reliability": 70, "flow_rate": 150},
    {"name": "Ili River", "lat": 43.5, "lng": 77.0, "type": "River", "reliability": 85, "flow_rate": 300}
]

EXCLUSION_ZONES = [
    {"name": "Altyn-Emel National Park", "lat": 43.7, "lng": 78.5, "radius": 50, "type": "environmental"},
    {"name": "Charyn Canyon", "lat": 43.4, "lng": 79.0, "radius": 30, "type": "environmental"},
    {"name": "High Seismic Zone (East)", "lat": 49.0, "lng": 83.0, "radius": 100, "type": "geological"},
    {"name": "Almaty Metro Area", "lat": 43.2, "lng": 76.8, "radius": 30, "type": "population"},
    {"name": "Nur-Sultan Metro Area", "lat": 51.1694, "lng": 71.4491, "radius": 30, "type": "population"}
]

# Seismic zones definition
SEISMIC_ZONES = [
    {"region": "East Kazakhstan", "lat_range": [49, 51], "lng_range": [80, 87], "risk_level": "High", "score": 30},
    {"region": "Southeast", "lat_range": [42, 45], "lng_range": [75, 80], "risk_level": "Medium-High", "score": 50},
    {"region": "West Kazakhstan", "lat_range": [46, 52], "lng_range": [46, 60], "risk_level": "Low", "score": 85},
    {"region": "North Kazakhstan", "lat_range": [50, 55], "lng_range": [60, 80], "risk_level": "Low", "score": 85},
    {"region": "Central Kazakhstan", "lat_range": [45, 50], "lng_range": [65, 75], "risk_level": "Medium", "score": 70}
]

# Utility functions
def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lng/2) * math.sin(delta_lng/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def find_nearest_entity(lat, lng, entities):
    """Find the nearest entity from a list"""
    nearest = None
    min_distance = float('inf')
    
    for entity in entities:
        distance = calculate_distance(lat, lng, entity['lat'], entity['lng'])
        if distance < min_distance:
            min_distance = distance
            nearest = {**entity, 'distance': distance}
    
    return nearest

def check_exclusion_zones(lat, lng):
    """Check if location is in any exclusion zone"""
    for zone in EXCLUSION_ZONES:
        distance = calculate_distance(lat, lng, zone['lat'], zone['lng'])
        if distance < zone['radius']:
            return {
                'in_zone': True,
                'zone_name': zone['name'],
                'zone_type': zone['type'],
                'distance': distance
            }
    
    return {'in_zone': False, 'distance': None}

def calculate_seismic_risk(lat, lng):
    """Calculate seismic risk based on location"""
    for zone in SEISMIC_ZONES:
        if (zone['lat_range'][0] <= lat <= zone['lat_range'][1] and 
            zone['lng_range'][0] <= lng <= zone['lng_range'][1]):
            return {
                'region': zone['region'],
                'level': zone['risk_level'],
                'score': zone['score']
            }
    
    # Default medium risk
    return {'region': 'Unknown', 'level': 'Medium', 'score': 60}

def get_elevation_data(lat, lng):
    """Get elevation data from external API"""
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lng}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['results'][0]['elevation']
    except:
        pass
    return 500  # Default elevation

def calculate_grid_integration_score(lat, lng, nearest_city):
    """Calculate grid integration feasibility"""
    # Base score on distance to major cities and existing infrastructure
    distance_penalty = min(nearest_city['distance'] * 0.15, 50)
    base_score = 100 - distance_penalty
    
    # Bonus for high-demand industrial areas
    if nearest_city['population'] > 500000:
        base_score += 10
    
    # Consider existing transmission infrastructure (simplified)
    if nearest_city['name'] in ['Almaty', 'Nur-Sultan', 'Shymkent']:
        base_score += 15
    
    return min(100, max(0, base_score))

def calculate_transportation_score(lat, lng, nearest_city):
    """Calculate transportation infrastructure score"""
    # Simplified model based on proximity to major cities
    base_score = max(0, 100 - nearest_city['distance'] * 0.2)
    
    # Bonus for cities with good infrastructure
    infrastructure_bonus = {
        'Almaty': 20, 'Nur-Sultan': 15, 'Shymkent': 15,
        'Karaganda': 10, 'Aktobe': 10, 'Pavlodar': 10
    }
    
    bonus = infrastructure_bonus.get(nearest_city['name'], 0)
    return min(100, base_score + bonus)

def calculate_economic_viability(lat, lng, nearest_city, nearest_water, seismic_risk):
    """Calculate economic viability score"""
    base_score = 80
    
    # Distance penalties
    city_penalty = min(nearest_city['distance'] * 0.1, 30)
    water_penalty = min(nearest_water['distance'] * 0.2, 20)
    
    # Seismic risk penalty
    seismic_penalty = (100 - seismic_risk['score']) * 0.3
    
    # Industrial demand bonus
    industrial_bonus = nearest_city['industrial_factor'] * 20
    
    final_score = base_score - city_penalty - water_penalty - seismic_penalty + industrial_bonus
    return max(0, min(100, final_score))

@app.route('/')
def index():
    """Serve the main application"""
    with open('nuclear_site_app.html', 'r') as f:
        html_content = f.read()
    return render_template_string(html_content)

@app.route('/api/analyze_site', methods=['POST'])
def analyze_site():
    """Analyze a potential nuclear plant site"""
    try:
        data = request.json
        lat = float(data['latitude'])
        lng = float(data['longitude'])
        
        # Validate coordinates are in Kazakhstan
        if not (40.5 <= lat <= 55.5 and 46.5 <= lng <= 87.5):
            return jsonify({'error': 'Coordinates outside Kazakhstan'}), 400
        
        # Find nearest entities
        nearest_city = find_nearest_entity(lat, lng, MAJOR_CITIES)
        nearest_water = find_nearest_entity(lat, lng, WATER_SOURCES)
        
        # Check constraints
        exclusion_check = check_exclusion_zones(lat, lng)
        seismic_risk = calculate_seismic_risk(lat, lng)
        
        # Get additional data
        elevation = get_elevation_data(lat, lng)
        
        # Calculate detailed criteria scores
        criteria = []
        
        # Population Access
        pop_score = max(0, 100 - nearest_city['distance'] * 0.2)
        criteria.append({
            'name': 'Population Access',
            'score': pop_score,
            'weight': 0.15,
            'details': f"{nearest_city['distance']:.0f}km from {nearest_city['name']} ({nearest_city['population']:,} people)"
        })
        
        # Water Supply
        water_score = max(0, 100 - nearest_water['distance'] * 0.5) * (nearest_water['reliability'] / 100)
        criteria.append({
            'name': 'Water Supply',
            'score': water_score,
            'weight': 0.12,
            'details': f"{nearest_water['distance']:.0f}km from {nearest_water['name']} ({nearest_water['reliability']}% reliable)"
        })
        
        # Seismic Safety
        criteria.append({
            'name': 'Seismic Safety',
            'score': seismic_risk['score'],
            'weight': 0.10,
            'details': f"{seismic_risk['level']} risk in {seismic_risk['region']}"
        })
        
        # Environmental Impact
        env_score = 20 if exclusion_check['in_zone'] else 90
        env_details = f"In {exclusion_check['zone_name']}" if exclusion_check['in_zone'] else "Clear area"
        criteria.append({
            'name': 'Environmental Impact',
            'score': env_score,
            'weight': 0.08,
            'details': env_details
        })
        
        # Grid Integration
        grid_score = calculate_grid_integration_score(lat, lng, nearest_city)
        criteria.append({
            'name': 'Grid Integration',
            'score': grid_score,
            'weight': 0.10,
            'details': f"Transmission infrastructure to {nearest_city['name']}"
        })
        
        # Transportation Infrastructure
        transport_score = calculate_transportation_score(lat, lng, nearest_city)
        criteria.append({
            'name': 'Transportation',
            'score': transport_score,
            'weight': 0.08,
            'details': f"Road/rail access via {nearest_city['name']}"
        })
        
        # Industrial Demand
        industrial_score = 50 + (nearest_city['industrial_factor'] * 40) - (nearest_city['distance'] * 0.1)
        industrial_score = max(0, min(100, industrial_score))
        criteria.append({
            'name': 'Industrial Demand',
            'score': industrial_score,
            'weight': 0.12,
            'details': f"Industrial factor: {nearest_city['industrial_factor']:.1f}"
        })
        
        # Economic Viability
        econ_score = calculate_economic_viability(lat, lng, nearest_city, nearest_water, seismic_risk)
        criteria.append({
            'name': 'Economic Viability',
            'score': econ_score,
            'weight': 0.10,
            'details': f"Cost-benefit analysis score"
        })
        
        # Public Acceptance (based on 2024 referendum)
        criteria.append({
            'name': 'Public Acceptance',
            'score': 71,
            'weight': 0.05,
            'details': "71% referendum support (Oct 2024)"
        })
        
        # Emergency Preparedness
        emergency_score = max(0, 100 - nearest_city['distance'] * 0.3)
        criteria.append({
            'name': 'Emergency Preparedness',
            'score': emergency_score,
            'weight': 0.10,
            'details': f"Emergency services in {nearest_city['name']}"
        })
        
        # Calculate overall score
        weighted_sum = sum(c['score'] * c['weight'] for c in criteria)
        total_weight = sum(c['weight'] for c in criteria)
        overall_score = round(weighted_sum / total_weight)
        
        # Additional analysis
        cost_estimate = calculate_cost_estimate(lat, lng, nearest_city, nearest_water, seismic_risk)
        timeline_estimate = calculate_timeline(lat, lng, overall_score)
        
        # Store evaluation in database
        store_evaluation(lat, lng, overall_score, {
            'criteria': criteria,
            'nearest_city': nearest_city,
            'nearest_water': nearest_water,
            'seismic_risk': seismic_risk,
            'exclusion_check': exclusion_check,
            'cost_estimate': cost_estimate,
            'timeline_estimate': timeline_estimate
        })
        
        return jsonify({
            'overall_score': overall_score,
            'criteria': criteria,
            'location_details': {
                'coordinates': {'lat': lat, 'lng': lng},
                'nearest_city': nearest_city,
                'nearest_water': nearest_water,
                'elevation': elevation
            },
            'risk_assessment': {
                'seismic': seismic_risk,
                'environmental': exclusion_check,
                'population': {
                    'safe_distance': nearest_city['distance'] >= 30,
                    'distance': nearest_city['distance']
                }
            },
            'economic_analysis': {
                'cost_estimate': cost_estimate,
                'timeline': timeline_estimate,
                'annual_revenue_estimate': calculate_revenue_estimate(nearest_city, industrial_score)
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_cost_estimate(lat, lng, nearest_city, nearest_water, seismic_risk):
    """Calculate construction cost estimate"""
    base_cost = 10.0  # Billion USD
    
    # Location factors
    remote_penalty = min(nearest_city['distance'] * 0.01, 2.0)
    water_penalty = min(nearest_water['distance'] * 0.005, 1.0)
    seismic_penalty = (100 - seismic_risk['score']) * 0.02
    
    total_cost = base_cost + remote_penalty + water_penalty + seismic_penalty
    
    return {
        'total_cost_billion_usd': round(total_cost, 1),
        'breakdown': {
            'base_cost': base_cost,
            'location_premium': remote_penalty,
            'water_infrastructure': water_penalty,
            'seismic_reinforcement': seismic_penalty
        }
    }

def calculate_timeline(lat, lng, overall_score):
    """Calculate project timeline"""
    base_timeline = 10  # years
    
    # Complexity factors
    if overall_score >= 80:
        complexity_factor = 0.9
    elif overall_score >= 60:
        complexity_factor = 1.0
    else:
        complexity_factor = 1.2
    
    total_timeline = base_timeline * complexity_factor
    
    return {
        'total_years': round(total_timeline, 1),
        'phases': {
            'site_preparation': 2,
            'construction': round(total_timeline - 4, 1),
            'commissioning': 2
        }
    }

def calculate_revenue_estimate(nearest_city, industrial_score):
    """Calculate annual revenue estimate"""
    base_revenue = 800  # Million USD
    
    # Market factors
    population_factor = min(nearest_city['population'] / 1000000, 2.0)
    industrial_factor = industrial_score / 100
    
    annual_revenue = base_revenue * (0.5 + 0.3 * population_factor + 0.2 * industrial_factor)
    
    return round(annual_revenue, 0)

def store_evaluation(lat, lng, score, data):
    """Store evaluation in database"""
    conn = sqlite3.connect('nuclear_sites.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO site_evaluations 
                 (latitude, longitude, overall_score, evaluation_data, timestamp)
                 VALUES (?, ?, ?, ?, ?)''',
             (lat, lng, score, json.dumps(data), datetime.now()))
    
    conn.commit()
    conn.close()

@app.route('/api/historical_evaluations', methods=['GET'])
def get_historical_evaluations():
    """Get historical site evaluations"""
    conn = sqlite3.connect('nuclear_sites.db')
    c = conn.cursor()
    
    c.execute('''SELECT latitude, longitude, overall_score, timestamp 
                 FROM site_evaluations 
                 ORDER BY timestamp DESC LIMIT 50''')
    
    evaluations = []
    for row in c.fetchall():
        evaluations.append({
            'latitude': row[0],
            'longitude': row[1],
            'score': row[2],
            'timestamp': row[3]
        })
    
    conn.close()
    return jsonify(evaluations)

@app.route('/api/update_criteria_weights', methods=['POST'])
def update_criteria_weights():
    """Update criteria weights"""
    try:
        weights = request.json
        
        conn = sqlite3.connect('nuclear_sites.db')
        c = conn.cursor()
        
        for criterion, weight in weights.items():
            c.execute('''UPDATE criteria_weights 
                        SET weight = ? 
                        WHERE criterion_name = ?''', (weight, criterion))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export_evaluation/<int:evaluation_id>')
def export_evaluation(evaluation_id):
    """Export detailed evaluation report"""
    conn = sqlite3.connect('nuclear_sites.db')
    c = conn.cursor()
    
    c.execute('''SELECT * FROM site_evaluations WHERE id = ?''', (evaluation_id,))
    row = c.fetchone()
    
    if not row:
        return jsonify({'error': 'Evaluation not found'}), 404
    
    evaluation_data = json.loads(row[4])
    
    report = {
        'id': row[0],
        'coordinates': {'latitude': row[1], 'longitude': row[2]},
        'overall_score': row[3],
        'timestamp': row[5],
        'detailed_analysis': evaluation_data
    }
    
    conn.close()
    return jsonify(report)

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Create the HTML file if it doesn't exist
    if not os.path.exists('nuclear_site_app.html'):
        print("Please save the HTML content as 'nuclear_site_app.html' in the same directory")
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
