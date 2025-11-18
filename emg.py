# cantilan_ers_nodb.py
import streamlit as st
import pandas as pd
import pydeck as pdk
import datetime
import time
from typing import Optional, List, Dict
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests

# ---------------- Page config & style ----------------
st.set_page_config(
    page_title="Cantilan ERS",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-repeat: no-repeat;
    }
    [data-testid="stSidebar"] {
        background-color: rgba(15, 15, 35, 0.95);
        color: white;
        backdrop-filter: blur(10px);
    }
    .main > div {
        background-color: rgba(255, 255, 255, 0.92);
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    h1, h2, h3 { 
        color: #d32f2f !important; 
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    div.stButton > button {
        background-color: #d32f2f;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        font-size: 16px;
        border: 2px solid white;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #b71c1c;
        transform: scale(1.05);
    }
    .delete-button {
        background-color: #b71c1c !important;
        color: white !important;
    }
    .dashboard-card {
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #d32f2f;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .role-specific {
        background-color: rgba(240, 248, 255, 0.9);
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid #d32f2f;
    }
    .emergency-alert {
        background: linear-gradient(135deg, #ff4444, #d32f2f);
        color: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        font-weight: bold;
    }
    .user-table {
        font-size: 0.9em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Constants ----------------
CANTILAN_CENTER = [9.3355, 125.9769]

EMERGENCY_CATEGORIES = [
    "Car Accident",
    "Flood",
    "Fight / Disturbance",
    "Fire",
    "Tsunami",
    "Landslide",
    "Fall Accident",
    "Medical",
    "Other",
]

HOTLINES = [
    {"Name": "BFP - Fire Station", "Contact": "0917-000-0000", "Address": "Brgy. Center, Cantilan, Surigao del Sur"},
    {"Name": "PNP - Police Station", "Contact": "0917-111-1111", "Address": "Municipal Hall, Cantilan, Surigao del Sur"},
    {"Name": "LGU Cantilan (DRRMO)", "Contact": "0917-222-2222", "Address": "Municipal Hall, Cantilan, Surigao del Sur"},
    {"Name": "Municipal Health Office", "Contact": "0917-333-3333", "Address": "Health Center, Cantilan, Surigao del Sur"},
]

# ---------------- Geopy Functions ----------------
@st.cache_data
def get_geocoder():
    """Initialize and cache geocoder"""
    return Nominatim(user_agent="cantilan_ers")

def geocode_address(address):
    """Geocode an address to get coordinates"""
    try:
        geolocator = get_geocoder()
        location = geolocator.geocode(f"{address}, Philippines")
        if location:
            return location.latitude, location.longitude
        else:
            return None
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None

def get_distance(coord1, coord2):
    """Calculate distance between two coordinates in kilometers"""
    try:
        return geodesic(coord1, coord2).kilometers
    except:
        return None

def get_address_from_coords(lat, lon):
    """Reverse geocode coordinates to get address"""
    try:
        geolocator = get_geocoder()
        location = geolocator.reverse(f"{lat}, {lon}")
        if location:
            return location.address
        else:
            return "Address not found"
    except Exception as e:
        return f"Error getting address: {e}"

# ---------------- Data Management (Session State) ----------------
def initialize_session_state():
    """Initialize all session state variables"""
    if "users" not in st.session_state:
        st.session_state.users = []
    
    if "sos_logs" not in st.session_state:
        st.session_state.sos_logs = []
    
    if "reports" not in st.session_state:
        st.session_state.reports = []
    
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    
    if "page" not in st.session_state:
        st.session_state.page = "home"
    
    if "hotline_coordinates" not in st.session_state:
        st.session_state.hotline_coordinates = {}

def add_user(user: dict):
    """Add a new user to session state"""
    user["id"] = len(st.session_state.users) + 1
    user["registered_on"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Geocode user address
    if user.get("property_address"):
        coords = geocode_address(user["property_address"])
        if coords:
            user["latitude"], user["longitude"] = coords
            st.toast(f"Auto-located your address: {get_address_from_coords(coords[0], coords[1])}")
        else:
            # Use Cantilan center as fallback
            user["latitude"], user["longitude"] = CANTILAN_CENTER
            st.warning("Could not locate your address. Using Cantilan center as default.")
    else:
        # Use Cantilan center if no address provided
        user["latitude"], user["longitude"] = CANTILAN_CENTER
    
    st.session_state.users.append(user)

def get_user_by_username(username: str) -> Optional[dict]:
    """Find user by username"""
    for user in st.session_state.users:
        if user.get("username") == username:
            return user
    return None

def validate_login(username: str, password: str) -> Optional[dict]:
    """Validate user login"""
    for user in st.session_state.users:
        if user.get("username") == username and user.get("password") == password:
            return user
    return None

def get_all_users_df():
    """Get all users as DataFrame"""
    if not st.session_state.users:
        return pd.DataFrame()
    return pd.DataFrame(st.session_state.users)

def delete_user_by_id(user_id: int):
    """Delete user by ID"""
    st.session_state.users = [user for user in st.session_state.users if user.get("id") != user_id]
    # Also remove their SOS logs
    st.session_state.sos_logs = [log for log in st.session_state.sos_logs if log.get("user_id") != user_id]

def log_sos(user_id: int, user_name: str, lat: float, lon: float, note: str = "", category: Optional[str] = None):
    """Log a new SOS alert"""
    sos_id = len(st.session_state.sos_logs) + 1
    sos_record = {
        "id": sos_id,
        "user_id": user_id,
        "user_name": user_name,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "lat": lat,
        "lon": lon,
        "note": note,
        "handled": False,
        "category": category,
        "address": get_address_from_coords(lat, lon)
    }
    st.session_state.sos_logs.append(sos_record)

def get_active_sos():
    """Get all SOS logs as DataFrame"""
    if not st.session_state.sos_logs:
        return pd.DataFrame()
    
    # Ensure 'handled' column exists in all records
    for sos in st.session_state.sos_logs:
        if 'handled' not in sos:
            sos['handled'] = False
    
    return pd.DataFrame(st.session_state.sos_logs)

def mark_sos_handled(sos_id: int):
    """Mark an SOS as handled"""
    for sos in st.session_state.sos_logs:
        if sos.get("id") == sos_id:
            sos["handled"] = True
            break

def add_report(reporter_id: int, reporter_name: str, category: str, description: str, lat: float, lon: float):
    """Add a new official report"""
    report_id = len(st.session_state.reports) + 1
    report = {
        "id": report_id,
        "reporter_id": reporter_id,
        "reporter_name": reporter_name,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "category": category,
        "description": description,
        "lat": lat,
        "lon": lon,
        "address": get_address_from_coords(lat, lon)
    }
    st.session_state.reports.append(report)

def get_reports_df():
    """Get all reports as DataFrame"""
    if not st.session_state.reports:
        return pd.DataFrame()
    return pd.DataFrame(st.session_state.reports)

def get_hotline_coordinates():
    """Get coordinates for all hotlines with caching"""
    if not st.session_state.hotline_coordinates:
        for hotline in HOTLINES:
            address_key = hotline["Address"]
            if address_key not in st.session_state.hotline_coordinates:
                coords = geocode_address(hotline["Address"])
                if coords:
                    st.session_state.hotline_coordinates[address_key] = coords
                else:
                    st.session_state.hotline_coordinates[address_key] = CANTILAN_CENTER
    return st.session_state.hotline_coordinates

# ---------------- Initialize Session State ----------------
initialize_session_state()

def safe_rerun():
    """Safely rerun the app"""
    try:
        st.rerun()
    except:
        try:
            st.experimental_rerun()
        except:
            pass

# ---------------- UI: sidebar navigation ----------------
with st.sidebar:
    st.title("Cantilan ERS")
    if st.session_state.current_user:
        st.markdown(f"**Logged in as:** {st.session_state.current_user.get('name') or st.session_state.current_user.get('username')}  ")
        st.markdown(f"**Role:** {st.session_state.current_user.get('role').capitalize()}")
        if st.button("Logout"):
            st.session_state.current_user = None
            st.success("Logged out.")
            safe_rerun()
    else:
        if st.button("Login"):
            st.session_state.page = "login"
        if st.button("Sign up"):
            st.session_state.page = "signup_role"
    st.markdown("---")
    st.markdown("### Quick links")
    st.button("Home", key="home_btn", on_click=lambda: st.session_state.update({"page":"home"}))
    st.button("About", key="about_btn", on_click=lambda: st.session_state.update({"page":"about"}))
    
    # Show registered users count in sidebar for quick reference
    if st.session_state.users:
        st.markdown("---")
        st.markdown(f"**Total Registered Users:** {len(st.session_state.users)}")

# ---------------- Pages ----------------
def page_home():
    st.title("🚨 Cantilan Emergency Response System")
    st.markdown("Use the sidebar to login or sign up. If you're already signed in, you'll be redirected to your dashboard.")
    
    # Show quick stats
    if st.session_state.users:
        col1, col2, col3, col4 = st.columns(4)
        df_users = get_all_users_df()
        role_counts = df_users['role'].value_counts()
        
        with col1:
            st.metric("Total Users", len(st.session_state.users))
        with col2:
            st.metric("Citizens", role_counts.get('user', 0))
        with col3:
            st.metric("Responders", role_counts.get('rescuer', 0))
        with col4:
            # Safe count of active alerts
            df_sos = get_active_sos()
            if not df_sos.empty and 'handled' in df_sos.columns:
                active_alerts = len(df_sos[df_sos['handled'] == False])
            else:
                active_alerts = 0
            st.metric("Active Alerts", active_alerts)
    
    st.markdown("### 📍 Cantilan Map (Reference)")
    
    # Get hotline coordinates
    hotline_coords = get_hotline_coordinates()
    
    # Create map data for hotlines
    map_data = []
    for i, hotline in enumerate(HOTLINES):
        address_key = hotline["Address"]
        if address_key in hotline_coords:
            lat, lon = hotline_coords[address_key]
        else:
            # Add slight variations to coordinates to show multiple locations
            lat = CANTILAN_CENTER[0] + (i * 0.001)
            lon = CANTILAN_CENTER[1] + (i * 0.001)
        
        map_data.append({
            "name": hotline["Name"],
            "contact": hotline["Contact"],
            "address": hotline["Address"],
            "lat": lat,
            "lon": lon,
            "type": "hotline"
        })
    
    # Add Cantilan center point
    map_data.append({
        "name": "Cantilan Center",
        "contact": "Reference Point",
        "address": "Cantilan, Surigao del Sur",
        "lat": CANTILAN_CENTER[0],
        "lon": CANTILAN_CENTER[1],
        "type": "center"
    })
    
    df_locs = pd.DataFrame(map_data)
    
    # Configure pydeck map
    view_state = pdk.ViewState(
        latitude=CANTILAN_CENTER[0],
        longitude=CANTILAN_CENTER[1],
        zoom=13,
        pitch=0
    )
    
    # Color points based on type
    df_locs['color'] = df_locs['type'].apply(
        lambda x: [255, 69, 0, 200] if x == "hotline" else [0, 100, 255, 150]
    )
    df_locs['radius'] = df_locs['type'].apply(
        lambda x: 150 if x == "hotline" else 100
    )
    
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_locs,
        get_position='[lon, lat]',
        get_radius='radius',
        get_fill_color='color',
        pickable=True,
        auto_highlight=True
    )
    
    tooltip = {
        "html": """
        <b>{name}</b><br>
        Contact: {contact}<br>
        Address: {address}
        """,
        "style": {"backgroundColor": "steelblue", "color": "white"}
    }
    
    deck = pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=view_state,
        layers=[layer],
        tooltip=tooltip
    )
    
    st.pydeck_chart(deck)
    
    
    st.markdown("### 📞 Emergency Hotlines")
    st.table(pd.DataFrame(HOTLINES))

def page_about():
    st.header("About")
    st.markdown(
        """
        This app provides a simple multi-role emergency response system for Cantilan:
        - Sign up as User, Rescuer, Government Officer, or Admin
        - Users can press SOS (with coordinates) — logged and visible to Rescuers & Government
        - Admin can view and delete user records
        - Uses geopy for address geocoding and location services
        Data is stored in session state (resets when app restarts).
        """
    )
    
    # Show all registered users in About page for transparency
    if st.session_state.users:
        st.markdown("### 👥 Currently Registered Users")
        df_users = get_all_users_df()
        
        # Create a simplified display table
        display_cols = ['id', 'username', 'name', 'role', 'registered_on']
        available_cols = [col for col in display_cols if col in df_users.columns]
        
        if available_cols:
            st.dataframe(df_users[available_cols], use_container_width=True)
        else:
            st.info("No user data available for display.")

def page_signup_role():
    st.header("🎯 Choose Your Role")
    st.markdown("Select the role that best fits your responsibilities:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👤 General Public")
        st.markdown("**Citizen / Resident**")
        st.markdown("- Send emergency alerts")
        st.markdown("- View local resources")
        st.markdown("- Access emergency contacts")
        if st.button("Sign up as User", key="user_btn", use_container_width=True):
            st.session_state.page = "signup_user"
            safe_rerun()
        
        st.markdown("### 🚑 Emergency Responder")
        st.markdown("**Police, Firefighter, Medic**")
        st.markdown("- Receive SOS alerts")
        st.markdown("- Coordinate responses")
        st.markdown("- Mark incidents as resolved")
        if st.button("Sign up as Rescuer", key="rescuer_btn", use_container_width=True):
            st.session_state.page = "signup_rescuer"
            safe_rerun()
    
    with col2:
        st.markdown("### 🏛️ Government Official")
        st.markdown("**LGU, DRRMO, Health Officer**")
        st.markdown("- Create official reports")
        st.markdown("- Monitor emergency patterns")
        st.markdown("- Coordinate with responders")
        if st.button("Sign up as Government", key="gov_btn", use_container_width=True):
            st.session_state.page = "signup_government"
            safe_rerun()
        
        st.markdown("### 🛠️ System Administrator")
        st.markdown("**IT Admin, System Manager**")
        st.markdown("- Manage user accounts")
        st.markdown("- Monitor system activity")
        st.markdown("- Generate reports")
        if st.button("Sign up as Admin", key="admin_btn", use_container_width=True):
            st.session_state.page = "signup_admin"
            safe_rerun()

def page_signup_user():
    st.header("👤 Citizen Registration")
    st.markdown("Register as a resident to access emergency services")
    
    # Address geocoding helper - MOVED OUTSIDE THE FORM
    st.markdown("#### 📍 Address Verification")
    col1, col2 = st.columns([3, 1])
    with col1:
        property_address = st.text_area("Property Address (Barangay, Street) *", 
                                      placeholder="e.g., Poblacion, Cantilan, Surigao del Sur")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📍 Geocode Address", key="geocode_user"):
            if property_address:
                with st.spinner("Locating your address..."):
                    coords = geocode_address(property_address)
                    if coords:
                        st.success(f"Address found! Coordinates: {coords[0]:.6f}, {coords[1]:.6f}")
                        st.info(f"Location: {get_address_from_coords(coords[0], coords[1])}")
                    else:
                        st.error("Address not found. Please check your address or try a more specific location.")
            else:
                st.warning("Please enter an address first.")
    
    # Registration form
    with st.form("signup_user", clear_on_submit=True):
        st.subheader("Personal Information")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *")
            password = st.text_input("Password *", type="password")
            name = st.text_input("Full Name *")
            age = st.number_input("Age *", 1, 120, 30)
            gender = st.selectbox("Gender *", ["Male", "Female", "Other"])
        
        with col2:
            mobile = st.text_input("Mobile Number *")
            work = st.text_input("Occupation")
            family_members = st.number_input("Family Members", 1, 50, 1)
        
        st.subheader("Residence Information")
        col3, col4 = st.columns(2)
        with col3:
            # property_address is already defined above
            specific_address = st.text_input("Specific Address / Landmark")
        with col4:
            property_size = st.text_input("Property Size (e.g., 150 sqm)")
            year_residency = st.number_input("Year of Residency", 1900, datetime.datetime.now().year, 2020)
        
        st.markdown("**Required fields*")
        submitted = st.form_submit_button("Create Citizen Account")
        
        if submitted:
            if not all([username, password, name, mobile, property_address]):
                st.error("Please fill all required fields (*)")
            elif get_user_by_username(username):
                st.error("Username already exists. Pick another.")
            else:
                user = {
                    "role": "user",
                    "username": username,
                    "password": password,
                    "name": name,
                    "age": age,
                    "gender": gender,
                    "mobile": mobile,
                    "position": None,
                    "work": work,
                    "family_members": family_members,
                    "property_address": property_address,
                    "specific_address": specific_address,
                    "property_size": property_size,
                    "year_residency": year_residency,
                    "specialization": None,
                    "equipment": None,
                    "department": None,
                    "clearance_level": None,
                    "admin_privileges": None,
                }
                add_user(user)
                st.success("Citizen account created successfully! You can now log in.")
                time.sleep(2)
                st.session_state.page = "login"
                safe_rerun()

def page_signup_rescuer():
    st.header("🚑 Emergency Responder Registration")
    st.markdown("Register as a first responder or emergency personnel")
    
    # Address geocoding helper - MOVED OUTSIDE THE FORM
    st.markdown("#### 📍 Base Location Verification")
    col1, col2 = st.columns([3, 1])
    with col1:
        base_address = st.text_input("Base Address *", placeholder="e.g., Municipal Hall, Cantilan")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📍 Geocode Base Address", key="geocode_rescuer"):
            if base_address:
                with st.spinner("Locating base address..."):
                    coords = geocode_address(base_address)
                    if coords:
                        st.success(f"Base located! Coordinates: {coords[0]:.6f}, {coords[1]:.6f}")
                        st.info(f"Location: {get_address_from_coords(coords[0], coords[1])}")
                    else:
                        st.error("Address not found. Please check your address or try a more specific location.")
            else:
                st.warning("Please enter a base address first.")
    
    # Registration form
    with st.form("signup_rescuer", clear_on_submit=True):
        st.subheader("Personal Information")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *")
            password = st.text_input("Password *", type="password")
            name = st.text_input("Full Name *")
            mobile = st.text_input("Mobile Number *")
        
        with col2:
            position = st.selectbox("Position/Rank *", 
                ["Police Officer", "Firefighter", "Paramedic", "EMT", "Doctor", "Nurse", 
                 "Search & Rescue", "Volunteer", "Other"])
            specialization = st.text_input("Specialization (e.g., Water Rescue, Medical)")
        
        st.subheader("Organization Details")
        col3, col4 = st.columns(2)
        with col3:
            work = st.text_input("Organization/Unit *", placeholder="e.g., BFP Cantilan, PNP Station")
            department = st.text_input("Department/Section")
        with col4:
            equipment = st.text_area("Equipment/Skills", placeholder="e.g., First Aid, Fire Truck, Boat")
            clearance_level = st.selectbox("Clearance Level", 
                ["Basic", "Intermediate", "Advanced", "Command", "Not Specified"])
        
        st.markdown("**Required fields*")
        submitted = st.form_submit_button("Create Responder Account")
        
        if submitted:
            if not all([username, password, name, mobile, position, work, base_address]):
                st.error("Please fill all required fields (*)")
            elif get_user_by_username(username):
                st.error("Username already exists. Pick another.")
            else:
                user = {
                    "role": "rescuer",
                    "username": username,
                    "password": password,
                    "name": name,
                    "age": None,
                    "gender": None,
                    "mobile": mobile,
                    "position": position,
                    "work": work,
                    "family_members": None,
                    "property_address": base_address,
                    "specific_address": None,
                    "property_size": None,
                    "year_residency": None,
                    "specialization": specialization,
                    "equipment": equipment,
                    "department": department,
                    "clearance_level": clearance_level,
                    "admin_privileges": None,
                }
                add_user(user)
                st.success("Responder account created successfully! You can now log in.")
                time.sleep(2)
                st.session_state.page = "login"
                safe_rerun()

def page_signup_government():
    st.header("🏛️ Government Official Registration")
    st.markdown("Register as a government officer or department representative")
    
    # Address geocoding helper - MOVED OUTSIDE THE FORM
    st.markdown("#### 📍 Office Location Verification")
    col1, col2 = st.columns([3, 1])
    with col1:
        office_address = st.text_input("Office Address *", placeholder="e.g., Municipal Hall, Cantilan")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📍 Geocode Office Address", key="geocode_gov"):
            if office_address:
                with st.spinner("Locating office address..."):
                    coords = geocode_address(office_address)
                    if coords:
                        st.success(f"Office located! Coordinates: {coords[0]:.6f}, {coords[1]:.6f}")
                        st.info(f"Location: {get_address_from_coords(coords[0], coords[1])}")
                    else:
                        st.error("Address not found. Please check your address or try a more specific location.")
            else:
                st.warning("Please enter an office address first.")
    
    # Registration form
    with st.form("signup_government", clear_on_submit=True):
        st.subheader("Official Information")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *")
            password = st.text_input("Password *", type="password")
            name = st.text_input("Full Name *")
            mobile = st.text_input("Mobile Number *")
        
        with col2:
            position = st.text_input("Official Position *", placeholder="e.g., DRRMO Officer, Mayor, Councilor")
            department = st.text_input("Department/Office *", placeholder="e.g., Mayor's Office, DRRMO, Health Office")
        
        st.subheader("Government Details")
        col3, col4 = st.columns(2)
        with col3:
            work = st.text_input("Specific Unit/Section", placeholder="e.g., Operations, Planning, Administration")
            clearance_level = st.selectbox("Security Clearance", 
                ["Public", "Internal", "Confidential", "Restricted", "Secret"])
        with col4:
            specialization = st.text_area("Responsibilities/Expertise", 
                placeholder="e.g., Disaster Response, Health Services, Infrastructure")
        
        st.markdown("**Required fields*")
        submitted = st.form_submit_button("Create Government Account")
        
        if submitted:
            if not all([username, password, name, mobile, position, department, office_address]):
                st.error("Please fill all required fields (*)")
            elif get_user_by_username(username):
                st.error("Username already exists. Pick another.")
            else:
                user = {
                    "role": "government",
                    "username": username,
                    "password": password,
                    "name": name,
                    "age": None,
                    "gender": None,
                    "mobile": mobile,
                    "position": position,
                    "work": work,
                    "family_members": None,
                    "property_address": office_address,
                    "specific_address": None,
                    "property_size": None,
                    "year_residency": None,
                    "specialization": specialization,
                    "equipment": None,
                    "department": department,
                    "clearance_level": clearance_level,
                    "admin_privileges": None,
                }
                add_user(user)
                st.success("Government account created successfully! You can now log in.")
                time.sleep(2)
                st.session_state.page = "login"
                safe_rerun()

def page_signup_admin():
    st.header("🛠️ System Administrator Registration")
    st.markdown("Register as a system administrator (requires verification)")
    
    # Address geocoding helper - MOVED OUTSIDE THE FORM
    st.markdown("#### 📍 Office Location (Optional)")
    col1, col2 = st.columns([3, 1])
    with col1:
        office_address = st.text_input("Office Address", placeholder="e.g., Municipal Hall, Cantilan")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📍 Geocode Office Address", key="geocode_admin"):
            if office_address:
                with st.spinner("Locating office address..."):
                    coords = geocode_address(office_address)
                    if coords:
                        st.success(f"Office located! Coordinates: {coords[0]:.6f}, {coords[1]:.6f}")
                        st.info(f"Location: {get_address_from_coords(coords[0], coords[1])}")
                    else:
                        st.error("Address not found. Please check your address or try a more specific location.")
            else:
                st.warning("Please enter an office address first.")
    
    # Registration form
    with st.form("signup_admin", clear_on_submit=True):
        st.subheader("Administrator Information")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *")
            password = st.text_input("Password *", type="password")
            name = st.text_input("Full Name *")
        with col2:
            mobile = st.text_input("Mobile Number *")
            admin_privileges = st.selectbox("Admin Level *", 
                ["Full System Admin", "User Management", "Data Management", "Monitor Only"])
        
        st.subheader("Administrative Details")
        col3, col4 = st.columns(2)
        with col3:
            position = st.text_input("IT Position *", placeholder="e.g., System Administrator, IT Manager")
            department = st.text_input("IT Department *", placeholder="e.g., MIS, ICT Office")
        with col4:
            work = st.text_input("Specific Role", placeholder="e.g., Database Admin, Network Admin")
            clearance_level = st.selectbox("System Access Level", 
                ["Full Access", "User Management", "Data Access", "Read Only"])
        
        st.subheader("Verification")
        verification_code = st.text_input("Verification Code *", 
            placeholder="Contact system owner for code")
        
        st.markdown("**Required fields*")
        
        # Add password confirmation
        confirm_password = st.text_input("Confirm Password *", type="password")
        
        submitted = st.form_submit_button("Create Administrator Account")
        
        if submitted:
            if not all([username, password, name, mobile, position, department, verification_code]):
                st.error("Please fill all required fields (*)")
            elif password != confirm_password:
                st.error("Passwords do not match!")
            elif get_user_by_username(username):
                st.error("Username already exists. Pick another.")
            elif verification_code != "admin":  # Updated verification code
                st.error("Invalid verification code. Contact system administrator.")
            else:
                user = {
                    "role": "admin",
                    "username": username,
                    "password": password,
                    "name": name,
                    "age": None,
                    "gender": None,
                    "mobile": mobile,
                    "position": position,
                    "work": work,
                    "family_members": None,
                    "property_address": office_address,
                    "specific_address": None,
                    "property_size": None,
                    "year_residency": None,
                    "specialization": None,
                    "equipment": None,
                    "department": department,
                    "clearance_level": clearance_level,
                    "admin_privileges": admin_privileges,
                }
                add_user(user)
                st.success("Administrator account created successfully! You can now log in.")
                time.sleep(2)
                st.session_state.page = "login"
                safe_rerun()

def page_login():
    st.header("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = validate_login(username, password)
            if not user:
                st.error("Invalid username or password.")
            else:
                st.session_state.current_user = user
                st.success(f"Welcome, {user.get('name') or user.get('username')}!")
                safe_rerun()

# ---------------- Enhanced Dashboards ----------------
def user_dashboard(user):
    st.title(f"👤 Citizen Dashboard")
    st.markdown(f"### Welcome, {user.get('name') or user.get('username')}!")
    
    # Personal Info Card
    with st.container():
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📋 Your Information")
            info = {
                "Name": user.get("name"),
                "Mobile": user.get("mobile"),
                "Address": user.get("property_address"),
                "Family Members": user.get("family_members"),
                "Registered": user.get("registered_on"),
            }
            for key, value in info.items():
                if value:
                    st.write(f"**{key}:** {value}")
        with col2:
            st.markdown("#### 🏠 Residence Details")
            residence_info = {
                "Specific Location": user.get("specific_address"),
                "Property Size": user.get("property_size"),
                "Years in Cantilan": user.get("year_residency"),
            }
            for key, value in residence_info.items():
                if value:
                    st.write(f"**{key}:** {value}")
            
            # Show address from coordinates
            if user.get("latitude") and user.get("longitude"):
                address = get_address_from_coords(user["latitude"], user["longitude"])
                st.write(f"**Geocoded Address:** {address}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Emergency SOS Section
    st.markdown("### 🚨 Emergency SOS")
    with st.container():
        st.markdown('<div class="role-specific">', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 3])
        with col1:
            note = st.text_area("Emergency Description", placeholder="What's happening? Provide details...")
            category = st.selectbox("Emergency Type", [""] + EMERGENCY_CATEGORIES)
            
            # Location options
            st.markdown("#### 📍 Location Options")
            use_registered = st.checkbox("Use my registered address", value=True)
            if not use_registered:
                current_address = st.text_input("Enter your current address:", 
                                             placeholder="Your current location in Cantilan...")
                if current_address:
                    if st.button("📍 Locate This Address"):
                        with st.spinner("Locating address..."):
                            coords = geocode_address(current_address)
                            if coords:
                                st.session_state.temp_emergency_coords = coords
                                st.success(f"Location set: {get_address_from_coords(coords[0], coords[1])}")
                            else:
                                st.error("Address not found. Please try a more specific location.")
            
            if st.button("🚨 SEND EMERGENCY ALERT", use_container_width=True):
                if use_registered:
                    lat = user.get("latitude")
                    lon = user.get("longitude")
                else:
                    temp_coords = getattr(st.session_state, 'temp_emergency_coords', None)
                    if temp_coords:
                        lat, lon = temp_coords
                    else:
                        st.error("Please locate your current address first!")
                        return
                
                log_sos(user_id=user.get("id"), user_name=user.get("name") or user.get("username"), 
                       lat=lat, lon=lon, note=note, category=category or None)
                st.error("EMERGENCY ALERT SENT! Help is on the way.", icon="⚠️")
                st.toast("Alert dispatched to all responders. Stay calm and safe.", icon="✅")
                safe_rerun()
                
        with col2:
            st.markdown("#### Quick Actions")
            st.info("Update your location if needed:")
            if st.button("📍 Re-geocode My Address", use_container_width=True):
                if user.get("property_address"):
                    coords = geocode_address(user["property_address"])
                    if coords:
                        user["latitude"], user["longitude"] = coords
                        st.success("Location updated from your address!")
                        safe_rerun()
                    else:
                        st.error("Could not locate your address. Please update your address details.")
            
            st.markdown("---")
            st.markdown("#### 📞 Emergency Contacts")
            for hotline in HOTLINES[:2]:
                st.write(f"**{hotline['Name']}:** {hotline['Contact']}")
                
            # Calculate distance to nearest responder
            if user.get("latitude") and user.get("longitude"):
                user_coords = (user["latitude"], user["longitude"])
                hotline_coords = get_hotline_coordinates()
                min_distance = float('inf')
                nearest_hotline = None
                
                for hotline in HOTLINES:
                    if hotline["Address"] in hotline_coords:
                        distance = get_distance(user_coords, hotline_coords[hotline["Address"]])
                        if distance and distance < min_distance:
                            min_distance = distance
                            nearest_hotline = hotline
                
                if nearest_hotline and min_distance != float('inf'):
                    st.info(f"Nearest responder: {nearest_hotline['Name']} ({min_distance:.1f} km away)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Map and Recent Alerts
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📍 Emergency Map")
        df_sos = get_active_sos()
        
        # Create map data
        map_data = []
        
        # Add user's location
        map_data.append({
            "latitude": user.get("latitude"),
            "longitude": user.get("longitude"),
            "name": "Your Location",
            "type": "user",
            "color": [0, 100, 255, 200]
        })
        
        # Add SOS alerts
        if not df_sos.empty:
            for _, alert in df_sos.iterrows():
                map_data.append({
                    "latitude": alert["lat"],
                    "longitude": alert["lon"],
                    "name": f"SOS: {alert['user_name']}",
                    "type": "sos",
                    "category": alert.get("category", "Emergency"),
                    "handled": alert.get("handled", False),
                    "color": [0, 255, 0, 160] if alert.get("handled") else [255, 0, 0, 200]
                })
        
        # Add hotlines
        hotline_coords = get_hotline_coordinates()
        for hotline in HOTLINES:
            if hotline["Address"] in hotline_coords:
                lat, lon = hotline_coords[hotline["Address"]]
                map_data.append({
                    "latitude": lat,
                    "longitude": lon,
                    "name": hotline["Name"],
                    "type": "hotline",
                    "color": [255, 165, 0, 180]
                })
        
        map_df = pd.DataFrame(map_data)
        
        # Configure map
        view_state = pdk.ViewState(
            latitude=user.get("latitude"),
            longitude=user.get("longitude"),
            zoom=13,
            pitch=0
        )
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[longitude, latitude]',
            get_radius=150,
            get_fill_color='color',
            pickable=True,
            auto_highlight=True
        )
        
        tooltip = {
            "html": "<b>{name}</b><br>Type: {type}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        
        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=view_state,
            layers=[layer],
            tooltip=tooltip
        )
        
        st.pydeck_chart(deck)
    
    with col2:
        st.markdown("### 📢 Recent Community Alerts")
        df_sos = get_active_sos()
        if df_sos.empty:
            st.info("No active emergency alerts in the community.")
        else:
            for _, alert in df_sos.head(5).iterrows():
                with st.expander(f"🚨 {alert['category'] or 'Emergency'} - {alert['timestamp']}"):
                    st.write(f"**From:** {alert['user_name']}")
                    st.write(f"**Note:** {alert['note']}")
                    if 'address' in alert:
                        st.write(f"**Location:** {alert['address']}")
                    # Safe status check
                    if 'handled' in alert:
                        st.write(f"**Status:** {'✅ Handled' if alert['handled'] else '🟡 Active'}")

def rescuer_dashboard(user):
    st.title(f"🚑 Responder Dashboard")
    st.markdown(f"### Welcome, {user.get('position') or user.get('name')}!")
    
    # Responder Info Card
    with st.container():
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 👤 Responder Info")
            st.write(f"**Name:** {user.get('name')}")
            st.write(f"**Position:** {user.get('position')}")
            st.write(f"**Mobile:** {user.get('mobile')}")
        with col2:
            st.markdown("#### 🏢 Organization")
            st.write(f"**Unit:** {user.get('work')}")
            st.write(f"**Department:** {user.get('department')}")
            st.write(f"**Clearance:** {user.get('clearance_level')}")
        with col3:
            st.markdown("#### 🛠️ Capabilities")
            st.write(f"**Specialization:** {user.get('specialization')}")
            if user.get('equipment'):
                st.write(f"**Equipment:** {user.get('equipment')}")
            
            # Show base location info
            if user.get("latitude") and user.get("longitude"):
                address = get_address_from_coords(user["latitude"], user["longitude"])
                st.write(f"**Base:** {address}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Active Emergencies with distance calculations - FIXED VERSION
    st.markdown("### 🚨 Active Emergencies")
    df_sos = get_active_sos()
    
    if df_sos.empty:
        st.info("No active emergencies. Stay alert!")
    else:
        # Calculate distances for each alert
        responder_coords = (user.get("latitude"), user.get("longitude"))
        
        alerts_with_distance = []
        for _, alert in df_sos.iterrows():
            alert_coords = (alert["lat"], alert["lon"])
            distance = get_distance(responder_coords, alert_coords)
            alerts_with_distance.append((alert, distance))
        
        # Sort by distance
        alerts_with_distance.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
        
        # Safe filtering for unresolved alerts
        unresolved_alerts = [alert_tuple for alert_tuple in alerts_with_distance 
                           if not alert_tuple[0].get('handled', False)]
        resolved_alerts = [alert_tuple for alert_tuple in alerts_with_distance 
                          if alert_tuple[0].get('handled', False)]
        
        if unresolved_alerts:
            st.markdown(f"#### 🟡 Active ({len(unresolved_alerts)})")
            for alert_tuple in unresolved_alerts[:5]:  # Show closest 5
                # FIX: Safely unpack the tuple
                if len(alert_tuple) == 2:
                    alert, distance = alert_tuple
                else:
                    # Handle case where tuple structure is unexpected
                    alert = alert_tuple[0] if alert_tuple else {}
                    distance = None
                    
                with st.container():
                    st.markdown('<div class="role-specific">', unsafe_allow_html=True)
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**🚨 {alert.get('category', 'Emergency')}**")
                        st.write(f"**From:** {alert.get('user_name', 'Unknown')} | **Time:** {alert.get('timestamp', 'Unknown')}")
                        if 'address' in alert:
                            st.write(f"**Location:** {alert['address']}")
                        if distance is not None:
                            st.write(f"**Distance:** {distance:.1f} km")
                        if alert.get('note'):
                            st.write(f"**Details:** {alert['note']}")
                    with col2:
                        if st.button(f"Mark Handled", key=f"handle_{alert.get('id', 'unknown')}"):
                            mark_sos_handled(int(alert.get('id', 0)))
                            st.success(f"Emergency {alert.get('id', 'unknown')} marked as handled.")
                            safe_rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
        
        if resolved_alerts:
            st.markdown(f"#### ✅ Resolved ({len(resolved_alerts)})")
            for alert_tuple in resolved_alerts[:3]:
                # FIX: Safely unpack the tuple
                if len(alert_tuple) == 2:
                    alert, distance = alert_tuple
                else:
                    alert = alert_tuple[0] if alert_tuple else {}
                    distance = None
                    
                with st.expander(f"✅ {alert.get('category', 'Emergency')} - {alert.get('timestamp', 'Unknown')} ({distance:.1f if distance else '?'} km)"):
                    st.write(f"**From:** {alert.get('user_name', 'Unknown')}")
                    st.write(f"**Note:** {alert.get('note', 'No details')}")
    
    # Enhanced Emergency Map
    st.markdown("### 📍 Response Map")
    df_sos = get_active_sos()
    
    if not df_sos.empty:
        # Create map data
        map_data = []
        
        # Add responder's location
        map_data.append({
            "latitude": user.get("latitude"),
            "longitude": user.get("longitude"),
            "name": "Your Location",
            "type": "responder",
            "color": [0, 100, 255, 200]
        })
        
        # Add SOS alerts
        for _, alert in df_sos.iterrows():
            map_data.append({
                "latitude": alert["lat"],
                "longitude": alert["lon"],
                "name": f"SOS: {alert['user_name']}",
                "type": "sos",
                "category": alert.get("category", "Emergency"),
                "handled": alert.get("handled", False),
                "color": [0, 255, 0, 160] if alert.get("handled") else [255, 0, 0, 200]
            })
        
        map_df = pd.DataFrame(map_data)
        
        view_state = pdk.ViewState(
            latitude=user.get("latitude"),
            longitude=user.get("longitude"),
            zoom=13,
            pitch=0
        )
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[longitude, latitude]',
            get_radius=200,
            get_fill_color='color',
            pickable=True,
            auto_highlight=True
        )
        
        tooltip = {
            "html": "<b>{name}</b><br>Type: {type}<br>Category: {category}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        
        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=view_state,
            layers=[layer],
            tooltip=tooltip
        )
        
        st.pydeck_chart(deck)
    else:
        st.info("No active emergencies to display on map.")

def government_dashboard(user):
    st.title(f"🏛️ Government Dashboard")
    st.markdown(f"### Welcome, {user.get('position') or user.get('name')}!")
    
    # Government Info Card with geolocation
    with st.container():
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 👤 Official Information")
            st.write(f"**Name:** {user.get('name')}")
            st.write(f"**Position:** {user.get('position')}")
            st.write(f"**Department:** {user.get('department')}")
        with col2:
            st.markdown("#### 🏢 Office Details")
            st.write(f"**Unit:** {user.get('work')}")
            st.write(f"**Clearance:** {user.get('clearance_level')}")
            if user.get('specialization'):
                st.write(f"**Expertise:** {user.get('specialization')}")
            if user.get("latitude") and user.get("longitude"):
                address = get_address_from_coords(user["latitude"], user["longitude"])
                st.write(f"**Office:** {address}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Report Creation with geocoding
    st.markdown("### 📋 Create Official Report")
    with st.container():
        st.markdown('<div class="role-specific">', unsafe_allow_html=True)
        
        # Address geocoding section - MOVED OUTSIDE THE FORM
        st.markdown("#### 📍 Incident Location")
        col1, col2 = st.columns([3, 1])
        with col1:
            incident_address = st.text_input("Incident Address *", 
                                           placeholder="Specific location of the incident in Cantilan...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📍 Geocode Incident Address", key="geocode_incident"):
                if incident_address:
                    with st.spinner("Locating incident address..."):
                        coords = geocode_address(incident_address)
                        if coords:
                            st.session_state.incident_lat = coords[0]
                            st.session_state.incident_lon = coords[1]
                            st.success(f"Incident located: {get_address_from_coords(coords[0], coords[1])}")
                        else:
                            st.error("Address not found. Please try a more specific location.")
                else:
                    st.warning("Please enter an incident address first.")
        
        # Report form
        with st.form("gov_report_form"):
            category = st.selectbox("Incident Category *", EMERGENCY_CATEGORIES)
            description = st.text_area("Official Description *", 
                                     placeholder="Detailed description of the incident...")
            
            submitted = st.form_submit_button("📄 Submit Official Report")
            if submitted:
                if not all([description, incident_address]):
                    st.error("Please provide description and incident address.")
                else:
                    # Use geocoded coordinates if available
                    final_lat = getattr(st.session_state, 'incident_lat', None)
                    final_lon = getattr(st.session_state, 'incident_lon', None)
                    
                    if final_lat is None or final_lon is None:
                        # Geocode the address if not already done
                        coords = geocode_address(incident_address)
                        if coords:
                            final_lat, final_lon = coords
                        else:
                            st.error("Could not locate the incident address. Please try a more specific location.")
                            return
                    
                    add_report(reporter_id=user.get("id"), 
                             reporter_name=user.get("name") or user.get("username"),
                             category=category, description=description, lat=final_lat, lon=final_lon)
                    st.success("Official report submitted and logged.")
                    safe_rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Official Reports")
        df_reports = get_reports_df()
        if df_reports.empty:
            st.info("No official reports yet.")
        else:
            for _, report in df_reports.head(5).iterrows():
                with st.expander(f"📄 {report['category']} - {report['timestamp']}"):
                    st.write(f"**By:** {report['reporter_name']}")
                    st.write(f"**Description:** {report['description']}")
                    if 'address' in report:
                        st.write(f"**Location:** {report['address']}")
    
    with col2:
        st.markdown("### 🚨 Recent SOS Alerts")
        df_sos = get_active_sos()
        if df_sos.empty:
            st.info("No recent SOS alerts.")
        else:
            if 'category' in df_sos.columns:
                alert_summary = df_sos['category'].value_counts()
                st.dataframe(alert_summary, use_container_width=True)
            else:
                st.info("No category data available.")
            
            st.markdown("#### Recent Activity")
            for _, alert in df_sos.head(3).iterrows():
                # Safe status check
                if 'handled' in alert:
                    status = "✅" if alert['handled'] else "🟡"
                else:
                    status = "🟡"
                location_info = alert.get('address', 'Location not available')
                st.write(f"{status} **{alert.get('category', 'Emergency')}** - {alert['timestamp'][11:16]}")
                st.caption(f"Location: {location_info}")

def admin_dashboard(user):
    st.title("🛠️ System Administration")
    st.markdown(f"### Welcome, System Administrator {user.get('name')}!")
    
    # Admin Info Card
    with st.container():
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 👤 Admin Profile")
            st.write(f"**Name:** {user.get('name')}")
            st.write(f"**Position:** {user.get('position')}")
            st.write(f"**Admin Level:** {user.get('admin_privileges')}")
        with col2:
            st.markdown("#### 🏢 Department")
            st.write(f"**Department:** {user.get('department')}")
            st.write(f"**Role:** {user.get('work')}")
            st.write(f"**Access Level:** {user.get('clearance_level')}")
        with col3:
            st.markdown("#### 📈 System Stats")
            df_users = get_all_users_df()
            df_sos = get_active_sos()
            st.write(f"**Total Users:** {len(df_users)}")
            
            # FIXED: Safe count of active alerts
            if not df_sos.empty and 'handled' in df_sos.columns:
                active_alerts = len(df_sos[df_sos['handled'] == False])
            else:
                active_alerts = 0
            st.write(f"**Active Alerts:** {active_alerts}")
            
            st.write(f"**Total Reports:** {len(get_reports_df())}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # User Management with location info
    st.markdown("### 👥 User Management")
    df_users = get_all_users_df()
    
    if df_users.empty:
        st.info("No registered users.")
    else:
        # User statistics
        col1, col2, col3, col4 = st.columns(4)
        role_counts = df_users['role'].value_counts()
        with col1:
            st.metric("Citizens", role_counts.get('user', 0))
        with col2:
            st.metric("Responders", role_counts.get('rescuer', 0))
        with col3:
            st.metric("Government", role_counts.get('government', 0))
        with col4:
            st.metric("Admins", role_counts.get('admin', 0))
        
        # Enhanced user table with location info
        st.markdown("#### User Accounts")
        
        # Create display dataframe with location info
        display_data = []
        for _, user_row in df_users.iterrows():
            user_info = {
                'id': user_row.get('id'),
                'username': user_row.get('username'),
                'name': user_row.get('name'),
                'role': user_row.get('role'),
                'mobile': user_row.get('mobile'),
                'position': user_row.get('position'),
                'department': user_row.get('department'),
                'registered_on': user_row.get('registered_on')
            }
            # Add location info if available
            if user_row.get('property_address'):
                user_info['address'] = user_row.get('property_address')
            
            display_data.append(user_info)
        
        display_df = pd.DataFrame(display_data)
        st.dataframe(display_df, use_container_width=True)
        
        # The rest of admin dashboard remains the same
        st.markdown("#### 🔧 Account Management")
        col1, col2 = st.columns(2)
        with col1:
            user_id_to_delete = st.number_input("Enter User ID to delete", min_value=1, step=1)
            if st.button("🗑️ Delete User", type="secondary"):
                if user_id_to_delete > 0:
                    if user_id_to_delete == user.get('id'):
                        st.error("You cannot delete your own account!")
                    else:
                        delete_user_by_id(int(user_id_to_delete))
                        st.success(f"User {user_id_to_delete} deleted successfully.")
                        safe_rerun()
        with col2:
            st.markdown("#### 📊 Data Export")
            if st.button("📥 Export Users CSV"):
                csv = df_users.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, "cantilan_users.csv", "text/csv")
    
    # System Monitoring with enhanced location info
    st.markdown("### 📊 System Monitoring")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🚨 Recent SOS Alerts")
        df_sos = get_active_sos()
        if df_sos.empty:
            st.info("No SOS alerts in system.")
        else:
            # Enhanced display with addresses
            display_data = []
            for _, alert in df_sos.iterrows():
                alert_info = {
                    'id': alert.get('id'),
                    'user_name': alert.get('user_name'),
                    'timestamp': alert.get('timestamp'),
                    'category': alert.get('category'),
                    'handled': alert.get('handled', False)
                }
                if 'address' in alert:
                    alert_info['location'] = alert['address']
                display_data.append(alert_info)
            
            display_df = pd.DataFrame(display_data)
            st.dataframe(display_df, use_container_width=True)
    
    with col2:
        st.markdown("#### 📄 Recent Reports")
        df_reports = get_reports_df()
        if df_reports.empty:
            st.info("No official reports.")
        else:
            # Enhanced display with addresses
            display_data = []
            for _, report in df_reports.iterrows():
                report_info = {
                    'id': report.get('id'),
                    'reporter_name': report.get('reporter_name'),
                    'timestamp': report.get('timestamp'),
                    'category': report.get('category')
                }
                if 'address' in report:
                    report_info['location'] = report['address']
                display_data.append(report_info)
            
            display_df = pd.DataFrame(display_data)
            st.dataframe(display_df, use_container_width=True)
    
    # Complete User Registry Table with geolocation
    st.markdown("### 📋 Complete User Registry")
    if not df_users.empty:
        st.markdown("#### All Registered Users (Detailed View)")
        
        # Show all available columns except password, include location info
        columns_to_show = [col for col in df_users.columns if col != 'password']
        
        if columns_to_show:
            st.dataframe(df_users[columns_to_show], use_container_width=True)
            
            # Summary statistics
            st.markdown("#### 📈 User Statistics")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Role Distribution**")
                role_dist = df_users['role'].value_counts()
                st.dataframe(role_dist, use_container_width=True)
            
            with col2:
                st.markdown("**Registration Timeline**")
                if 'registered_on' in df_users.columns:
                    try:
                        reg_dates = pd.to_datetime(df_users['registered_on']).dt.date
                        reg_timeline = reg_dates.value_counts().sort_index()
                        if not reg_timeline.empty:
                            st.dataframe(reg_timeline, use_container_width=True)
                        else:
                            st.info("No registration date data.")
                    except Exception as e:
                        st.info(f"Could not process registration dates: {e}")
                else:
                    st.info("Registration dates not available.")
        else:
            st.info("No user data available for display.")
    else:
        st.info("No users registered in the system.")

# ---------------- Router ----------------
def main_router():
    # Show role-based dashboard if logged in
    if st.session_state.current_user:
        role = st.session_state.current_user.get("role")
        
        if role == "user":
            user_dashboard(st.session_state.current_user)
        elif role == "rescuer":
            rescuer_dashboard(st.session_state.current_user)
        elif role == "government":
            government_dashboard(st.session_state.current_user)
        elif role == "admin":
            admin_dashboard(st.session_state.current_user)
        else:
            st.error("Unknown user role. Please contact system administrator.")
    else:
        # Show public pages if not logged in
        if st.session_state.page == "home":
            page_home()
        elif st.session_state.page == "about":
            page_about()
        elif st.session_state.page == "signup_role":
            page_signup_role()
        elif st.session_state.page == "signup_user":
            page_signup_user()
        elif st.session_state.page == "signup_rescuer":
            page_signup_rescuer()
        elif st.session_state.page == "signup_government":
            page_signup_government()
        elif st.session_state.page == "signup_admin":
            page_signup_admin()
        elif st.session_state.page == "login":
            page_login()
        else:
            page_home()

# ---------------- Run app ----------------
if __name__ == "__main__":
    main_router()