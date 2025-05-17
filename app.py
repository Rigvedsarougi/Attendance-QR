import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
import uuid
from PIL import Image
from datetime import datetime, time, timedelta
import pytz
from dateutil.relativedelta import relativedelta

# --- Helpers & Caching ---
@st.cache_data(ttl=300)
def init_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def load_person_data(conn):
    try:
        df = conn.read(worksheet="Person", ttl=5)
        df.dropna(how='all', inplace=True)
        fill_vals = {col: 0 if pd.api.types.is_numeric_dtype(df[col]) else '' for col in df.columns}
        return df.fillna(fill_vals)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_attendance_data(conn):
    try:
        df = conn.read(worksheet="Attendance", usecols=list(range(12)), ttl=5)
        return df.dropna(how='all')
    except Exception:
        return pd.DataFrame()

# Initialize
conn = init_connection()
Person = load_person_data(conn)
Attendance = load_attendance_data(conn)

# IST Time
def get_ist_time():
    tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(pytz.utc).astimezone(tz)

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def format_datetime(dt):
    return dt.strftime("%d-%m-%Y %H:%M:%S")

# Authentication
@st.cache_data
def authenticate_employee(name, key):
    row = Person.loc[Person['Employee Name']==name]
    return not row.empty and str(key)==str(row['Employee Code'].values[0])

# Attendance checks & logging
def check_existing(employee_code, date_str, column, value_op):
    if Attendance.empty:
        return False
    df = Attendance
    return not df.query(f"`Employee Code`=={employee_code} and Date=='{date_str}' and {column}{value_op}").empty

# Metrics & Stats
@st.cache_data(ttl=300)
def get_attendance_stats(employee_code):
    if Attendance.empty:
        return {'present':0,'half_day':0,'mini_half_day':0,'leave':0,'total_working_hours':0}
    month = get_ist_time().strftime('%m-%Y')
    df = Attendance.query(f"`Employee Code`=={employee_code} and Date.str.endswith('{month}')", engine='python')
    stats = { 'Present':0, 'Half Day':0, 'Mini Half Day':0, 'Leave':0 }
    total_hours = 0.0
    for _, row in df.iterrows():
        status = row['Status']
        stats[status] = stats.get(status,0) + 1
        if row['Total Working Hours']!='':
            total_hours += float(row['Total Working Hours'])
    return {
        'present': stats['Present'],
        'half_day': stats['Half Day'],
        'mini_half_day': stats['Mini Half Day'],
        'leave': stats['Leave'],
        'total_working_hours': round(total_hours,2)
    }

# Layout/CSS
st.set_page_config(page_title="Employee Portal", layout="wide")
st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden !important}
</style>
""", unsafe_allow_html=True)

# Pages
def display_login():
    cols = st.columns([1,3,1])
    with cols[1]:
        if os.path.exists('logo.png'):
            st.image('logo.png', use_container_width=True)
        st.title("Employee Portal")
        st.subheader("Login")
        name = st.selectbox("Your Name", Person['Employee Name'].dropna().tolist())
        key = st.text_input("Employee Code", type='password')
        if st.button("Log in") and authenticate_employee(name, key):
            st.session_state.authenticated = True
            st.session_state.employee_name = name
        elif st.button:
            st.error("Invalid credentials")

def resources_page():
    st.title("Company Resources")
    for res in [
        ("Product Catalogue","Complete list of products","Biolume Salon Prices Catalogue.pdf"),
        ("Employee Handbook","Policies and guidelines","Biolume Employee Handbook.pdf"),
        ("Facial Treatments","List of facial products","Biolume's Facial Treatment Catalogue.pdf")]:
        st.subheader(res[0])
        st.write(res[1])
        if os.path.exists(res[2]):
            st.download_button(f"Download {res[0]}", open(res[2],'rb'))
        else:
            st.error(f"Missing: {res[2]}")
        st.markdown("---")

def announcements_page():
    st.title("Announcements")
    announcements = [
        ("Ansh Birthday","30-05-2025","Join us for celebrations!","ALLGEN TRADING logo.png"),
        ("Office Closure","15-08-2025","Independence Day holiday.","holiday.png"),
        ("New Product Launch","10-07-2025","Stay tuned for our new line!","product.png")
    ]
    for h, d, desc, img in announcements:
        st.subheader(h)
        st.caption(f"Date: {d}")
        if os.path.exists(img):
            st.image(img, use_column_width=True)
        st.write(desc)
        st.markdown("---")

def attendance_page():
    st.title("Attendance")
    emp = st.session_state.employee_name
    code = Person.loc[Person['Employee Name']==emp,'Employee Code'].values[0]
    stats = get_attendance_stats(code)
    cols = st.columns(5)
    cols[0].metric("Present", stats['present'])
    cols[1].metric("Half Days", stats['half_day'])
    cols[2].metric("Mini Half Days", stats['mini_half_day'])
    cols[3].metric("Leaves", stats['leave'])
    cols[4].metric("Total Hours", stats['total_working_hours'])
    st.markdown("---")
    today = format_date(get_ist_time())
    if check_existing(code, today, "Date", "=='"+today+"'"):
        if not check_existing(code, today, "`Check-out Time`", "!='''"):
            if st.button("Check-out"):
                st.success("Checked out")
        else:
            st.info("Already checked out today.")
    else:
        if st.button("Check-in"):
            st.success("Checked in")

# Main
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.employee_name = None

if not st.session_state.authenticated:
    display_login()
else:
    page = st.sidebar.radio("Navigate", ["Attendance","Resources","Announcements"] )
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()
    if page=="Attendance":
        attendance_page()
    elif page=="Resources":
        resources_page()
    else:
        announcements_page()

