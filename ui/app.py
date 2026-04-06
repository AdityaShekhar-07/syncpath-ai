"""
ui/app.py — SyncPath Streamlit Dashboard.

Run with: streamlit run ui/app.py
Requires the FastAPI server to be running on localhost:8000.
"""

import streamlit as st
import httpx
import json

API = "http://localhost:8000"

st.set_page_config(page_title="SyncPath AI", page_icon="🚇", layout="wide")

# ── Sidebar — User Profile ─────────────────────────────────────────────────────

with st.sidebar:
    st.title("🚇 SyncPath AI")
    st.caption("Autonomous Last-Mile Transit Orchestrator")
    st.divider()

    st.subheader("👤 User Profile")
    user_id = st.text_input("User ID", value="commuter_01")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Load Profile", use_container_width=True):
            r = httpx.get(f"{API}/personalization/get-profile/{user_id}")
            if r.status_code == 200:
                st.session_state["profile"] = r.json()
                st.success("Profile loaded")
            else:
                st.warning("User not found")

    with col2:
        if st.button("Create User", use_container_width=True):
            r = httpx.post(f"{API}/personalization/create-user", json={"user_id": user_id})
            if r.status_code == 201:
                st.session_state["profile"] = r.json()
                st.success("Created!")
            elif r.status_code == 409:
                st.info("Already exists")
            else:
                st.error(r.text)

    st.divider()
    st.subheader("⚙️ Preferences")
    budget    = st.select_slider("Budget",    ["low", "medium", "high"], value="medium")
    urgency   = st.select_slider("Urgency",   ["low", "medium", "high"], value="medium")
    comfort   = st.select_slider("Comfort",   ["low", "medium", "high"], value="medium")
    walking   = st.select_slider("Walking Tolerance", ["low", "medium", "high"], value="medium")

    if st.button("💾 Save Preferences", use_container_width=True):
        r = httpx.post(f"{API}/personalization/update-preferences", json={
            "user_id": user_id,
            "budget_preference":  budget,
            "urgency_level":      urgency,
            "comfort_preference": comfort,
            "walking_tolerance":  walking,
        })
        if r.status_code == 200:
            st.session_state["profile"] = r.json()
            st.success("Saved!")
        else:
            st.error(r.text)

    # Show current profile
    if "profile" in st.session_state:
        p = st.session_state["profile"]
        st.divider()
        st.caption("Current Profile")
        st.json({k: v for k, v in p.items() if k != "historical_choices"})

# ── Main area ──────────────────────────────────────────────────────────────────

st.title("🗺️ Journey Planner")

tab1, tab2, tab3 = st.tabs(["🎯 Get Decision", "🚆 GTFS Status", "🚗 Ride Options"])

# ── Tab 1: Decision ────────────────────────────────────────────────────────────

with tab1:
    st.subheader("Current Situation")
    c1, c2, c3, c4 = st.columns(4)
    delay   = c1.number_input("Train Delay (min)", 0.0, 60.0, 0.0, 1.0)
    surge   = c2.number_input("Surge Multiplier",  1.0, 5.0,  1.0, 0.1)
    ride_ok = c3.checkbox("Rides Available", value=True)
    weather = c4.checkbox("Bad Weather", value=False)

    st.subheader("Transport Options")
    st.caption("Edit the options below or use defaults")

    default_options = [
        {"name": "Metro+Auto",  "travel_time": 25, "cost": 60,  "comfort": 6, "walking_distance": 300,  "available": True},
        {"name": "Uber Go",     "travel_time": 18, "cost": 180, "comfort": 9, "walking_distance": 50,   "available": True},
        {"name": "Uber Auto",   "travel_time": 22, "cost": 120, "comfort": 7, "walking_distance": 50,   "available": True},
        {"name": "Rapido Bike", "travel_time": 15, "cost": 70,  "comfort": 4, "walking_distance": 50,   "available": True},
        {"name": "Bus",         "travel_time": 40, "cost": 20,  "comfort": 3, "walking_distance": 500,  "available": True},
        {"name": "Walk",        "travel_time": 55, "cost": 0,   "comfort": 2, "walking_distance": 4000, "available": True},
    ]

    use_llm = st.checkbox("🤖 Refine explanation with Ollama (Llama3)", value=False)

    if st.button("🚀 Get Best Option", type="primary", use_container_width=True):
        payload = {
            "user_id": user_id,
            "situation": {
                "train_delay_minutes": delay,
                "surge_multiplier":    surge,
                "ride_available":      ride_ok,
                "weather_bad":         weather,
            },
            "options": default_options,
            "use_llm": use_llm,
        }
        with st.spinner("Scoring options..."):
            r = httpx.post(f"{API}/personalization/get-decision", json=payload, timeout=30)

        if r.status_code == 200:
            data = r.json()
            st.success(f"✅ Best Option: **{data['best_option']}** (score: {data['score']:.3f})")
            st.info(f"💬 {data['explanation']}")

            st.subheader("📊 Ranked Options")
            ranked = data["ranked"]
            cols = st.columns(len(ranked))
            for col, opt in zip(cols, ranked):
                status = "✅" if opt["available"] else "❌"
                col.metric(
                    label=f"{status} #{opt['rank']} {opt['name']}",
                    value=f"{opt['score']:.3f}",
                )
        elif r.status_code == 404:
            st.error(f"User '{user_id}' not found. Create the user first in the sidebar.")
        else:
            st.error(f"Error {r.status_code}: {r.text}")

# ── Tab 2: GTFS Status ─────────────────────────────────────────────────────────

with tab2:
    st.subheader("Live Transit Status")
    route_options = {"Yellow Line (YL)": "YL", "Blue Line (BL)": "BL", "Green Line (GR)": "GR"}
    selected_route_label = st.selectbox("Select Route", list(route_options.keys()))
    selected_route = route_options[selected_route_label]

    if st.button("🔄 Fetch Status", use_container_width=True):
        with st.spinner("Polling GTFS feed..."):
            r = httpx.get(f"{API}/gtfs/trip-update", params={"route_id": selected_route})

        if r.status_code == 200:
            data = r.json()
            delay_min = data["delay_minutes"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Delay", f"{delay_min:.1f} min",
                        delta=f"{delay_min:.1f} min late" if delay_min > 0 else "On time",
                        delta_color="inverse")
            col2.metric("Current Stop", data["current_stop"])
            col3.metric("Next Stop",    data["next_stop"])

            if delay_min == 0:
                st.success("🟢 Train is running on time")
            elif delay_min < 5:
                st.warning(f"🟡 Minor delay: {delay_min:.1f} minutes")
            else:
                st.error(f"🔴 Significant delay: {delay_min:.1f} minutes — consider alternatives")

            st.caption(f"Trip ID: {data['trip_id']} | Route: {data['route_id']}")
        else:
            st.error(r.text)

# ── Tab 3: Ride Options ────────────────────────────────────────────────────────

with tab3:
    st.subheader("Ride-Hailing Availability")
    c1, c2, c3 = st.columns(3)
    dist_km      = c1.number_input("Distance (km)",    1.0, 50.0, 5.0, 0.5)
    dur_min      = c2.number_input("Duration (min)",   5.0, 120.0, 20.0, 5.0)
    demand_fac   = c3.slider("Demand Factor", 0.5, 3.0, 1.0, 0.1,
                              help="1.0 = normal, 2.0+ = high demand zone")

    if st.button("🔍 Check Rides", use_container_width=True):
        with st.spinner("Checking availability..."):
            r = httpx.post(f"{API}/rides/options", json={
                "distance_km":   dist_km,
                "duration_min":  dur_min,
                "demand_factor": demand_fac,
            })

        if r.status_code == 200:
            rides = r.json()
            available = [rd for rd in rides if rd["available"]]
            unavailable = [rd for rd in rides if not rd["available"]]

            if available:
                st.success(f"{len(available)} ride(s) available")
                cols = st.columns(len(available))
                for col, ride in zip(cols, available):
                    col.metric(
                        label=ride["ride_type"],
                        value=f"₹{ride['total_fare']:.0f}",
                        delta=f"ETA {ride['eta_minutes']:.0f} min | {ride['surge_multiplier']}x surge",
                        delta_color="inverse" if ride["surge_multiplier"] > 1.5 else "normal",
                    )
            else:
                st.error("No rides available in this area")

            if unavailable:
                st.caption(f"Unavailable: {', '.join(r['ride_type'] for r in unavailable)}")
        else:
            st.error(r.text)
