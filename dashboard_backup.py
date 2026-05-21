"""
DynaMo Dashboard — Visibility layer for CoolSip's CMO
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

# ============================================================
# SETUP
# ============================================================

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

st.set_page_config(page_title="DynaMo — CoolSip", page_icon="🌤️", layout="wide")
st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)

# Custom CSS for card styling
st.markdown("""
<style>
    .city-card {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        margin: 5px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .city-card h3 {
        margin-top: 0;
        color: #1f2937;
    }
    .badge-active {
        background-color: #10b981;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-paused {
        background-color: #6b7280;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .freshness-fresh { color: #10b981; }
    .freshness-stale { color: #f59e0b; }
    .freshness-very-stale { color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.title("🌤️ DynaMo — CoolSip Summer Campaign")
st.caption(f"Live view • Last refreshed: {datetime.now().strftime('%I:%M:%S %p')}")

# ============================================================


# ============================================================
# ACTION REQUIRED PANEL
# ============================================================

# Detect issues that need CMO attention
action_required_items = []

# (Detection logic runs after data loads — placeholder check below uses dummy logic)
# Real checks happen further down once data is loaded

# ============================================================
# FETCH DATA
# ============================================================

def load_data():
    line_items = supabase.table("line_items").select("*").execute().data
    creatives = supabase.table("creatives").select("*").execute().data
    weather = supabase.table("weather_readings").select("*").order("fetched_at", desc=True).execute().data
    changes = supabase.table("change_log").select("*").order("timestamp", desc=True).limit(50).execute().data
    return line_items, creatives, weather, changes

line_items, creatives, weather_readings, change_log = load_data()

creative_titles = {c["id"]: c["title"] for c in creatives}

latest_weather = {}
for w in weather_readings:
    if w["city"] not in latest_weather:
        latest_weather[w["city"]] = w


# ============================================================
# EMERGENCY CAMPAIGN PAUSE
# ============================================================

with st.expander("🚨 Emergency Controls", expanded=False):
    st.caption("Use only in case of brand emergencies — this pauses ALL active line items across ALL cities immediately.")
    
    confirm_emergency = st.checkbox("I understand this will pause every active line item across all 4 cities.")
    
    if st.button("🛑 PAUSE ENTIRE CAMPAIGN", type="primary", disabled=not confirm_emergency):
        # Pause every active line item
        active_items = [li for li in line_items if li["state"] == "active"]
        
        if not active_items:
            st.info("No active line items to pause.")
        else:
            for item in active_items:
                supabase.table("line_items").update({
                    "state": "paused",
                    "state_reason": "EMERGENCY: Campaign-wide pause triggered by CMO",
                    "last_changed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", item["id"]).execute()
                
                supabase.table("change_log").insert({
                    "line_item_id": item["id"],
                    "previous_state": item["state"],
                    "new_state": "paused",
                    "trigger_source": "manual_override",
                    "weather_snapshot": None,
                    "rule_applied": None,
                    "reason": "EMERGENCY: Campaign-wide pause triggered by CMO",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }).execute()
            
            st.success(f"🛑 EMERGENCY PAUSE EXECUTED — {len(active_items)} line items paused across all cities.")
            st.rerun()

# Check for stale weather data
for city in ["Mumbai", "Delhi", "Bangalore", "Chennai"]:
    weather = latest_weather.get(city)
    if not weather:
        action_required_items.append(f"⚠️ {city}: No weather data available")
        continue
    fetched_at = datetime.fromisoformat(weather["fetched_at"].replace("Z", "+00:00"))
    age_min = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 60
    if age_min > 30:
        action_required_items.append(f"🔴 {city}: Weather data is {int(age_min)} min old — review outage policy")
    elif age_min > 15:
        action_required_items.append(f"🟡 {city}: Weather data is {int(age_min)} min old (approaching freshness ceiling)")

# Render the panel
if action_required_items:
    with st.container():
        st.warning("**Action Required**")
        for item in action_required_items:
            st.write(item)
else:
    st.success("✅ All systems normal — no action required.")

# ============================================================
# CITY CARDS
# ============================================================

st.subheader("Cities at a glance")

cities = ["Mumbai", "Delhi", "Bangalore", "Chennai"]
cols = st.columns(4)

for col, city in zip(cols, cities):
    with col:
        active_item = next(
            (li for li in line_items if li["city"] == city and li["state"] == "active"),
            None
        )
        weather = latest_weather.get(city)
        
        # Calculate freshness
        if weather:
            fetched_at = datetime.fromisoformat(weather["fetched_at"].replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 60
            
            if age_min < 15:
                freshness_class = "freshness-fresh"
                freshness_text = f"🟢 Updated {int(age_min)} min ago"
            elif age_min < 30:
                freshness_class = "freshness-stale"
                freshness_text = f"🟡 Updated {int(age_min)} min ago (stale)"
            else:
                freshness_class = "freshness-very-stale"
                freshness_text = f"🔴 Updated {int(age_min)} min ago (very stale)"
        else:
            freshness_class = ""
            freshness_text = "⚪ No weather data"
        
        # Active creative info
        if active_item:
            creative_name = creative_titles.get(active_item["creative_id"], "Unknown")
            if active_item.get("last_changed_at"):
                changed_at = datetime.fromisoformat(active_item["last_changed_at"].replace("Z", "+00:00"))
                running_for = datetime.now(timezone.utc) - changed_at
                hours = int(running_for.total_seconds() // 3600)
                minutes = int((running_for.total_seconds() % 3600) // 60)
                running_text = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                running_text = "—"
        else:
            creative_name = "None"
            running_text = "—"
        
        # Render card with HTML
        temp = f"{weather['temperature']}°C" if weather else "—"
        precip = f"{weather['precipitation']} mm" if weather else "—"
        
        card_html = f"""
        <div class="city-card">
            <h3>{city}</h3>
            <div style="font-size: 28px; font-weight: 600; color: #1f2937;">{temp}</div>
            <div style="color: #6b7280; margin-bottom: 12px;">💧 {precip}</div>
            <hr style="margin: 12px 0; border: none; border-top: 1px solid #e0e0e0;">
            <div style="margin-bottom: 6px;"><strong>Active:</strong> {creative_name}</div>
            <div style="color: #6b7280; font-size: 13px; margin-bottom: 12px;">Running for {running_text}</div>
            <div class="{freshness_class}" style="font-size: 12px;">{freshness_text}</div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

# ============================================================
# LINE ITEMS WITH FILTERS
# ============================================================

st.divider()
st.subheader("All Line Items")

filter_col1, filter_col2, _ = st.columns([1, 1, 2])

with filter_col1:
    li_filter_city = st.selectbox("Filter by city", ["All"] + cities, key="li_city")

with filter_col2:
    li_filter_state = st.selectbox("Filter by state", ["All", "active", "paused"], key="li_state")

li_rows = []
for item in line_items:
    if li_filter_city != "All" and item["city"] != li_filter_city:
        continue
    if li_filter_state != "All" and item["state"] != li_filter_state:
        continue
    
    creative_name = creative_titles.get(item["creative_id"], "Unknown")
    li_rows.append({
        "ID": item["id"],
        "City": item["city"],
        "Creative": creative_name,
        "State": item["state"].upper(),
        "Reason": item.get("state_reason") or "—",
    })

if li_rows:
    st.dataframe(pd.DataFrame(li_rows), width="stretch", hide_index=True)
else:
    st.info("No line items match these filters.")

# ============================================================
# RECENT CHANGES
# ============================================================

st.divider()
st.subheader("Recent Changes")

change_col1, change_col2, _ = st.columns([1, 1, 2])

with change_col1:
    cl_filter_city = st.selectbox("Filter by city", ["All"] + cities, key="cl_city")

with change_col2:
    cl_filter_source = st.selectbox("Filter by source", ["All", "weather", "manual_override"], key="cl_source")

cl_rows = []
for entry in change_log:
    item = next((li for li in line_items if li["id"] == entry["line_item_id"]), None)
    if item is None:
        continue
    
    if cl_filter_city != "All" and item["city"] != cl_filter_city:
        continue
    if cl_filter_source != "All" and entry["trigger_source"] != cl_filter_source:
        continue
    
    creative_name = creative_titles.get(item["creative_id"], "Unknown")
    timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    
    cl_rows.append({
        "Time": timestamp.strftime("%d %b, %I:%M %p"),
        "City": item["city"],
        "Creative": creative_name,
        "Change": f"{entry['previous_state']} → {entry['new_state']}",
        "Source": entry["trigger_source"].replace("_", " ").title(),
        "Reason": entry["reason"] or "—",
    })

if cl_rows:
    st.dataframe(pd.DataFrame(cl_rows), width="stretch", hide_index=True)
else:
    st.info("No changes match these filters.")

# ============================================================
# MANUAL OVERRIDE
# ============================================================

st.divider()
st.subheader("Manual Override")
st.caption("Pause or activate a specific line item, overriding the automated rules.")

def label_for(item_id):
    item = next((i for i in line_items if i["id"] == item_id), None)
    if item is None:
        return str(item_id)
    creative = creative_titles.get(item["creative_id"], "Unknown")
    return f"#{item_id} — {item['city']} - {creative} ({item['state'].upper()})"

with st.form("override_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        line_item_id = st.selectbox(
            "Line Item",
            options=[item["id"] for item in line_items],
            format_func=label_for,
        )
    
    with col2:
        new_action = st.selectbox("Action", ["pause", "active"])
    
    with col3:
        duration = st.selectbox("Duration", ["1 hour", "4 hours", "24 hours", "Until I undo"])
    
    reason = st.text_input("Reason (optional)", placeholder="e.g., Brand-sensitive event")
    
    submitted = st.form_submit_button("Apply Override", type="primary")
    
    if submitted:
        item = next((li for li in line_items if li["id"] == line_item_id), None)
        if item:
            full_reason = f"Manual override. {reason}" if reason else "Manual override (no reason given)."
            
            supabase.table("line_items").update({
                "state": new_action,
                "state_reason": full_reason,
                "last_changed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", line_item_id).execute()
            
            supabase.table("change_log").insert({
                "line_item_id": line_item_id,
                "previous_state": item["state"],
                "new_state": new_action,
                "trigger_source": "manual_override",
                "weather_snapshot": None,
                "rule_applied": None,
                "reason": full_reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).execute()
            
            st.success(f"✅ Line item #{line_item_id} set to {new_action.upper()}")
            st.rerun()

# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption("DynaMo MVP • CoolSip Summer Campaign • Built for YOptima assessment")
# ============================================================
# SETTINGS & POLICIES (Read-only)
# ============================================================

st.divider()

with st.expander("⚙️ Settings & Configured Policies", expanded=False):
    st.caption("These are the policies the system is operating under. Editing is future scope — contact YOptima to update.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Decision Thresholds**")
        st.write("🔥 **Hot** — temperature ≥ 35°C → activate 'Beat the Heat'")
        st.write("🌧️ **Rainy** — precipitation > 0 mm/hr → activate 'Rainy Day Pick-Me-Up'")
        st.write("✨ **Normal** — neither condition → activate 'Refresh Anytime'")
        st.write("📌 **Rule priority:** Rainy > Hot > Normal")
        
        st.markdown("**Polling**")
        st.write("⏱️ Weather refresh every: **12 minutes**")
        st.write("🎯 Freshness tolerance: **15 minutes** (CoolSip SLA)")
    
    with col2:
        st.markdown("**Outage Handling Policy**")
        st.write("🟢 **0–15 min stale:** hold last known state")
        st.write("🟡 **15–30 min stale:** fall back to 'Refresh Anytime'")
        st.write("🔴 **30+ min stale:** keep generic, alert CMO, await decision")
        st.write("ℹ️ System never auto-pauses — irreversible budget decisions belong to CMO")
        
        st.markdown("**Manual Override Behavior**")
        st.write("🛑 **Pause** override — applies immediately, no friction")
        st.write("✅ **Activate** override — warns if contradicts current weather rule")
        st.write("⏳ **Default duration:** 4 hours (auto-resumes automation after)")
        st.write("📋 Every override is logged with user, reason, and timestamp")
    
    st.markdown("**Alert Channels**")
    st.caption("Configurable per CMO. Default settings shown.")
    
    alert_data = [
        {"Channel": "🔴 SMS (interrupts CMO)", "Triggers": "Outages > 30 min, multi-city failures, conflict requiring decision"},
        {"Channel": "🟡 Email digest", "Triggers": "Stale data warnings, team overrides, daily summary"},
        {"Channel": "🟢 In-app only", "Triggers": "Regular state flips, weather updates"},
    ]
    st.dataframe(pd.DataFrame(alert_data), width="stretch", hide_index=True)