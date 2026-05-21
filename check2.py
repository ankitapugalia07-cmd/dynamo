import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

cities = supabase.table("cities").select("*").execute().data
line_items = supabase.table("line_items").select("*").execute().data

print("=== CITIES ===")
for c in cities:
    print(f"  id={c['id']}, name={c['name']}")

print("\n=== LINE ITEMS: city_id check ===")
for li in line_items:
    print(f"  id={li['id']}, city={li.get('city')}, city_id={li.get('city_id')}")