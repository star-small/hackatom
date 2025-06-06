#!/usr/bin/env python3
"""
Reset Kazakhstan NPP data to ensure Kazakhstan-only geographic data
"""

import os
import glob
import sqlite3
import shutil
from datetime import datetime


def reset_all_cache():
    """Remove all cached data to force fresh Kazakhstan-only queries"""
    cache_dir = "data_cache"

    print("🗑️ Resetting Kazakhstan NPP geographic data cache...")
    print("=" * 50)

    if not os.path.exists(cache_dir):
        print("📁 No cache directory found - will be created fresh")
        return

    # Remove all cache files
    cache_files = glob.glob(f"{cache_dir}/*.geojson")
    metadata_file = f"{cache_dir}/cache_metadata.db"

    removed_count = 0

    for file in cache_files:
        try:
            os.remove(file)
            filename = os.path.basename(file)
            print(f"   ✅ Removed {filename}")
            removed_count += 1
        except Exception as e:
            print(f"   ❌ Failed to remove {file}: {e}")

    # Remove metadata
    if os.path.exists(metadata_file):
        try:
            os.remove(metadata_file)
            print(f"   ✅ Removed cache metadata")
            removed_count += 1
        except Exception as e:
            print(f"   ⚠️ Failed to remove metadata: {e}")

    print(f"\n🎯 Cache Reset Complete!")
    print(f"   📊 Removed {removed_count} cache files")
    print(f"   🔄 Next run will fetch fresh Kazakhstan-only data")
    print(f"   ⏱️  First run may take 3-5 minutes to download data")


def check_current_cache():
    """Check what's currently in cache"""
    cache_dir = "data_cache"

    print("📊 Current Cache Status:")
    print("=" * 30)

    if not os.path.exists(cache_dir):
        print("📁 No cache directory")
        return

    data_types = ['cities', 'water_sources', 'seismic_zones', 'transportation']

    for data_type in data_types:
        cache_file = f"{cache_dir}/kazakhstan_{data_type}.geojson"

        if os.path.exists(cache_file):
            try:
                file_size = os.path.getsize(cache_file) / 1024  # KB
                mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file))

                print(f"✅ {data_type}:")
                print(f"   📏 Size: {file_size:.1f} KB")
                print(f"   📅 Modified: {
                      mod_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Try to count features
                try:
                    import json
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        feature_count = len(data.get('features', []))
                        print(f"   📊 Features: {feature_count}")

                        # Flag potential issues
                        if data_type == 'cities' and feature_count == 0:
                            print(f"   ⚠️ No cities - needs reset")
                        elif data_type == 'water_sources' and feature_count > 1000:
                            print(f"   ⚠️ Too many water sources - needs filtering")
                        elif data_type == 'cities' and feature_count < 10:
                            print(f"   ⚠️ Very few cities - might need reset")

                except Exception as e:
                    print(f"   ❌ Can't read features: {e}")

            except Exception as e:
                print(f"❌ {data_type}: Error - {e}")
        else:
            print(f"📭 {data_type}: No cache")

        print()


def show_expected_data():
    """Show what data should be loaded for Kazakhstan"""
    print("🎯 Expected Kazakhstan Data:")
    print("=" * 30)

    print("🏙️ Cities (15-20 expected):")
    cities = [
        "Almaty", "Nur-Sultan", "Shymkent", "Aktobe", "Taraz",
        "Pavlodar", "Oskemen", "Karaganda", "Aktau", "Atyrau",
        "Kostanay", "Petropavl", "Oral", "Semey", "Taldykorgan"
    ]
    for city in cities:
        print(f"   • {city}")

    print(f"\n💧 Water Sources (20-50 expected):")
    water_sources = [
        "Lake Balkhash", "Caspian Sea", "Irtysh River", "Ishim River",
        "Ili River", "Syr Darya", "Ural River", "Tobol River",
        "Lake Alakol", "Kapchagai Reservoir"
    ]
    for source in water_sources:
        print(f"   • {source}")

    print(f"\n⚡ Seismic Zones (7 expected):")
    seismic_zones = [
        "Almaty-Tien Shan Seismic Zone (High Risk)",
        "Altai Mountain Seismic Zone (High Risk)",
        "Central Kazakhstan Stable Platform (Low Risk)",
        "West Kazakhstan Basin (Low Risk)",
        "Balkhash-Ili Transition Zone (Medium Risk)",
        "Irtysh River Valley (Medium Risk)",
        "Mangystau Peninsula (Medium-High Risk)"
    ]
    for zone in seismic_zones:
        print(f"   • {zone}")

    print(f"\n🛣️ Transportation (50-200 expected):")
    print(f"   • Major highways within Kazakhstan")
    print(f"   • Railway lines (Trans-Kazakhstan Railway)")
    print(f"   • Major airports (Almaty, Nur-Sultan, etc.)")


if __name__ == "__main__":
    import sys

    print("🇰🇿 Kazakhstan NPP Data Reset Tool")
    print("=" * 40)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "reset":
            reset_all_cache()
        elif command == "check":
            check_current_cache()
        elif command == "expected":
            show_expected_data()
        else:
            print("❌ Unknown command. Use: reset, check, or expected")

    else:
        print("🔍 Checking current cache status...")
        check_current_cache()

        print("\n🤔 What would you like to do?")
        print("1. Reset all cache (recommended)")
        print("2. Show expected data for Kazakhstan")
        print("3. Exit")

        try:
            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                print()
                reset_all_cache()
                print("\n📝 Next steps:")
                print("   1. Run: python3 app.py")
                print("   2. Wait 3-5 minutes for fresh Kazakhstan data download")
                print("   3. Check console for 'Kazakhstan-only' confirmation messages")

            elif choice == "2":
                print()
                show_expected_data()

            elif choice == "3":
                print("👋 Goodbye!")

            else:
                print("❌ Invalid choice")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
