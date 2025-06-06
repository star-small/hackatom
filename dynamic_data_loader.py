#!/usr/bin/env python3
"""
Dynamic Data Loader for Kazakhstan NPP Site Selection
Loads seismic zones, cities, water sources, and other parameters from external sources
"""

import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
import geopandas as gpd
import pandas as pd


class DynamicDataLoader:
    def __init__(self, cache_dir="data_cache"):
        self.cache_dir = cache_dir
        self.cache_duration = timedelta(days=30)  # Cache data for 30 days

        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)

        # Initialize cache database
        self.init_cache_db()

    def init_cache_db(self):
        """Initialize cache database to track data freshness"""
        conn = sqlite3.connect(f"{self.cache_dir}/cache_metadata.db")
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS cache_metadata
                     (data_type TEXT PRIMARY KEY,
                      last_updated DATETIME,
                      file_path TEXT,
                      source_url TEXT)''')

        conn.commit()
        conn.close()

    def clear_cache(self, data_type=None):
        """Clear cache for specific data type or all cache"""
        if data_type:
            cache_file = f"{self.cache_dir}/kazakhstan_{data_type}.geojson"
            if os.path.exists(cache_file):
                os.remove(cache_file)
                print(f"🗑️ Cleared {data_type} cache")
        else:
            # Clear all cache
            import glob
            cache_files = glob.glob(f"{self.cache_dir}/*.geojson")
            for file in cache_files:
                os.remove(file)
            print("🗑️ Cleared all cache")

        # Update metadata
        conn = sqlite3.connect(f"{self.cache_dir}/cache_metadata.db")
        c = conn.cursor()
        if data_type:
            c.execute(
                'DELETE FROM cache_metadata WHERE data_type = ?', (data_type,))
        else:
            c.execute('DELETE FROM cache_metadata')
        conn.commit()
        conn.close()

    def validate_cached_data(self, data_type):
        """Validate that cached data is not empty or corrupted"""
        cache_file = f"{self.cache_dir}/kazakhstan_{data_type}.geojson"

        if not os.path.exists(cache_file):
            return False

        try:
            features = self.load_geojson_file(cache_file)
            # Check if we have reasonable amount of data
            if data_type == 'cities' and len(features) < 5:
                print(f"⚠️ {data_type} cache has too few entries ({
                      len(features)}), refreshing...")
                return False
            elif data_type == 'water_sources' and len(features) > 1000:
                print(f"⚠️ {data_type} cache has too many entries ({
                      len(features)}), refreshing...")
                return False
            elif len(features) == 0:
                print(f"⚠️ {data_type} cache is empty, refreshing...")
                return False

            return True
        except Exception as e:
            print(f"⚠️ {data_type} cache is corrupted: {e}")
            return False

    def is_cache_valid(self, data_type):
        """Check if cached data is still valid and not corrupted"""
        # First check if it exists and is not corrupted
        if not self.validate_cached_data(data_type):
            return False

        # Then check timestamp
        conn = sqlite3.connect(f"{self.cache_dir}/cache_metadata.db")
        c = conn.cursor()

        c.execute(
            'SELECT last_updated FROM cache_metadata WHERE data_type = ?', (data_type,))
        result = c.fetchone()

        conn.close()

        if not result:
            return False

        last_updated = datetime.fromisoformat(result[0])
        return datetime.now() - last_updated < self.cache_duration

    def update_cache_metadata(self, data_type, file_path, source_url):
        """Update cache metadata"""
        conn = sqlite3.connect(f"{self.cache_dir}/cache_metadata.db")
        c = conn.cursor()

        c.execute('''INSERT OR REPLACE INTO cache_metadata
                     (data_type, last_updated, file_path, source_url)
                     VALUES (?, ?, ?, ?)''',
                  (data_type, datetime.now().isoformat(), file_path, source_url))

        conn.commit()
        conn.close()

    def load_seismic_zones(self):
        """Load seismic hazard zones for Kazakhstan"""
        print("🌍 Loading seismic hazard data...")

        # Check cache first
        cache_file = f"{self.cache_dir}/kazakhstan_seismic_zones.geojson"
        if self.is_cache_valid('seismic_zones') and os.path.exists(cache_file):
            print("📁 Using cached seismic data")
            return self.load_geojson_file(cache_file)

        seismic_zones = []

        try:
            # Method 1: Use OpenStreetMap data for geological features
            seismic_zones.extend(self.get_osm_geological_data())

            # Method 2: Use known seismic regions with more detailed boundaries
            seismic_zones.extend(self.create_detailed_seismic_zones())

            # Save to cache
            self.save_geojson_cache(
                seismic_zones, cache_file, 'seismic_zones', 'multiple_sources')

        except Exception as e:
            print(f"⚠️ Error loading seismic data: {e}")
            # Fallback to basic zones
            seismic_zones = self.create_basic_seismic_zones()

        return seismic_zones

    def load_major_cities(self):
        """Load major cities from OpenStreetMap"""
        print("🏙️ Loading major cities from OpenStreetMap...")

        cache_file = f"{self.cache_dir}/kazakhstan_cities.geojson"
        if self.is_cache_valid('cities') and os.path.exists(cache_file):
            print("📁 Using cached cities data")
            return self.load_geojson_file(cache_file)

        try:
            cities = self.query_osm_cities()

            # Enhance with population and industrial data
            cities = self.enhance_city_data(cities)

            # Save to cache
            self.save_geojson_cache(
                cities, cache_file, 'cities', 'openstreetmap')

            return cities

        except Exception as e:
            print(f"⚠️ Error loading cities: {e}")
            return self.create_fallback_cities()

    def load_water_sources(self):
        """Load water sources from OpenStreetMap and Natural Earth"""
        print("💧 Loading water sources...")

        cache_file = f"{self.cache_dir}/kazakhstan_water_sources.geojson"
        if self.is_cache_valid('water_sources') and os.path.exists(cache_file):
            print("📁 Using cached water sources data")
            return self.load_geojson_file(cache_file)

        try:
            water_sources = []

            # Get major water bodies from OSM
            water_sources.extend(self.query_osm_water_bodies())

            # Add major rivers
            water_sources.extend(self.query_osm_rivers())

            # Enhance with reliability estimates
            water_sources = self.enhance_water_data(water_sources)

            # Save to cache
            self.save_geojson_cache(
                water_sources, cache_file, 'water_sources', 'openstreetmap')

            return water_sources

        except Exception as e:
            print(f"⚠️ Error loading water sources: {e}")
            return self.create_fallback_water_sources()

    def load_transportation_network(self):
        """Load transportation infrastructure"""
        print("🛣️ Loading transportation network...")

        cache_file = f"{self.cache_dir}/kazakhstan_transportation.geojson"
        if self.is_cache_valid('transportation') and os.path.exists(cache_file):
            print("📁 Using cached transportation data")
            return self.load_geojson_file(cache_file)

        try:
            transport_data = []

            # Major highways
            transport_data.extend(self.query_osm_highways())

            # Railways
            transport_data.extend(self.query_osm_railways())

            # Airports
            transport_data.extend(self.query_osm_airports())

            # Filter all transportation data for Kazakhstan
            kazakhstan_transport = self.filter_kazakhstan_features(
                transport_data)

            # Save to cache
            self.save_geojson_cache(
                kazakhstan_transport, cache_file, 'transportation', 'openstreetmap')

            return kazakhstan_transport

        except Exception as e:
            print(f"⚠️ Error loading transportation: {e}")
            return []

    def query_osm_cities(self):
        """Query OpenStreetMap for major cities in Kazakhstan"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        # More specific query for Kazakhstan cities only
        overpass_query = """
        [out:json][timeout:60];
        (
          node["place"="city"]["name"]
              ["addr:country"="KZ"]
              (bbox:40.5,46.5,55.5,87.5);
          way["place"="city"]["name"]
             ["addr:country"="KZ"]
             (bbox:40.5,46.5,55.5,87.5);
          relation["place"="city"]["name"]
                 ["addr:country"="KZ"]
                 (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            cities = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    # Get coordinates
                    if element['type'] == 'node':
                        lat, lng = element['lat'], element['lon']
                    elif 'center' in element:
                        lat, lng = element['center']['lat'], element['center']['lon']
                    else:
                        continue

                    # Extract data
                    tags = element['tags']
                    population = self.parse_population(
                        tags.get('population', '0'))

                    city = {
                        'type': 'Feature',
                        'properties': {
                            'name': tags['name'],
                            'name_en': tags.get('name:en', tags['name']),
                            'population': population,
                            'place_type': tags.get('place', 'city'),
                            'admin_level': tags.get('admin_level', ''),
                            'industrial_factor': self.estimate_industrial_factor(tags, population)
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [lng, lat]
                        }
                    }
                    cities.append(city)

            # Sort by population and take top cities, filtered for Kazakhstan
            cities.sort(key=lambda x: x['properties']
                        ['population'], reverse=True)
            kazakhstan_cities = self.filter_kazakhstan_features(cities)
            return kazakhstan_cities[:15]  # Top 15 cities in Kazakhstan

        except Exception as e:
            print(f"OSM query failed: {e}")
            return self.create_fallback_cities()

    def query_osm_water_bodies(self):
        """Query OpenStreetMap for major water bodies in Kazakhstan only"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        # Focus on significant water bodies within Kazakhstan
        overpass_query = """
        [out:json][timeout:60];
        (
          way["natural"="water"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
          relation["natural"="water"]["name"]
                  (bbox:40.5,46.5,55.5,87.5);
          way["landuse"="reservoir"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            water_bodies = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    tags = element['tags']

                    # Calculate approximate center
                    if 'center' in element:
                        lat, lng = element['center']['lat'], element['center']['lon']
                    elif 'geometry' in element and element['geometry']:
                        coords = element['geometry']
                        lats = [c['lat'] for c in coords]
                        lngs = [c['lon'] for c in coords]
                        lat, lng = sum(lats)/len(lats), sum(lngs)/len(lngs)
                    else:
                        continue

                    water_body = {
                        'type': 'Feature',
                        'properties': {
                            'name': tags['name'],
                            'type': self.classify_water_type(tags),
                            'reliability': self.estimate_water_reliability(tags),
                            'flow_rate': self.estimate_flow_rate(tags)
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [lng, lat]
                        }
                    }
                    water_bodies.append(water_body)

            # Filter for Kazakhstan and limit to reasonable number
            kazakhstan_water = self.filter_kazakhstan_features(water_bodies)
            # Limit to 25 major water bodies in Kazakhstan
            return kazakhstan_water[:25]

        except Exception as e:
            print(f"Water bodies query failed: {e}")
            return []

    def query_osm_rivers(self):
        """Query OpenStreetMap for major rivers in Kazakhstan only"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        # Focus on major rivers within Kazakhstan boundaries
        overpass_query = """
        [out:json][timeout:60];
        (
          way["waterway"="river"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
          relation["waterway"="river"]["name"]
                  (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            rivers = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    tags = element['tags']

                    # Get representative point for river
                    if 'geometry' in element and element['geometry']:
                        coords = element['geometry']
                        # Use middle point of river
                        mid_idx = len(coords) // 2
                        lat, lng = coords[mid_idx]['lat'], coords[mid_idx]['lon']
                    else:
                        continue

                    river = {
                        'type': 'Feature',
                        'properties': {
                            'name': tags['name'],
                            'type': 'River',
                            'reliability': self.estimate_river_reliability(tags),
                            'flow_rate': self.estimate_river_flow(tags)
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [lng, lat]
                        }
                    }
                    rivers.append(river)

            # Filter for Kazakhstan and limit
            kazakhstan_rivers = self.filter_kazakhstan_features(rivers)
            # Limit to 15 major rivers in Kazakhstan
            return kazakhstan_rivers[:15]

        except Exception as e:
            print(f"Rivers query failed: {e}")
            return []

    def get_osm_geological_data(self):
        """Get geological hazard data from OpenStreetMap"""
        # OSM has limited geological data, but we can get some hazard zones
        overpass_url = "http://overpass-api.de/api/interpreter"

        overpass_query = """
        [out:json][timeout:60];
        (
          way["geological"="fault"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
          way["natural"="cliff"]
             (bbox:40.5,46.5,55.5,87.5);
          area["place"="region"]["geological"]
               (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            geological_features = []
            for element in data['elements']:
                # Process geological features and convert to seismic risk zones
                # This is simplified - in practice you'd use more sophisticated geological data
                pass

            return []  # For now, return empty - OSM geological data is limited

        except Exception as e:
            print(f"Geological data query failed: {e}")
            return []

    def create_detailed_seismic_zones(self):
        """Create realistic seismic zones based on geological surveys and fault lines"""
        # Based on Kazakhstan's actual geological structure and seismic hazard maps
        seismic_zones = [
            {
                'type': 'Feature',
                'properties': {
                    'region': 'Almaty-Tien Shan Seismic Zone',
                    'risk_level': 'High',
                    'score': 25,
                    'description': 'Active fault systems along Tien Shan mountain range'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [75.0, 42.5], [76.5, 42.8], [77.8, 43.0], [78.5, 43.3],
                        [79.2, 43.8], [79.0, 44.3], [78.2, 44.5], [77.0, 44.2],
                        [76.0, 43.8], [75.2, 43.2], [75.0, 42.5]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'East Kazakhstan-Altai Seismic Zone',
                    'risk_level': 'High',
                    'score': 30,
                    'description': 'Altai mountain region with complex fault networks'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [82.0, 48.2], [84.5, 48.0], [86.2, 49.0], [86.8, 49.8],
                        [86.5, 50.5], [85.0, 50.8], [83.5, 50.3], [82.5, 49.5],
                        [82.0, 48.2]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'Balkhash-Alakol Moderate Zone',
                    'risk_level': 'Medium',
                    'score': 65,
                    'description': 'Transitional zone between stable platform and active margins'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [74.0, 45.5], [78.0, 45.0], [81.0, 46.0], [82.5, 47.5],
                        [82.0, 48.0], [79.0, 48.2], [76.5, 47.8], [74.5, 47.0],
                        [74.0, 45.5]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'Central Kazakhstan Stable Platform',
                    'risk_level': 'Low',
                    'score': 85,
                    'description': 'Ancient crystalline basement with minimal seismic activity'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [65.0, 46.5], [72.0, 46.8], [74.0, 48.0], [73.5, 50.5],
                        [71.0, 52.0], [68.0, 52.5], [66.0, 51.0], [65.5, 48.5],
                        [65.0, 46.5]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'West Kazakhstan-Caspian Stable Zone',
                    'risk_level': 'Low',
                    'score': 80,
                    'description': 'Caspian depression and Ural foreland with low seismic activity'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [47.0, 44.0], [55.0, 44.5], [60.0, 46.0], [62.0, 48.0],
                        [60.5, 50.0], [57.0, 51.5], [52.0, 52.0], [48.0, 50.5],
                        [47.0, 47.0], [47.0, 44.0]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'North Kazakhstan Platform',
                    'risk_level': 'Low',
                    'score': 88,
                    'description': 'Stable Siberian platform extension with very low seismic risk'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [60.0, 50.0], [70.0, 50.5], [75.0, 52.0], [76.0, 54.0],
                        [74.0, 55.0], [68.0, 55.2], [62.0, 54.5], [60.0, 52.0],
                        [60.0, 50.0]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'Mangystau Peninsula Moderate Zone',
                    'risk_level': 'Medium',
                    'score': 70,
                    'description': 'Coastal zone with moderate tectonic activity'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [50.0, 42.5], [53.5, 42.0], [55.0, 43.5], [54.0, 45.0],
                        [52.0, 45.5], [50.5, 44.0], [50.0, 42.5]
                    ]]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'region': 'South Kazakhstan Transitional Zone',
                    'risk_level': 'Medium',
                    'score': 60,
                    'description': 'Transitional area between Tien Shan and stable platform'
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [66.0, 40.8], [74.0, 41.0], [75.0, 42.5], [73.5, 43.5],
                        [70.0, 43.8], [67.5, 43.0], [66.0, 42.0], [66.0, 40.8]
                    ]]
                }
            }
        ]

        return seismic_zones

    def enhance_city_data(self, cities):
        """Enhance city data with additional information"""
        enhanced_cities = []

        for city in cities:
            # Add any missing data or corrections
            props = city['properties']

            # Ensure all required fields exist
            if 'industrial_factor' not in props:
                props['industrial_factor'] = self.estimate_industrial_factor(
                    {}, props.get('population', 0)
                )

            enhanced_cities.append(city)

        return enhanced_cities

    def enhance_water_data(self, water_sources):
        """Enhance water source data with reliability estimates"""
        enhanced_sources = []

        for source in water_sources:
            props = source['properties']

            # Ensure all required fields exist
            if 'reliability' not in props:
                props['reliability'] = self.estimate_water_reliability({})

            if 'flow_rate' not in props:
                props['flow_rate'] = self.estimate_flow_rate({})

            enhanced_sources.append(source)

        return enhanced_sources

    def query_osm_highways(self):
        """Query OpenStreetMap for major highways"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        overpass_query = """
        [out:json][timeout:60];
        (
          way["highway"~"^(motorway|trunk|primary)$"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            highways = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    highway = {
                        'type': 'Feature',
                        'properties': {
                            'name': element['tags']['name'],
                            'type': f"Highway ({element['tags']['highway']})",
                            'highway_type': element['tags']['highway']
                        },
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [[pt['lon'], pt['lat']] for pt in element.get('geometry', [])]
                        }
                    }
                    highways.append(highway)

            return highways[:15]  # Limit to top 15 highways

        except Exception as e:
            print(f"Highways query failed: {e}")
            return []

    def query_osm_railways(self):
        """Query OpenStreetMap for railway lines"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        overpass_query = """
        [out:json][timeout:60];
        (
          way["railway"="rail"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            railways = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    railway = {
                        'type': 'Feature',
                        'properties': {
                            'name': element['tags']['name'],
                            'type': 'Railway',
                            'railway_type': element['tags'].get('railway', 'rail')
                        },
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [[pt['lon'], pt['lat']] for pt in element.get('geometry', [])]
                        }
                    }
                    railways.append(railway)

            return railways[:10]  # Limit to top 10 railways

        except Exception as e:
            print(f"Railways query failed: {e}")
            return []

    def query_osm_airports(self):
        """Query OpenStreetMap for airports"""
        overpass_url = "http://overpass-api.de/api/interpreter"

        overpass_query = """
        [out:json][timeout:60];
        (
          way["aeroway"="aerodrome"]["name"]
             (bbox:40.5,46.5,55.5,87.5);
          node["aeroway"="aerodrome"]["name"]
              (bbox:40.5,46.5,55.5,87.5);
        );
        out geom;
        """

        try:
            response = requests.post(
                overpass_url, data=overpass_query, timeout=120)
            data = response.json()

            airports = []
            for element in data['elements']:
                if 'tags' in element and 'name' in element['tags']:
                    # Get coordinates
                    if element['type'] == 'node':
                        lat, lng = element['lat'], element['lon']
                    elif 'center' in element:
                        lat, lng = element['center']['lat'], element['center']['lon']
                    elif 'geometry' in element and element['geometry']:
                        coords = element['geometry']
                        lats = [c['lat'] for c in coords]
                        lngs = [c['lon'] for c in coords]
                        lat, lng = sum(lats)/len(lats), sum(lngs)/len(lngs)
                    else:
                        continue

                    airport = {
                        'type': 'Feature',
                        'properties': {
                            'name': element['tags']['name'],
                            'type': 'Airport',
                            'aeroway_type': element['tags'].get('aeroway', 'aerodrome'),
                            'iata': element['tags'].get('iata', ''),
                            'icao': element['tags'].get('icao', '')
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [lng, lat]
                        }
                    }
                    airports.append(airport)

            return airports

        except Exception as e:
            print(f"Airports query failed: {e}")
            return []
        """Parse population from various string formats"""
        if not pop_str or pop_str == '0':
            return 0

        try:
            # Remove commas and spaces
            pop_str = pop_str.replace(',', '').replace(' ', '')

            # Handle different formats
            if 'million' in pop_str.lower():
                return int(float(pop_str.lower().replace('million', '')) * 1000000)
            elif 'k' in pop_str.lower():
                return int(float(pop_str.lower().replace('k', '')) * 1000)
            else:
                return int(float(pop_str))
        except:
            return 0

    def estimate_industrial_factor(self, tags, population):
        """Estimate industrial factor based on city characteristics"""
        industrial_keywords = ['industrial',
                               'mining', 'factory', 'plant', 'port']

        base_factor = min(population / 1000000, 0.8)  # Scale with population

        # Check for industrial indicators in tags
        for key, value in tags.items():
            if any(keyword in str(value).lower() for keyword in industrial_keywords):
                base_factor += 0.2

        return min(base_factor, 1.0)

    def classify_water_type(self, tags):
        """Classify water body type"""
        if 'landuse' in tags and tags['landuse'] == 'reservoir':
            return 'Reservoir'
        elif 'water' in tags and 'lake' in tags['water']:
            return 'Lake'
        elif 'natural' in tags and tags['natural'] == 'water':
            return 'Lake'
        else:
            return 'Water Body'

    def estimate_water_reliability(self, tags):
        """Estimate water source reliability"""
        water_type = self.classify_water_type(tags)

        if water_type == 'Reservoir':
            return 95
        elif water_type == 'Lake':
            return 85
        else:
            return 75

    def estimate_flow_rate(self, tags):
        """Estimate water flow rate"""
        # Simplified estimation
        return 500  # Default flow rate

    def estimate_river_reliability(self, tags):
        """Estimate river reliability"""
        # Major rivers are more reliable
        name = tags.get('name', '').lower()
        major_rivers = ['irtysh', 'ob', 'ishim', 'ili', 'syr darya', 'ural']

        if any(river in name for river in major_rivers):
            return 90
        else:
            return 70

    def estimate_river_flow(self, tags):
        """Estimate river flow rate"""
        name = tags.get('name', '').lower()
        major_rivers = {
            'irtysh': 1000, 'ob': 800, 'ishim': 200,
            'ili': 400, 'syr darya': 600, 'ural': 300
        }

        for river, flow in major_rivers.items():
            if river in name:
                return flow

        return 150  # Default for smaller rivers

    # Cache management functions
    def save_geojson_cache(self, data, file_path, data_type, source_url):
        """Save data to GeoJSON cache"""
        geojson = {
            'type': 'FeatureCollection',
            'features': data
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        self.update_cache_metadata(data_type, file_path, source_url)

    def load_geojson_file(self, file_path):
        """Load GeoJSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        return geojson['features']

    # Fallback functions
    def create_fallback_cities(self):
        """Create fallback cities if OSM query fails"""
        return [
            {
                'type': 'Feature',
                'properties': {
                    'name': 'Almaty',
                    'population': 2000000,
                    'industrial_factor': 0.8
                },
                'geometry': {'type': 'Point', 'coordinates': [76.8512, 43.2220]}
            },
            {
                'type': 'Feature',
                'properties': {
                    'name': 'Nur-Sultan',
                    'population': 1200000,
                    'industrial_factor': 0.6
                },
                'geometry': {'type': 'Point', 'coordinates': [71.4491, 51.1694]}
            }
            # Add more fallback cities...
        ]

    def create_fallback_water_sources(self):
        """Create fallback water sources"""
        return [
            {
                'type': 'Feature',
                'properties': {
                    'name': 'Lake Balkhash',
                    'type': 'Large Lake',
                    'reliability': 95,
                    'flow_rate': 1000
                },
                'geometry': {'type': 'Point', 'coordinates': [74.5, 46.8]}
            }
            # Add more fallback sources...
        ]

    def create_basic_seismic_zones(self):
        """Create basic seismic zones as fallback"""
        return self.create_detailed_seismic_zones()


# Usage example
if __name__ == "__main__":
    loader = DynamicDataLoader()

    print("Loading dynamic data for Kazakhstan NPP analysis...")

    seismic_zones = loader.load_seismic_zones()
    print(f"Loaded {len(seismic_zones)} seismic zones")

    cities = loader.load_major_cities()
    print(f"Loaded {len(cities)} cities")

    water_sources = loader.load_water_sources()
    print(f"Loaded {len(water_sources)} water sources")

    transport = loader.load_transportation_network()
    # !/usr/bin/env python3
    print(f"Loaded {len(transport)} transportation features")
"""
"""
