import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

creatives = supabase.table("creatives").select("*").execute().data
line_items = supabase.table("line_items").select("*").execute().data

print("=== CREATIVES ===")
for c in creatives:
    print(f"  id={c['id']} (type: {type(c['id']).__name__}), title={c['title']}")

print("\n=== LINE ITEMS (first 3) ===")
for li in line_items[:3]:
    print(f"  id={li['id']}, city={li['city']}, creative_id={li['creative_id']} (type: {type(li['creative_id']).__name__})")