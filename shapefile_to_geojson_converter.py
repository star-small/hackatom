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

# Global variable to store exclusion zones
EXCLUSION_ZONES = []


def load_exclusion_zones():
    """Load exclusion zones from WDPA shapefile or other formats"""
    global EXCLUSION_ZONES
    try:
        EXCLUSION_ZONES = []

        # Try to load from WDPA shapefile first (best option)
        if load_wdpa_shapefile():
            print(f"✅ Successfully loaded {
                  len(EXCLUSION_ZONES)} protected areas from WDPA shapefile")
            return

        # Fallback to CSV with approximations
        if load_wdpa_csv():
            print(f"⚠️  Loaded {
                  len(EXCLUSION_ZONES)} protected areas from CSV (with approximated boundaries)")
            return

        # Fallback to custom exclusion zones
        if load_custom_exclusion_zones():
            print(f"ℹ️  Loaded {len(EXCLUSION_ZONES)} custom exclusion zones")
            return

        # Final fallback to defaults
        create_default_exclusion_zones()
        print(f"⚠️  Using {len(EXCLUSION_ZONES)} default exclusion zones")

    except Exception as e:
        print(f"❌ Error loading exclusion zones: {e}")
        create_default_exclusion_zones()


def load_wdpa_shapefile():
    """Load real WDPA polygon data from shapefile"""
    global EXCLUSION_ZONES

    shapefile_path = "WDPA_WDOECM_Jun2025_Public_KAZ_shp-polygons.shp"

    if not os.path.exists(shapefile_path):
        print("📁 WDPA shapefile not found, trying alternatives...")
        return False

    try:
        import geopandas as gpd
        print("🗺️  Loading WDPA Kazakhstan shapefile...")

        # Read the shapefile
        gdf = gpd.read_file(shapefile_path)

        # Convert to WGS84 if not already
        if gdf.crs != 'EPSG:4326':
            print("🔄 Converting to WGS84 coordinate system...")
            gdf = gdf.to_crs('EPSG:4326')

        print(f"📊 Processing {len(gdf)} protected areas...")

        # Convert each protected area to our format
        for _, row in gdf.iterrows():
            name = row.get('NAME', 'Unknown')
            orig_name = row.get('ORIG_NAME', '')
            desig_eng = row.get('DESIG_ENG', '')
            desig = row.get('DESIG', '')
            iucn_cat = row.get('IUCN_CAT', '')
            area_km2 = float(row.get('GIS_AREA', 0) or 0)
            status = row.get('STATUS', '')
            wdpa_id = row.get('WDPAID', '')

            # Skip if no name or geometry
            if not name or not row.geometry:
                continue

            # Determine restriction level
            restriction_level = determine_restriction_level(
                desig_eng, desig, iucn_cat, area_km2)

            # Create GeoJSON-style feature with real geometry
            feature = {
                'type': 'Feature',
                'properties': {
                    'name': name,
                    'orig_name': orig_name,
                    'type': map_designation_to_type(desig_eng, desig),
                    'description': f"{desig_eng or desig} | IUCN: {iucn_cat} | Area: {area_km2:.1f} km² | Status: {status}",
                    'restriction_level': restriction_level,
                    'area_km2': area_km2,
                    'iucn_category': iucn_cat,
                    'designation': desig_eng or desig,
                    'status': status,
                    'wdpa_id': wdpa_id,
                    'wdpa_source': True,
                    'geometry_source': 'shapefile'
                },
                'geometry': row.geometry.__geo_interface__
            }
            EXCLUSION_ZONES.append(feature)

        # Show statistics
        show_loading_statistics()
        return True

    except ImportError:
        print("❌ geopandas not installed. Install with: pip install geopandas")
        return False
    except Exception as e:
        print(f"❌ Error loading shapefile: {e}")
        return False


def load_wdpa_csv():
    """Fallback: Load WDPA CSV data with approximated boundaries"""
    global EXCLUSION_ZONES

    csv_path = "WDPA_WDOECM_Jun2025_Public_KAZ_csv.csv"

    if not os.path.exists(csv_path):
        return False

    try:
        import csv
        print("📄 Loading WDPA CSV data (creating approximated boundaries)...")

        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)

            for row in csv_reader:
                name = row.get('NAME', '').strip()
                orig_name = row.get('ORIG_NAME', '').strip()
                desig_eng = row.get('DESIG_ENG', '').strip()
                desig = row.get('DESIG', '').strip()
                iucn_cat = row.get('IUCN_CAT', '').strip()
                area_km2 = float(row.get('GIS_AREA', 0) or 0)
                status = row.get('STATUS', '').strip()
                wdpa_id = row.get('WDPAID', '')

                if not name:
                    continue

                # Determine restriction level
                restriction_level = determine_restriction_level(
                    desig_eng, desig, iucn_cat, area_km2)

                # Create approximated coordinates
                coordinates = create_approximated_coordinates(name, area_km2)

                if coordinates:
                    feature = {
                        'type': 'Feature',
                        'properties': {
                            'name': name,
                            'orig_name': orig_name,
                            'type': map_designation_to_type(desig_eng, desig),
                            'description': f"{desig_eng or desig} | IUCN: {iucn_cat} | Area: {area_km2:.1f} km² | Status: {status} | ⚠️ Approximated boundary",
                            'restriction_level': restriction_level,
                            'area_km2': area_km2,
                            'iucn_category': iucn_cat,
                            'designation': desig_eng or desig,
                            'status': status,
                            'wdpa_id': wdpa_id,
                            'wdpa_source': True,
                            'geometry_source': 'approximated'
                        },
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [coordinates]
                        }
                    }
                    EXCLUSION_ZONES.append(feature)

        return True

    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return False


def load_custom_exclusion_zones():
    """Load custom exclusion zones from CSV or GeoJSON"""
    global EXCLUSION_ZONES

    # Try GeoJSON first
    if os.path.exists('exclusion_zones.geojson'):
        try:
            with open('exclusion_zones.geojson', 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
                EXCLUSION_ZONES = geojson_data['features']
                return True
        except Exception as e:
            print(f"Error loading GeoJSON: {e}")

    # Try custom CSV
    if os.path.exists('exclusion_zones.csv'):
        try:
            import csv
            with open('exclusion_zones.csv', 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                for row in csv_reader:
                    coordinates_str = row.get('coordinates', '').strip()
                    if not coordinates_str:
                        continue

                    coordinates = parse_coordinates(coordinates_str)
                    if coordinates:
                        feature = {
                            'type': 'Feature',
                            'properties': {
                                'name': row.get('name', 'Unknown Zone'),
                                'type': row.get('type', 'environmental'),
                                'description': row.get('description', ''),
                                'restriction_level': row.get('restriction_level', 'high').lower(),
                                'geometry_source': 'custom'
                            },
                            'geometry': {
                                'type': 'Polygon',
                                'coordinates': [coordinates]
                            }
                        }
                        EXCLUSION_ZONES.append(feature)
            return len(EXCLUSION_ZONES) > 0
        except Exception as e:
            print(f"Error loading custom CSV: {e}")

    return False


def determine_restriction_level(desig_eng, desig, iucn_cat, area_km2):
    """Determine restriction level based on protected area characteristics"""
    designation = (desig_eng or desig or '').lower()

    # Strict protection (high restriction) - No nuclear development
    if any(term in designation for term in ['nature reserve', 'world heritage', 'ramsar']):
        return 'high'

    # IUCN Category I (strict protection)
    if iucn_cat in ['Ia', 'Ib']:
        return 'high'

    # IUCN Category II (national parks) - usually high restriction for NPP
    if iucn_cat == 'II':
        return 'high'

    # Large areas (>1000 km2) - usually significant restrictions
    if area_km2 > 1000:
        return 'medium'

    # IUCN Category III, IV (natural monuments, habitat management)
    if iucn_cat in ['III', 'IV']:
        return 'medium'

    # IUCN Category V, VI (landscape protection, sustainable use)
    if iucn_cat in ['V', 'VI']:
        return 'low'

    # Zakaznik (wildlife sanctuary) - usually medium restriction
    if 'zakaznik' in designation:
        return 'medium'

    # Default to medium for protected areas
    return 'medium'


def map_designation_to_type(desig_eng, desig):
    """Map WDPA designation to our zone types"""
    designation = (desig_eng or desig or '').lower()

    if any(term in designation for term in ['ramsar', 'wetland']):
        return 'environmental'
    elif any(term in designation for term in ['nature reserve', 'national park', 'zakaznik']):
        return 'environmental'
    elif any(term in designation for term in ['world heritage']):
        return 'environmental'
    elif any(term in designation for term in ['botanical', 'forest']):
        return 'environmental'
    else:
        return 'environmental'


def create_approximated_coordinates(name, area_km2):
    """Create approximated coordinates based on known locations and area size"""
    import random
    import math

    # Known locations for major protected areas
    known_locations = {
        'altyn-emel': (43.8, 78.5),
        'charyn': (43.4, 79.0),
        'katon-karagay': (49.2, 85.9),
        'kokshetau': (53.3, 69.4),
        'aksu-zhabagly': (42.5, 70.6),
        'naurzum': (51.1, 64.6),
        'tengiz': (50.5, 69.2),
        'markakol': (49.0, 85.5),
        'usturt': (43.5, 54.0),
        'almaty': (43.2, 76.8),
        'ile-alatau': (43.0, 77.0),
        'burabay': (53.4, 70.3)
    }

    # Regional centers
    regional_centers = {
        ('south', 'syr', 'darya', 'shymkent'): (42.5, 69.0),
        ('east', 'altai', 'katon'): (49.0, 84.0),
        ('north', 'kostanay', 'kokshe'): (53.0, 68.0),
        ('west', 'atyrau', 'caspian', 'mangystau'): (46.0, 52.0),
        ('central', 'karaganda', 'ulytau'): (48.0, 68.0),
        ('almaty', 'southeast', 'tien'): (43.5, 77.0)
    }

    # Find location
    name_lower = name.lower()

    # Try known locations first
    center_lat, center_lng = None, None
    for keyword, (lat, lng) in known_locations.items():
        if keyword in name_lower:
            center_lat, center_lng = lat, lng
            break

    # Try regional matching
    if center_lat is None:
        for keywords, (lat, lng) in regional_centers.items():
            if any(keyword in name_lower for keyword in keywords):
                center_lat, center_lng = lat, lng
                # Add randomness
                center_lat += random.uniform(-0.5, 0.5)
                center_lng += random.uniform(-1.0, 1.0)
                break

    # Default random location in Kazakhstan
    if center_lat is None:
        center_lat = random.uniform(41.0, 55.0)
        center_lng = random.uniform(47.0, 87.0)

    # Create polygon based on area
    radius_km = math.sqrt(area_km2 / math.pi)
    radius_deg = radius_km / 111.0  # Convert to degrees
    radius_deg = max(0.02, min(radius_deg, 1.5))  # Limit range

    # Create natural-looking polygon
    if area_km2 > 5000:  # Large areas - irregular shape
        return create_irregular_polygon(center_lng, center_lat, radius_deg, 10)
    elif area_km2 > 500:  # Medium areas - elongated
        return create_elongated_polygon(center_lng, center_lat, radius_deg)
    else:  # Small areas - circular
        return create_circular_polygon(center_lng, center_lat, radius_deg, 8)


def create_irregular_polygon(center_lng, center_lat, radius_deg, num_points):
    """Create irregular polygon for large areas"""
    import random
    import math

    coordinates = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        # Vary radius for irregular shape
        current_radius = radius_deg * random.uniform(0.6, 1.4)
        lng = center_lng + current_radius * math.cos(angle)
        lat = center_lat + current_radius * math.sin(angle)
        coordinates.append([lng, lat])

    coordinates.append(coordinates[0])  # Close polygon
    return coordinates


def create_elongated_polygon(center_lng, center_lat, radius_deg):
    """Create elongated polygon for medium areas"""
    import random

    # Random elongation direction
    if random.choice([True, False]):  # Horizontal
        return [
            [center_lng - radius_deg * 1.5, center_lat - radius_deg * 0.6],
            [center_lng + radius_deg * 1.5, center_lat - radius_deg * 0.6],
            [center_lng + radius_deg * 1.3, center_lat + radius_deg * 0.6],
            [center_lng - radius_deg * 1.3, center_lat + radius_deg * 0.6],
            [center_lng - radius_deg * 1.5, center_lat - radius_deg * 0.6]
        ]
    else:  # Vertical
        return [
            [center_lng - radius_deg * 0.6, center_lat - radius_deg * 1.5],
            [center_lng + radius_deg * 0.6, center_lat - radius_deg * 1.5],
            [center_lng + radius_deg * 0.6, center_lat + radius_deg * 1.3],
            [center_lng - radius_deg * 0.6, center_lat + radius_deg * 1.3],
            [center_lng - radius_deg * 0.6, center_lat - radius_deg * 1.5]
        ]


def create_circular_polygon(center_lng, center_lat, radius_deg, num_points):
    """Create circular polygon for small areas"""
    import math

    coordinates = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        lng = center_lng + radius_deg * math.cos(angle)
        lat = center_lat + radius_deg * math.sin(angle)
        coordinates.append([lng, lat])

    coordinates.append(coordinates[0])  # Close polygon
    return coordinates


def parse_coordinates(coordinates_str):
    """Parse coordinates from various string formats"""
    try:
        import ast
        coordinates_str = coordinates_str.strip()

        # JSON-like array format
        if coordinates_str.startswith('[') and coordinates_str.endswith(']'):
            try:
                return ast.literal_eval(coordinates_str)
            except:
                pass

        # Semicolon separated format
        if ';' in coordinates_str:
            coords = []
            for pair in coordinates_str.split(';'):
                if ',' in pair:
                    lng, lat = map(float, pair.split(','))
                    coords.append([lng, lat])
            return coords

        return None
    except:
        return None


def show_loading_statistics():
    """Show statistics about loaded exclusion zones"""
    if not EXCLUSION_ZONES:
        return

    restriction_counts = {'high': 0, 'medium': 0, 'low': 0}
    designation_counts = {}
    geometry_sources = {}

    for zone in EXCLUSION_ZONES:
        props = zone['properties']

        # Count restriction levels
        level = props.get('restriction_level', 'unknown')
        if level in restriction_counts:
            restriction_counts[level] += 1

        # Count designations
        desig = props.get('designation', 'Unknown')[:20]
        designation_counts[desig] = designation_counts.get(desig, 0) + 1

        # Count geometry sources
        source = props.get('geometry_source', 'unknown')
        geometry_sources[source] = geometry_sources.get(source, 0) + 1

    print(f"\n📊 Loaded Exclusion Zones Statistics:")
    print(f"🔴 High restriction: {restriction_counts['high']} areas")
    print(f"🟠 Medium restriction: {restriction_counts['medium']} areas")
    print(f"🟡 Low restriction: {restriction_counts['low']} areas")

    if geometry_sources:
        print(f"\n🗺️  Geometry Sources:")
        for source, count in geometry_sources.items():
            print(f"   {source}: {count} areas")


def create_default_exclusion_zones():
    """Create default exclusion zones if no files are found"""
    global EXCLUSION_ZONES

    EXCLUSION_ZONES = [
        {
            'type': 'Feature',
            'properties': {
                'name': 'Almaty Metropolitan Area',
                'type': 'population',
                'description': 'High population density exclusion zone',
                'restriction_level': 'high',
                'geometry_source': 'default'
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[76.6, 43.0], [77.2, 43.0], [77.2, 43.4], [76.6, 43.4], [76.6, 43.0]]]
            }
        },
        {
            'type': 'Feature',
            'properties': {
                'name': 'Nur-Sultan Metropolitan Area',
                'type': 'population',
                'description': 'Capital city exclusion zone',
                'restriction_level': 'high',
                'geometry_source': 'default'
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[71.2, 50.9], [71.8, 50.9], [71.8, 51.4], [71.2, 51.4], [71.2, 50.9]]]
            }
        }
    ]

# Polygon checking functions


def point_in_polygon(x, y, polygon):
    """Ray casting algorithm to determine if a point is inside a polygon"""
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def check_exclusion_zones_polygon(lat, lng):
    """Check if location is in any polygon-based exclusion zone"""
    for zone_feature in EXCLUSION_ZONES:
        geometry = zone_feature['geometry']
        properties = zone_feature['properties']

        if geometry['type'] == 'Polygon':
            coordinates = geometry['coordinates'][0]  # Outer ring
            if point_in_polygon(lng, lat, coordinates):
                return {
                    'in_zone': True,
                    'zone_name': properties['name'],
                    'zone_type': properties['type'],
                    'restriction_level': properties.get('restriction_level', 'high'),
                    'description': properties.get('description', ''),
                    'distance': 0
                }
        elif geometry['type'] == 'MultiPolygon':
            for polygon in geometry['coordinates']:
                coordinates = polygon[0]  # Outer ring
                if point_in_polygon(lng, lat, coordinates):
                    return {
                        'in_zone': True,
                        'zone_name': properties['name'],
                        'zone_type': properties['type'],
                        'restriction_level': properties.get('restriction_level', 'high'),
                        'description': properties.get('description', ''),
                        'distance': 0
                    }

    return {'in_zone': False, 'distance': None}

# Database setup


def init_db():
    conn = sqlite3.connect('nuclear_sites.db')
    c = conn.cursor()

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
    {"name": "Almaty", "lat": 43.2220, "lng": 76.8512,
        "population": 2000000, "industrial_factor": 0.8},
    {"name": "Nur-Sultan", "lat": 51.1694, "lng": 71.4491,
        "population": 1200000, "industrial_factor": 0.6},
    {"name": "Shymkent", "lat": 42.3417, "lng": 69.5901,
        "population": 1000000, "industrial_factor": 0.7},
    {"name": "Aktobe", "lat": 50.2839, "lng": 57.1670,
        "population": 500000, "industrial_factor": 0.5},
    {"name": "Taraz", "lat": 42.9000, "lng": 71.3667,
        "population": 400000, "industrial_factor": 0.4},
    {"name": "Pavlodar", "lat": 52.2856, "lng": 76.9749,
        "population": 350000, "industrial_factor": 0.6},
    {"name": "Ust-Kamenogorsk", "lat": 49.9483, "lng": 82.6283,
        "population": 300000, "industrial_factor": 0.5},
    {"name": "Karaganda", "lat": 49.8047, "lng": 73.1094,
        "population": 500000, "industrial_factor": 0.9},
    {"name": "Aktau", "lat": 43.6500, "lng": 51.2000,
        "population": 200000, "industrial_factor": 0.8},
    {"name": "Atyrau", "lat": 47.1164, "lng": 51.8830,
        "population": 300000, "industrial_factor": 0.7}
]

WATER_SOURCES = [
    {"name": "Lake Balkhash", "lat": 46.8, "lng": 74.5,
        "type": "Large Lake", "reliability": 95, "flow_rate": 1000},
    {"name": "Caspian Sea", "lat": 44.0, "lng": 51.0,
        "type": "Sea", "reliability": 100, "flow_rate": 10000},
    {"name": "Lake Alakol", "lat": 46.2, "lng": 81.5,
        "type": "Lake", "reliability": 80, "flow_rate": 200},
    {"name": "Irtysh River", "lat": 50.0, "lng": 82.0,
        "type": "River", "reliability": 85, "flow_rate": 500},
    {"name": "Ishim River", "lat": 51.5, "lng": 71.0,
        "type": "River", "reliability": 70, "flow_rate": 150},
    {"name": "Ili River", "lat": 43.5, "lng": 77.0,
        "type": "River", "reliability": 85, "flow_rate": 300}
]

SEISMIC_ZONES = [
    {"region": "East Kazakhstan", "lat_range": [49, 51], "lng_range": [
        80, 87], "risk_level": "High", "score": 30},
    {"region": "Southeast", "lat_range": [42, 45], "lng_range": [
        75, 80], "risk_level": "Medium-High", "score": 50},
    {"region": "West Kazakhstan", "lat_range": [46, 52], "lng_range": [
        46, 60], "risk_level": "Low", "score": 85},
    {"region": "North Kazakhstan", "lat_range": [50, 55], "lng_range": [
        60, 80], "risk_level": "Low", "score": 85},
    {"region": "Central Kazakhstan", "lat_range": [45, 50], "lng_range": [
        65, 75], "risk_level": "Medium", "score": 70}
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

    return {'region': 'Unknown', 'level': 'Medium', 'score': 60}


def get_elevation_data(lat, lng):
    """Get elevation data from external API"""
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={
            lat},{lng}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data['results'][0]['elevation']
    except:
        pass
    return 500


def calculate_grid_integration_score(lat, lng, nearest_city):
    """Calculate grid integration feasibility"""
    distance_penalty = min(nearest_city['distance'] * 0.15, 50)
    base_score = 100 - distance_penalty

    if nearest_city['population'] > 500000:
        base_score += 10

    if nearest_city['name'] in ['Almaty', 'Nur-Sultan', 'Shymkent']:
        base_score += 15

    return min(100, max(0, base_score))


def calculate_transportation_score(lat, lng, nearest_city):
    """Calculate transportation infrastructure score"""
    base_score = max(0, 100 - nearest_city['distance'] * 0.2)

    infrastructure_bonus = {
        'Almaty': 20, 'Nur-Sultan': 15, 'Shymkent': 15,
        'Karaganda': 10, 'Aktobe': 10, 'Pavlodar': 10
    }

    bonus = infrastructure_bonus.get(nearest_city['name'], 0)
    return min(100, base_score + bonus)


def calculate_economic_viability(lat, lng, nearest_city, nearest_water, seismic_risk):
    """Calculate economic viability score"""
    base_score = 80

    city_penalty = min(nearest_city['distance'] * 0.1, 30)
    water_penalty = min(nearest_water['distance'] * 0.2, 20)
    seismic_penalty = (100 - seismic_risk['score']) * 0.3
    industrial_bonus = nearest_city['industrial_factor'] * 20

    final_score = base_score - city_penalty - \
        water_penalty - seismic_penalty + industrial_bonus
    return max(0, min(100, final_score))


@app.route('/')
def index():
    """Serve the main application"""
    with open('nuclear_site_app.html', 'r') as f:
        html_content = f.read()
    return render_template_string(html_content)


@app.route('/api/exclusion_zones', methods=['GET'])
def get_exclusion_zones():
    """Return exclusion zones GeoJSON data for frontend"""
    return jsonify({
        'type': 'FeatureCollection',
        'features': EXCLUSION_ZONES
    })


@app.route('/api/analyze_site', methods=['POST'])
def analyze_site():
    """Analyze a potential nuclear plant site"""
    try:
        data = request.json
        lat = float(data['latitude'])
        lng = float(data['longitude'])

        if not (40.5 <= lat <= 55.5 and 46.5 <= lng <= 87.5):
            return jsonify({'error': 'Coordinates outside Kazakhstan'}), 400

        nearest_city = find_nearest_entity(lat, lng, MAJOR_CITIES)
        nearest_water = find_nearest_entity(lat, lng, WATER_SOURCES)
        exclusion_check = check_exclusion_zones_polygon(lat, lng)
        seismic_risk = calculate_seismic_risk(lat, lng)
        elevation = get_elevation_data(lat, lng)

        # Calculate detailed criteria scores
        criteria = []

        pop_score = max(0, 100 - nearest_city['distance'] * 0.2)
        criteria.append({
            'name': 'Population Access',
            'score': pop_score,
            'weight': 0.15,
            'details': f"{nearest_city['distance']:.0f}km from {nearest_city['name']} ({nearest_city['population']:,} people)"
        })

        water_score = max(
            0, 100 - nearest_water['distance'] * 0.5) * (nearest_water['reliability'] / 100)
        criteria.append({
            'name': 'Water Supply',
            'score': water_score,
            'weight': 0.12,
            'details': f"{nearest_water['distance']:.0f}km from {nearest_water['name']} ({nearest_water['reliability']}% reliable)"
        })

        criteria.append({
            'name': 'Seismic Safety',
            'score': seismic_risk['score'],
            'weight': 0.10,
            'details': f"{seismic_risk['level']} risk in {seismic_risk['region']}"
        })

        # Enhanced environmental scoring with real WDPA data
        if exclusion_check['in_zone']:
            restriction_level = exclusion_check.get(
                'restriction_level', 'high')
            if restriction_level == 'high':
                env_score = 10  # 90% penalty
            elif restriction_level == 'medium':
                env_score = 40  # 60% penalty
            else:
                env_score = 60  # 40% penalty
        else:
            env_score = 90

        env_details = f"In {exclusion_check['zone_name']} ({exclusion_check.get(
            'restriction_level', 'high')} restriction)" if exclusion_check['in_zone'] else "Clear area"
        criteria.append({
            'name': 'Environmental Impact',
            'score': env_score,
            'weight': 0.08,
            'details': env_details
        })

        grid_score = calculate_grid_integration_score(lat, lng, nearest_city)
        criteria.append({
            'name': 'Grid Integration',
            'score': grid_score,
            'weight': 0.10,
            'details': f"Transmission infrastructure to {nearest_city['name']}"
        })

        transport_score = calculate_transportation_score(
            lat, lng, nearest_city)
        criteria.append({
            'name': 'Transportation',
            'score': transport_score,
            'weight': 0.08,
            'details': f"Road/rail access via {nearest_city['name']}"
        })

        industrial_score = 50 + \
            (nearest_city['industrial_factor'] * 40) - \
            (nearest_city['distance'] * 0.1)
        industrial_score = max(0, min(100, industrial_score))
        criteria.append({
            'name': 'Industrial Demand',
            'score': industrial_score,
            'weight': 0.12,
            'details': f"Industrial factor: {nearest_city['industrial_factor']:.1f}"
        })

        econ_score = calculate_economic_viability(
            lat, lng, nearest_city, nearest_water, seismic_risk)
        criteria.append({
            'name': 'Economic Viability',
            'score': econ_score,
            'weight': 0.10,
            'details': f"Cost-benefit analysis score"
        })

        criteria.append({
            'name': 'Public Acceptance',
            'score': 71,
            'weight': 0.05,
            'details': "71% referendum support (Oct 2024)"
        })

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
        cost_estimate = calculate_cost_estimate(
            lat, lng, nearest_city, nearest_water, seismic_risk)
        timeline_estimate = calculate_timeline(lat, lng, overall_score)

        # Store evaluation
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
    base_cost = 10.0

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
    base_timeline = 10

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
    base_revenue = 800

    population_factor = min(nearest_city['population'] / 1000000, 2.0)
    industrial_factor = industrial_score / 100

    annual_revenue = base_revenue * \
        (0.5 + 0.3 * population_factor + 0.2 * industrial_factor)

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
    # Load exclusion zones (will try shapefile first, then fallbacks)
    load_exclusion_zones()

    # Initialize database
    init_db()

    # Check for HTML file
    if not os.path.exists('nuclear_site_app.html'):
        print(
            "Please save the HTML content as 'nuclear_site_app.html' in the same directory")

    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
