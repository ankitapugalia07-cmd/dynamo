import os
from dotenv import load_dotenv
from supabase import create_client

# Load credentials from .env file
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# Connect to Supabase
supabase = create_client(url, key)

# Try to read line items
result = supabase.table("line_items").select("*").execute()

print(f"Connected! Found {len(result.data)} line items.")
print("\nFirst 3 line items:")
for item in result.data[:3]:
    print(f"  - {item['city']} | creative_id: {item['creative_id']} | state: {item['state']}")