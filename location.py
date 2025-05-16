import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# Set page config
st.set_page_config(page_title="Admin Dashboard", layout="wide")

# Hide Streamlit style
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stActionButton > button[title="Open source on GitHub"] {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Constants
LOCATION_TRACKING_SHEET = "LocationTracking"
ADMIN_PASSWORD = "admin123"  # Change this to a more secure password

# Establish connection
conn = st.connection("gsheets", type=GSheetsConnection)

def authenticate_admin():
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.title("Admin Login")
        password = st.text_input("Enter Admin Password", type="password")
        
        if st.button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        return False
    return True

def get_location_data():
    try:
        data = conn.read(worksheet=LOCATION_TRACKING_SHEET, ttl=5)
        data = data.dropna(how="all")
        
        # Convert columns to proper types
        data['Date'] = pd.to_datetime(data['Date'], dayfirst=True)
        data['Time'] = pd.to_datetime(data['Time'], format='%H:%M:%S').dt.time
        data['Latitude'] = pd.to_numeric(data['Latitude'], errors='coerce')
        data['Longitude'] = pd.to_numeric(data['Longitude'], errors='coerce')
        
        return data
    except Exception as e:
        st.error(f"Error loading location data: {e}")
        return pd.DataFrame()

def display_location_map(data):
    st.subheader("Employee Locations")
    
    # Filter active employees
    active_data = data[data['Status'] == 'active']
    
    if not active_data.empty:
        # Create map
        fig = px.scatter_mapbox(
            active_data,
            lat="Latitude",
            lon="Longitude",
            hover_name="Employee Name",
            hover_data=["Date", "Time", "Address", "Accuracy (m)"],
            color="Employee Name",
            zoom=10,
            height=600
        )
        
        fig.update_layout(mapbox_style="open-street-map")
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No active location data available")

def display_location_history(data):
    st.subheader("Location History")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        employee_filter = st.multiselect(
            "Filter by Employee",
            options=data['Employee Name'].unique(),
            default=data['Employee Name'].unique()
        )
    with col2:
        date_filter = st.date_input(
            "Filter by Date",
            value=[datetime.now().date() - timedelta(days=7), datetime.now().date()],
            max_value=datetime.now().date()
        )
    with col3:
        status_filter = st.multiselect(
            "Filter by Status",
            options=data['Status'].unique(),
            default=['active', 'inactive']
        )
    
    filtered_data = data[
        (data['Employee Name'].isin(employee_filter)) &
        (data['Date'].between(pd.to_datetime(date_filter[0]), pd.to_datetime(date_filter[1]))) &
        (data['Status'].isin(status_filter))
    ]
    
    if not filtered_data.empty:
        st.dataframe(
            filtered_data.sort_values(['Date', 'Time'], ascending=False),
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        csv = filtered_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download as CSV",
            csv,
            "location_history.csv",
            "text/csv",
            key='download-location-csv'
        )
    else:
        st.warning("No data matching filters")

def display_analytics(data):
    st.subheader("Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Daily activity count
        daily_activity = data.groupby(['Date', 'Employee Name']).size().unstack().fillna(0)
        st.bar_chart(daily_activity)
    
    with col2:
        # Employee activity count
        employee_activity = data['Employee Name'].value_counts().reset_index()
        employee_activity.columns = ['Employee', 'Location Reports']
        st.dataframe(employee_activity, hide_index=True)

def main():
    if not authenticate_admin():
        return
    
    st.title("Admin Dashboard - Location Tracking")
    
    data = get_location_data()
    if data.empty:
        st.warning("No location data available")
        return
    
    tab1, tab2, tab3 = st.tabs(["Live Tracking", "History", "Analytics"])
    
    with tab1:
        display_location_map(data)
    
    with tab2:
        display_location_history(data)
    
    with tab3:
        display_analytics(data)

if __name__ == "__main__":
    main()
