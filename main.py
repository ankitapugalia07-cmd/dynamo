"""
DynaMo - Weather-triggered ad campaign system
Fetches weather for cities, evaluates rules, updates line item states.
"""

import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
import requests

from manual_override import is_manual_weather_lock

# ============================================================
# CONFIGURATION
# ============================================================

# Cities and their coordinates (you can challenge these in your write-up)
CITIES = {
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777},
    "Delhi":     {"lat": 28.6139, "lon": 77.2090},
    "Bangalore": {"lat": 12.9716, "lon": 77.5946},
    "Chennai":   {"lat": 13.0827, "lon": 80.2707},
}

# Valid ranges for data validation
VALID_TEMP_RANGE = (-50, 60)        # Celsius
VALID_PRECIP_RANGE = (0, 500)       # mm/hr

# Scheduler interval (seconds) — 12 minutes
SCHEDULER_INTERVAL = 720

# ============================================================
# SETUP
# ============================================================

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ============================================================
# WEATHER FETCHING
# ============================================================

def fetch_weather(city_name, lat, lon):
    """Fetch current weather from Open-Meteo for one city."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation",
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        temp = data["current"]["temperature_2m"]
        precip = data["current"]["precipitation"]
        
        # Validate the data is sensible
        if not (VALID_TEMP_RANGE[0] <= temp <= VALID_TEMP_RANGE[1]):
            print(f"  ⚠️  {city_name}: temperature {temp}°C out of valid range. Skipping.")
            return None
        if not (VALID_PRECIP_RANGE[0] <= precip <= VALID_PRECIP_RANGE[1]):
            print(f"  ⚠️  {city_name}: precipitation {precip}mm out of valid range. Skipping.")
            return None
        
        return {"temperature": temp, "precipitation": precip}
    
    except Exception as e:
        print(f"  ❌ {city_name}: weather fetch failed: {e}")
        return None


# city name -> id (loaded once)
CITY_IDS = {c["name"]: c["id"] for c in supabase.table("cities").select("*").execute().data}

def save_weather_reading(city, weather):
    """Save a weather reading to the database."""
    supabase.table("weather_readings").insert({
        "city": city,
        "city_id": CITY_IDS.get(city),
        "temperature": weather["temperature"],
        "precipitation": weather["precipitation"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

# ============================================================
# DECISION LOGIC
# ============================================================

def evaluate_rules(weather, rules):
    """Given weather, find which rule fires. Returns the rule, or None."""
    # Sort rules by priority (lower number = higher priority)
    sorted_rules = sorted(rules, key=lambda r: r["priority"])
    
    for rule in sorted_rules:
        param = rule["parameter"]
        op = rule["operator"]
        val = rule["value"]
        
        # The "Normal" rule (default fallback)
        if param == "default":
            return rule
        
        # Get the actual reading for this parameter
        if param == "temperature":
            reading = weather["temperature"]
        elif param == "precipitation":
            reading = weather["precipitation"]
        else:
            continue  # Unknown parameter, skip
        
        # Check the condition
        if op == ">=" and reading >= val:
            return rule
        if op == ">" and reading > val:
            return rule
        if op == "<=" and reading <= val:
            return rule
        if op == "<" and reading < val:
            return rule
    
    return None  # Should never happen if Normal rule exists

# ============================================================
# MAIN LOOP
# ============================================================

def run_cycle():
    """One full cycle: fetch weather for all cities, decide, update."""
    print(f"\n{'='*60}")
    print(f"DynaMo cycle starting at {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}")
    
    # Load rules and line items once per cycle
    rules = supabase.table("rules").select("*").execute().data
    line_items = supabase.table("line_items").select("*").execute().data
    
    # For each city, fetch weather and decide
    for city, coords in CITIES.items():
        print(f"\n📍 {city}")
        
        weather = fetch_weather(city, coords["lat"], coords["lon"])
        if weather is None:
            print(f"  Skipping {city} due to weather fetch failure.")
            continue
        
        print(f"  Weather: {weather['temperature']}°C, precipitation: {weather['precipitation']}mm")
        
        # Save the reading
        save_weather_reading(city, weather)
        
        # Find which rule fires for this weather
        winning_rule = evaluate_rules(weather, rules)
        if winning_rule is None:
            print(f"  No rule matched. Skipping.")
            continue
        
        active_creative_id = winning_rule["creative_id"]
        print(f"  Rule '{winning_rule['name']}' fires → creative_id {active_creative_id} should be active")
        
        # Update line items for this city
        city_items = [li for li in line_items if li["city"] == city]
        
        for item in city_items:
            if is_manual_weather_lock(item):
                print(f"    ⏭️  Line item {item['id']}: skipped (manual override active)")
                continue

            should_be_active = (item["creative_id"] == active_creative_id)
            new_state = "active" if should_be_active else "paused"
            
            # Only update + log if state is actually changing
            if item["state"] != new_state:
                reason = (
                    f"Rule '{winning_rule['name']}' fired "
                    f"(temp={weather['temperature']}°C, precip={weather['precipitation']}mm)"
                )
                
                # Update the line item
                supabase.table("line_items").update({
                    "state": new_state,
                    "state_reason": reason,
                    "last_changed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", item["id"]).execute()
                
                # Log the transition
                supabase.table("change_log").insert({
                    "line_item_id": item["id"],
                    "previous_state": item["state"],
                    "new_state": new_state,
                    "trigger_source": "weather",
                    "weather_snapshot": weather,
                    "rule_applied": winning_rule["name"],
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).execute()
                
                print(f"    🔄 Line item {item['id']}: {item['state']} → {new_state}")
    
    print(f"\n✅ Cycle complete.\n")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # For testing: run one cycle and exit
    # For production: change to while True with sleep
    run_cycle()
    
    # Uncomment below to run continuously every 12 min:
    # while True:
    #     run_cycle()
    #     print(f"💤 Sleeping {SCHEDULER_INTERVAL}s...")
    #     time.sleep(SCHEDULER_INTERVAL)