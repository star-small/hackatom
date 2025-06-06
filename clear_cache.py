#!/usr/bin/env python3
"""
Clear corrupted cache data for Kazakhstan NPP analysis
"""

import os
import glob
import sqlite3
from datetime import datetime


def clear_all_cache():
    """Clear all cached data"""
    cache_dir = "data_cache"

    if not os.path.exists(cache_dir):
        print("📁 No cache directory found")
        return

    # Remove all GeoJSON cache files
    cache_files = glob.glob(f"{cache_dir}/*.geojson")

    if not cache_files:
        print("📁 No cache files found")
        return

    print(f"🗑️ Clearing {len(cache_files)} cache files...")

    for file in cache_files:
        try:
            os.remove(file)
            filename = os.path.basename(file)
            print(f"   ✅ Removed {filename}")
        except Exception as e:
            print(f"   ❌ Failed to remove {file}: {e}")

    # Clear cache metadata
    metadata_db = f"{cache_dir}/cache_metadata.db"
    if os.path.exists(metadata_db):
        try:
            conn = sqlite3.connect(metadata_db)
            c = conn.cursor()
            c.execute('DELETE FROM cache_metadata')
            conn.commit()
            conn.close()
            print("   ✅ Cleared metadata database")
        except Exception as e:
            print(f"   ⚠️ Failed to clear metadata: {e}")

    print("\n🎉 Cache cleared successfully!")
    print("🔄 Next run will download fresh data from OpenStreetMap")


def clear_specific_cache(data_type):
    """Clear cache for specific data type"""
    cache_dir = "data_cache"
    cache_file = f"{cache_dir}/kazakhstan_{data_type}.geojson"

    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
            print(f"✅ Cleared {data_type} cache")

            # Update metadata
            metadata_db = f"{cache_dir}/cache_metadata.db"
            if os.path.exists(metadata_db):
                conn = sqlite3.connect(metadata_db)
                c = conn.cursor()
                c.execute(
                    'DELETE FROM cache_metadata WHERE data_type = ?', (data_type,))
                conn.commit()
                conn.close()

        except Exception as e:
            print(f"❌ Failed to clear {data_type} cache: {e}")
    else:
        print(f"📁 No {data_type} cache file found")


def check_cache_status():
    """Check current cache status"""
    cache_dir = "data_cache"

    if not os.path.exists(cache_dir):
        print("📁 No cache directory found")
        return

    print("📊 Current Cache Status:")
    print("=" * 30)

    data_types = ['cities', 'water_sources', 'seismic_zones', 'transportation']

    for data_type in data_types:
        cache_file = f"{cache_dir}/kazakhstan_{data_type}.geojson"

        if os.path.exists(cache_file):
            try:
                file_size = os.path.getsize(cache_file)
                mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file))

                # Try to count features
                try:
                    import json
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        feature_count = len(data.get('features', []))
                except:
                    feature_count = "unknown"

                print(f"✅ {data_type}:")
                print(f"   📏 Size: {file_size:,} bytes")
                print(f"   📅 Modified: {
                      mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   📊 Features: {feature_count}")

                # Flag potential issues
                if data_type == 'cities' and isinstance(feature_count, int) and feature_count < 5:
                    print(f"   ⚠️ Too few cities ({
                          feature_count}) - recommend clearing")
                elif data_type == 'water_sources' and isinstance(feature_count, int) and feature_count > 1000:
                    print(f"   ⚠️ Too many water sources ({
                          feature_count}) - recommend clearing")

            except Exception as e:
                print(f"❌ {data_type}: Error reading file - {e}")
        else:
            print(f"📭 {data_type}: No cache file")

        print()


if __name__ == "__main__":
    import sys

    print("🗑️ Kazakhstan NPP Cache Manager")
    print("=" * 35)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "clear":
            if len(sys.argv) > 2:
                data_type = sys.argv[2]
                clear_specific_cache(data_type)
            else:
                clear_all_cache()

        elif command == "status":
            check_cache_status()

        else:
            print("❌ Unknown command. Use:")
            print("   python clear_cache.py status")
            print("   python clear_cache.py clear")
            print("   python clear_cache.py clear cities")

    else:
        print("Usage:")
        print("  python clear_cache.py status          # Check cache status")
        print("  python clear_cache.py clear           # Clear all cache")
        print("  python clear_cache.py clear cities    # Clear specific cache")
        print("")

        # Default: show status
        check_cache_status()

        # Ask user what to do
        print("🤔 What would you like to do?")
        print("1. Clear all cache")
        print("2. Clear cities cache only")
        print("3. Clear water sources cache only")
        print("4. Exit")

        try:
            choice = input("\nEnter choice (1-4): ").strip()

            if choice == "1":
                clear_all_cache()
            elif choice == "2":
                clear_specific_cache("cities")
            elif choice == "3":
                clear_specific_cache("water_sources")
            elif choice == "4":
                print("👋 Goodbye!")
            else:
                print("❌ Invalid choice")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
