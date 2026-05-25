"""
DynaMo Dashboard — Visibility layer for CoolSip's CMO
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, date
from dotenv import load_dotenv
from supabase import create_client
from streamlit_autorefresh import st_autorefresh

from manual_override import is_manual_weather_lock

# ============================================================
# SETUP
# ============================================================

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

st.set_page_config(page_title="DynaMo — CoolSip", page_icon="🌤️", layout="wide")

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
    }

    iframe {
        pointer-events: none;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FETCH DATA
# ============================================================

def load_data():
    line_items = supabase.table("line_items").select("*").execute().data
    creatives = supabase.table("creatives").select("*").execute().data
    cities_data = supabase.table("cities").select("*").execute().data
    weather = (
        supabase.table("weather_readings")
        .select("*")
        .order("fetched_at", desc=True)
        .limit(100)
        .execute()
        .data
    )
    changes = supabase.table("change_log").select("*").order("timestamp", desc=True).limit(100).execute().data
    return line_items, creatives, cities_data, weather, changes

line_items, creatives, cities_data, weather_readings, change_log = load_data()

creative_titles = {c["id"]: c["title"] for c in creatives}
CITIES = [c["name"] for c in cities_data]

latest_weather = {}

sorted_weather = sorted(
    weather_readings,
    key=lambda x: x["fetched_at"],
    reverse=True
)

for w in sorted_weather:
    city = w["city"]
    if city not in latest_weather:
        latest_weather[city] = w
# Fixed dummy KPIs (deterministic, won't change on scroll)
DUMMY = {}
for li in line_items:
    base = li["id"] * 37
    if li["state"] == "active":
        DUMMY[li["id"]] = {
            "impressions": 80000 + base * 1000 % 120000,
            "clicks": 200 + base % 300,
            "kpi": 10 + base % 30,
        }
    else:
        DUMMY[li["id"]] = {"impressions": 0, "clicks": 0, "kpi": 0}

def fmt_num(n):
    if n == 0: return "—"
    if n >= 1000000: return f"{n/1000000:.1f}M"
    if n >= 1000: return f"{n/1000:.1f}K"
    return str(n)

def running_duration(item):
    if item["state"] != "active" or not item.get("last_changed_at"):
        return "—"
    changed = datetime.fromisoformat(item["last_changed_at"].replace("Z", "+00:00"))
    d = datetime.now(timezone.utc) - changed
    h, m = int(d.total_seconds() // 3600), int((d.total_seconds() % 3600) // 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def last_changed_str(item):
    if not item.get("last_changed_at"): return "—"
    return datetime.fromisoformat(item["last_changed_at"].replace("Z", "+00:00")).strftime("%d %b, %I:%M %p")

def freshness_age(city):
    w = latest_weather.get(city)
    if not w: return None
    fetched = datetime.fromisoformat(w["fetched_at"].replace("Z", "+00:00"))
    return int((datetime.now(timezone.utc) - fetched).total_seconds() / 60)

def freshness_dot(city):
    age = freshness_age(city)
    if age is None: return "⚪", "no data"
    if age < 15: return "🟢", f"{age} min ago"
    if age < 30: return "🟡", f"{age} min ago (stale)"
    return "🔴", f"{age} min ago (very stale)"

# ============================================================
# HEADER
# ============================================================

st.title("🌤️ DynaMo — CoolSip Summer Campaign")
st.caption(f"Real-time campaign control • Last refreshed: {datetime.now().strftime('%I:%M:%S %p')}")
if st.button("🔄 Refresh data"):
    st.rerun()

# ============================================================
# SECTION 1 — KPI CARDS + CHART
# ============================================================

total_imp = sum(DUMMY[li["id"]]["impressions"] for li in line_items)
total_clk = sum(DUMMY[li["id"]]["clicks"] for li in line_items)
total_kpi = sum(DUMMY[li["id"]]["kpi"] for li in line_items)
active_count = len([li for li in line_items if li["state"] == "active"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Impressions (demo)", fmt_num(total_imp), "+10.1%")
c2.metric("Clicks (demo)", fmt_num(total_clk), "-5.3%")
c3.metric("KPI Events (demo)", fmt_num(total_kpi), "+7.2%")
c4.metric("Active Line Items", f"{active_count} / {len(line_items)}")

# Weather API status card — per-city tick/cross
st.markdown("**🌤️ Live Market Conditions**")
ws = st.columns(len(CITIES))
for col, city in zip(ws, CITIES):
    age = freshness_age(city)
    if age is None:
        col.markdown(f"❌ **{city}**<br><span style='color:#ef4444;font-size:12px;'>No data</span>", unsafe_allow_html=True)
    elif age < 15:
        col.markdown(f"✅ **{city}**<br><span style='color:#10b981;font-size:12px;'>{age} min ago</span>", unsafe_allow_html=True)
    elif age < 30:
        col.markdown(f"⚠️ **{city}**<br><span style='color:#f59e0b;font-size:12px;'>{age} min ago</span>", unsafe_allow_html=True)
    else:
        col.markdown(f"❌ **{city}**<br><span style='color:#ef4444;font-size:12px;'>{age} min stale</span>", unsafe_allow_html=True)

st.caption("📊 Impressions / Clicks / KPI are demo data — DynaMo controls which ad runs; the ad platform measures performance.")

# Fixed trend chart (static data, won't change on scroll)
trend_df = pd.DataFrame({
    "Day": ["15 May", "16 May", "17 May", "18 May", "19 May", "20 May", "21 May"],
    "Impressions": [95, 110, 102, 118, 125, 108, 115],
    "Clicks": [30, 35, 32, 40, 42, 38, 36],
    "KPI Events": [8, 12, 10, 15, 14, 11, 13],
}).set_index("Day")
st.markdown("**KPI Trend (Last 7 Days)** — demo data")
st.line_chart(
    trend_df,
    height=220,
    use_container_width=True
)

st.divider()

# ============================================================
# SECTION 2 — CITY / LINE ITEM TABLE
# ============================================================

st.subheader("Campaigns by City")

def toggle(item, ns):
    supabase.table("line_items").update({"state": ns, "state_reason": f"Manual {ns} by CMO", "last_changed_at": datetime.now(timezone.utc).isoformat()}).eq("id", item["id"]).execute()
    supabase.table("change_log").insert({"line_item_id": item["id"], "previous_state": item["state"], "new_state": ns, "trigger_source": "manual_override", "weather_snapshot": None, "rule_applied": None, "reason": f"Manual {ns} by CMO", "timestamp": datetime.now(timezone.utc).isoformat()}).execute()

# ---- Collapsed: city summary as aligned table with headers ----
st.markdown("**Cities Overview**")
ch = st.columns([0.5, 1.5, 1.8, 1.8, 1, 1])
ch[0].caption("**Status**")
ch[1].caption("**City**")
ch[2].caption("**Weather**")
ch[3].caption("**Running**")
ch[4].caption("**Impr**")
ch[5].caption("**Clicks**")

for city in CITIES:
    city_items = [li for li in line_items if li["city"] == city]
    dot, fresh = freshness_dot(city)
    active_item = next((li for li in city_items if li["state"] == "active"), None)
    running = creative_titles.get(active_item["creative_id"], "None") if active_item else "None"
    cimp = sum(DUMMY[li["id"]]["impressions"] for li in city_items)
    cclk = sum(DUMMY[li["id"]]["clicks"] for li in city_items)

    cr = st.columns([0.4, 1.4, 1.3, 1.8, 0.8, 0.8])

    cr[0].markdown(f"<div style='padding-top:4px'>{dot}</div>", unsafe_allow_html=True)

    cr[1].markdown(
        f"<div style='font-size:14px'><b>{city}</b> ({len(city_items)})</div>",
        unsafe_allow_html=True
    )

    cr[2].markdown(
        f"<div style='font-size:13px'>{fresh}</div>",
        unsafe_allow_html=True
    )

    cr[3].markdown(
        f"<div style='font-size:13px'>{running}</div>",
        unsafe_allow_html=True
    )

    cr[4].markdown(
        f"<div style='font-size:13px'>{fmt_num(cimp)}</div>",
        unsafe_allow_html=True
    )

    cr[5].markdown(
        f"<div style='font-size:13px'>{fmt_num(cclk)}</div>",
        unsafe_allow_html=True
    )
st.divider()

# ---- Expanded per city: line item table with per-row action dropdown ----
st.markdown("**Line Item Details**")
tb1, tb2, tb3, tb4 = st.columns([1, 1.3, 1, 1])

with tb1:
    if st.button("⏸ Pause All", key="btn_pause_all"):
        st.session_state["confirm_activate_all"] = False
        st.session_state["confirm_pause_all"] = True

with tb2:
    if st.button("▶ Activate All (by weather)", key="btn_activate_all"):
        st.session_state["confirm_pause_all"] = False
        st.session_state["confirm_activate_all"] = True

with tb3:
    expand_all = st.toggle("Expand all")

with tb4:
    state_filter = st.selectbox(
        "Show",
        ["All", "active", "paused"],
        label_visibility="collapsed"
    )

# Bulk actions — confirmation must render here (after buttons), not under "Campaigns by City"
if st.session_state.get("confirm_pause_all"):
    active_items = [li for li in line_items if li["state"] == "active"]
    st.warning(f"⚠️ This pauses **{len(active_items)} active line items** across all cities. Continue?")
    cc1, cc2 = st.columns(2)
    if cc1.button("✅ Yes, pause all", key="confirm_pause_yes"):
        for item in active_items:
            supabase.table("line_items").update({"state": "paused", "state_reason": "Bulk pause-all by CMO", "last_changed_at": datetime.now(timezone.utc).isoformat()}).eq("id", item["id"]).execute()
            supabase.table("change_log").insert({"line_item_id": item["id"], "previous_state": "active", "new_state": "paused", "trigger_source": "manual_override", "weather_snapshot": None, "rule_applied": None, "reason": "Bulk pause-all by CMO", "timestamp": datetime.now(timezone.utc).isoformat()}).execute()
        st.session_state["confirm_pause_all"] = False
        st.rerun()
    if cc2.button("Cancel", key="confirm_pause_cancel"):
        st.session_state["confirm_pause_all"] = False
        st.rerun()

if st.session_state.get("confirm_activate_all"):
    st.warning("⚠️ Re-applies current weather rules per city — activates the correct creative for each city's weather. Does NOT activate every line item. Continue?")
    ac1, ac2 = st.columns(2)
    if ac1.button("✅ Yes, re-apply rules", key="confirm_activate_yes"):
        rules = sorted(supabase.table("rules").select("*").execute().data, key=lambda r: r["priority"])
        for city in CITIES:
            w = latest_weather.get(city)
            if not w: continue
            winner = None
            for rule in rules:
                p = rule["parameter"]
                if p == "default":
                    winner = rule; break
                val = w["temperature"] if p == "temperature" else w["precipitation"]
                if (rule["operator"] == ">=" and val >= rule["value"]) or (rule["operator"] == ">" and val > rule["value"]):
                    winner = rule; break
            if not winner: continue
            for item in [li for li in line_items if li["city"] == city]:
                if is_manual_weather_lock(item):
                    continue
                ns = "active" if item["creative_id"] == winner["creative_id"] else "paused"
                if item["state"] != ns:
                    reason = f"Re-applied rule '{winner['name']}' (temp={w['temperature']}°C)"
                    supabase.table("line_items").update({"state": ns, "state_reason": reason, "last_changed_at": datetime.now(timezone.utc).isoformat()}).eq("id", item["id"]).execute()
                    supabase.table("change_log").insert({"line_item_id": item["id"], "previous_state": item["state"], "new_state": ns, "trigger_source": "manual_override", "weather_snapshot": w, "rule_applied": winner["name"], "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()}).execute()
        st.session_state["confirm_activate_all"] = False
        st.rerun()
    if ac2.button("Cancel", key="confirm_activate_cancel"):
        st.session_state["confirm_activate_all"] = False
        st.rerun()

for city in CITIES:
    city_items = [li for li in line_items if li["city"] == city]
    dot, fresh = freshness_dot(city)

    with st.expander(f"{dot} {city} ({len(city_items)})", expanded=expand_all or city == CITIES[0]):
        # Header row
        h = st.columns([1.3, 1.8, 3, 1.2, 1.5, 1.3])
        h[0].caption("**Status**")
        h[1].caption("**Creative**")
        h[2].caption("**Why**")
        h[3].caption("**Running**")
        h[4].caption("**KPIs (demo)**")
        h[5].caption("**Action**")

        shown = 0
        for item in city_items:
            if state_filter != "All" and item["state"] != state_filter:
                continue
            shown += 1
            k = DUMMY[item["id"]]
            is_active = item["state"] == "active"
            is_manual = is_manual_weather_lock(item)
            status_txt = ("🟢 ACTIVE" if is_active else "🟡 PAUSED") + (" 🔒" if is_manual else "")

            row = st.columns([1.3, 1.8, 3, 1.2, 1.5, 1.3])
            row[0].write(status_txt)
            row[1].write(creative_titles.get(item["creative_id"], "?"))
            row[2].caption(f"{item.get('state_reason') or '—'}  \n_{last_changed_str(item)}_")
            row[3].write(running_duration(item))
            row[4].caption(f"Impr {fmt_num(k['impressions'])}  \nClk {fmt_num(k['clicks'])} · KPI {fmt_num(k['kpi'])}")
            with row[5]:
                action = st.selectbox(
                    "act",
                    [
                        "—",
                        "Pause (1 hr)",
                        "Pause (3 hrs)",
                        "Pause (Until Resume)",
                        "Activate"
                    ],
                    key=f"act_{item['id']}",
                    label_visibility="collapsed",
                )
                if "Pause" in action and is_active:
                    pause_reason = action.replace("Pause ", "")
                    supabase.table("line_items").update({
                        "state": "paused",
                        "state_reason": f"Manual pause {pause_reason} by CMO",
                        "last_changed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", item["id"]).execute()
                    supabase.table("change_log").insert({
                        "line_item_id": item["id"],
                        "previous_state": item["state"],
                        "new_state": "paused",
                        "trigger_source": "manual_override",
                        "weather_snapshot": None,
                        "rule_applied": None,
                        "reason": f"Manual pause {pause_reason} by CMO",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                    st.rerun()
                if action == "Activate" and not is_active:
                    toggle(item, "active")
                    st.rerun()

        st.divider()
        if shown == 0:
            st.caption("No line items match the filter.")

# ============================================================
# SECTION 3 — CHANGE LOG
# ============================================================

st.subheader("Change Log")

f = st.columns(5)
date_from = f[0].date_input("From", value=date(2026, 5, 1))
date_to = f[1].date_input("To", value=date.today())
cl_city = f[2].selectbox("City", ["All"] + CITIES)
cl_source = f[3].selectbox("Source", ["All", "weather", "manual_override"])
f[4].write("")
f[4].button("Apply")

rows = []
for entry in change_log:
    item = next((li for li in line_items if li["id"] == entry["line_item_id"]), None)
    if not item: continue
    ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    if not (date_from <= ts.date() <= date_to): continue
    if cl_city != "All" and item["city"] != cl_city: continue
    if cl_source != "All" and entry["trigger_source"] != cl_source: continue
    rows.append({
        "Time": ts.strftime("%d %b, %I:%M %p"),
        "City": item["city"],
        "Creative": creative_titles.get(item["creative_id"], "?"),
        "Change": f"{entry['previous_state']} → {entry['new_state']}",
        "Source": entry["trigger_source"].replace("_", " ").title(),
        "Reason": entry["reason"] or "—",
    })

if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("No changes match these filters.")

st.divider()

# ============================================================
# SECTION 4 — SETTINGS
# ============================================================

with st.expander("⚙️ Settings & Configured Policies", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Decision Thresholds**")
        st.write("🔥 Hot — temp ≥ 35°C → Beat the Heat")
        st.write("🌧️ Rainy — precipitation > 0 → Rainy Day Pick-Me-Up")
        st.write("✨ Normal — neither → Refresh Anytime")
        st.write("📌 Priority: Rainy > Hot > Normal")
        st.markdown("**Polling**")
        st.write("⏱️ Refresh every 12 min · Freshness tolerance 15 min")
    with col2:
        st.markdown("**Outage Policy**")
        st.write("🟢 0–15 min stale: hold last state")
        st.write("🟡 15–30 min: fall back to Refresh Anytime")
        st.write("🔴 30+ min: keep generic, alert CMO, await decision")
        st.markdown("**Override Behavior**")
        st.write("Default duration 4h · all overrides logged with reason")

    st.markdown("**🔔 CMO Alert Policy** — when the CMO is notified")
    alert_data = [
        {"Channel": "🔴 SMS (interrupts)", "When": "Outage >30 min, multi-city failure, conflict needing a decision"},
        {"Channel": "🟡 Email digest", "When": "Stale-data warnings, team overrides, end-of-day summary"},
        {"Channel": "🟢 In-app only", "When": "Routine weather-driven state flips"},
    ]
    st.dataframe(pd.DataFrame(alert_data), width="stretch", hide_index=True)

st.divider()
st.caption("DynaMo MVP • CoolSip Summer Campaign • Built for YOptima assessment")