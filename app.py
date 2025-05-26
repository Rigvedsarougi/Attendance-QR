import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
import uuid
from PIL import Image
from datetime import datetime, time, timedelta
import pytz
import time

# Hide Streamlit style elements
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stActionButton > button[title="Open source on GitHub"] {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Constants
ATTENDANCE_SHEET_COLUMNS = [
    "Attendance ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Date",
    "Check-in Time",
    "Check-out Time",
    "Status",
    "Location Link",
    "Leave Reason",
    "Total Hours"
]

# Establishing a Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Load employee data
Person = pd.read_csv('Invoice - Person.csv')

def get_ist_time():
    """Get current time in Indian Standard Time (IST)"""
    utc_now = datetime.now(pytz.utc)
    ist = pytz.timezone('Asia/Kolkata')
    return utc_now.astimezone(ist)

def display_login_header():
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        try:
            logo = Image.open("logo.png")
            st.image(logo, use_container_width=True)
        except FileNotFoundError:
            st.warning("Logo image not found. Please ensure 'logo.png' exists in the same directory.")
        except Exception as e:
            st.warning(f"Could not load logo: {str(e)}")
        
        st.markdown("""
        <div style='text-align: center; margin-bottom: 30px;'>
            <h1 style='margin-bottom: 0;'>Employee Portal</h1>
            <h2 style='margin-top: 0; color: #555;'>Login</h2>
        </div>
        """, unsafe_allow_html=True)

def authenticate_employee(employee_name, passkey):
    try:
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        return str(passkey) == str(employee_code)
    except:
        return False

def generate_attendance_id():
    return f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def log_attendance_to_gsheet(conn, attendance_data):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        
        attendance_data = attendance_data.reindex(columns=ATTENDANCE_SHEET_COLUMNS)
        
        updated_data = pd.concat([existing_data, attendance_data], ignore_index=True)
        updated_data = updated_data.drop_duplicates(subset=["Attendance ID"], keep="last")
        
        conn.update(worksheet="Attendance", data=updated_data)
        return True, None
    except Exception as e:
        return False, str(e)

def check_todays_attendance(employee_name):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        
        if existing_data.empty:
            return None, None, None
        
        current_date = get_ist_time().strftime("%d-%m-%Y")
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        
        todays_record = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date)
        ]
        
        if todays_record.empty:
            return None, None, None
        
        check_in = todays_record.iloc[0].get('Check-in Time', None)
        check_out = todays_record.iloc[0].get('Check-out Time', None)
        status = todays_record.iloc[0].get('Status', None)
        
        return check_in, check_out, status
        
    except Exception as e:
        st.error(f"Error checking attendance: {str(e)}")
        return None, None, None

def get_location():
    result = st.session_state.get('location', None)
    if result is None:
        result = streamlit_js_eval(
            js_expressions="""
                new Promise((resolve) => {
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}),
                            err => resolve({latitude: null, longitude: null})
                        );
                    } else {
                        resolve({latitude: null, longitude: null});
                    }
                });
            """,
            key="geo"
        ) or {}
        st.session_state.location = result
    
    lat = result.get("latitude")
    lng = result.get("longitude")
    
    if lat and lng:
        return f"https://maps.google.com/?q={lat},{lng}"
    return ""

def resources_page():
    st.title("Company Resources")
    st.markdown("Download important company documents and product catalogs.")
    
    # Define the resources
    resources = [
        {
            "name": "Product Catalogue",
            "description": "Complete list of all available products with specifications",
            "file_path": "Biolume Salon Prices Catalogue.pdf"
        },
        {
            "name": "Employee Handbook",
            "description": "Company policies, procedures, and guidelines for employees",
            "file_path": "Biolume Employee Handbook.pdf"
        },
        {
            "name": "Facial Treatment Catalogue",
            "description": "Complete list of all Facial products with specifications",
            "file_path": "Biolume's Facial Treatment Catalogue.pdf"
        }
    ]
    
    # Display each resource in a card-like format
    for resource in resources:
        with st.container():
            st.subheader(resource["name"])
            st.markdown(resource["description"])
            
            # Check if file exists
            if os.path.exists(resource["file_path"]):
                with open(resource["file_path"], "rb") as file:
                    btn = st.download_button(
                        label=f"Download {resource['name']}",
                        data=file,
                        file_name=resource["file_path"],
                        mime="application/pdf",
                        key=f"download_{resource['name']}"
                    )
            else:
                st.error(f"File not found: {resource['file_path']}")
            
            st.markdown("---")  # Divider between resources

def attendance_page():
    st.title("Attendance Management")
    selected_employee = st.session_state.employee_name
    
    # Check today's attendance status
    check_in, check_out, status = check_todays_attendance(selected_employee)
    
    tab1, tab2 = st.tabs(["Check-in", "Check-out"])
    
    with tab1:
        st.subheader("Daily Check-in")
        
        if check_in:
            st.success(f"You have already checked in today at {check_in}")
            st.write(f"Status: {status}")
        else:
            st.subheader("Attendance Status")
            status = st.radio("Select Status", ["Present", "Half Day", "Leave"], index=0, key="attendance_status")
            
            if status in ["Present", "Half Day"]:
                location_link = get_location()
                
                if location_link:
                    st.success(f"Location captured: [View on Map]({location_link})")
                else:
                    st.warning("Could not capture location. Please enable location services.")
                
                if st.button("Check-in", key="check_in_button"):
                    if not location_link and status != "Leave":
                        st.error("Location is required for check-in")
                    else:
                        with st.spinner("Recording check-in..."):
                            attendance_id = generate_attendance_id()
                            current_date = get_ist_time().strftime("%d-%m-%Y")
                            current_time = get_ist_time().strftime("%H:%M:%S")
                            current_datetime = get_ist_time().strftime("%d-%m-%Y %H:%M:%S")
                            
                            attendance_data = {
                                "Attendance ID": attendance_id,
                                "Employee Name": selected_employee,
                                "Employee Code": Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0],
                                "Designation": Person[Person['Employee Name'] == selected_employee]['Designation'].values[0],
                                "Date": current_date,
                                "Check-in Time": current_time,
                                "Check-out Time": "",
                                "Status": status,
                                "Location Link": location_link,
                                "Leave Reason": "",
                                "Total Hours": ""
                            }
                            
                            success, error = log_attendance_to_gsheet(conn, pd.DataFrame([attendance_data]))
                            
                            if success:
                                st.success(f"Check-in recorded successfully at {current_time}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"Failed to record check-in: {error}")
            else:
                st.subheader("Leave Details")
                leave_types = ["Sick Leave", "Personal Leave", "Vacation", "Other"]
                leave_type = st.selectbox("Leave Type", leave_types, key="leave_type")
                leave_reason = st.text_area("Reason for Leave",
                                           placeholder="Please provide details about your leave",
                                           key="leave_reason")
                
                if st.button("Submit Leave Request", key="submit_leave_button"):
                    if not leave_reason:
                        st.error("Please provide a reason for your leave")
                    else:
                        full_reason = f"{leave_type}: {leave_reason}"
                        with st.spinner("Submitting leave request..."):
                            attendance_id = generate_attendance_id()
                            current_date = get_ist_time().strftime("%d-%m-%Y")
                            current_time = get_ist_time().strftime("%H:%M:%S")
                            
                            attendance_data = {
                                "Attendance ID": attendance_id,
                                "Employee Name": selected_employee,
                                "Employee Code": Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0],
                                "Designation": Person[Person['Employee Name'] == selected_employee]['Designation'].values[0],
                                "Date": current_date,
                                "Check-in Time": current_time,
                                "Check-out Time": "",
                                "Status": "Leave",
                                "Location Link": "",
                                "Leave Reason": full_reason,
                                "Total Hours": ""
                            }
                            
                            success, error = log_attendance_to_gsheet(conn, pd.DataFrame([attendance_data]))
                            
                            if success:
                                st.success("Leave request submitted successfully!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"Failed to submit leave request: {error}")
    
    with tab2:
        st.subheader("Daily Check-out")
        
        if not check_in:
            st.warning("You need to check-in first before checking out")
        elif check_out:
            st.success(f"You have already checked out today at {check_out}")
            
            # Calculate total hours if available
            total_hours = check_todays_attendance(selected_employee)[2]
            if total_hours:
                st.write(f"Total hours: {total_hours}")
        else:
            location_link = get_location()
            
            if location_link:
                st.success(f"Location captured: [View on Map]({location_link})")
            else:
                st.warning("Could not capture location. Please enable location services.")
            
            if st.button("Check-out", key="check_out_button"):
                if not location_link:
                    st.error("Location is required for check-out")
                else:
                    with st.spinner("Recording check-out..."):
                        try:
                            # Get existing attendance data
                            existing_data = conn.read(worksheet="Attendance", ttl=5)
                            existing_data = existing_data.dropna(how="all")
                            
                            current_date = get_ist_time().strftime("%d-%m-%Y")
                            employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
                            
                            # Find today's record
                            mask = (
                                (existing_data['Employee Code'] == employee_code) & 
                                (existing_data['Date'] == current_date)
                            
                            if not existing_data[mask].empty:
                                # Update the record
                                current_time = get_ist_time().strftime("%H:%M:%S")
                                existing_data.loc[mask, 'Check-out Time'] = current_time
                                existing_data.loc[mask, 'Location Link'] = location_link
                                
                                # Calculate total hours
                                check_in_time = existing_data.loc[mask, 'Check-in Time'].iloc[0]
                                try:
                                    fmt = "%H:%M:%S"
                                    check_in_dt = datetime.strptime(check_in_time, fmt)
                                    check_out_dt = datetime.strptime(current_time, fmt)
                                    total_hours = (check_out_dt - check_in_dt).total_seconds() / 3600
                                    existing_data.loc[mask, 'Total Hours'] = f"{total_hours:.2f} hours"
                                except:
                                    existing_data.loc[mask, 'Total Hours'] = "N/A"
                                
                                # Update the sheet
                                conn.update(worksheet="Attendance", data=existing_data)
                                st.success(f"Check-out recorded successfully at {current_time}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("No check-in record found for today")
                        except Exception as e:
                            st.error(f"Failed to record check-out: {str(e)}")

def add_back_button():
    st.markdown("""
    <style>
    .back-button {
        position: fixed;
        bottom: 20px;
        left: 20px;
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("← Logout", key="back_button"):
        st.session_state.authenticated = False
        st.session_state.selected_mode = None
        st.session_state.employee_name = None
        st.session_state.location = None
        st.rerun()

def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_mode' not in st.session_state:
        st.session_state.selected_mode = None
    if 'employee_name' not in st.session_state:
        st.session_state.employee_name = None
    if 'location' not in st.session_state:
        st.session_state.location = None

    if not st.session_state.authenticated:
        # Display the centered logo and heading
        display_login_header()

        employee_names = Person['Employee Name'].tolist()

        # Create centered form
        form_col1, form_col2, form_col3 = st.columns([1, 2, 1])

        with form_col2:
            with st.container():
                employee_name = st.selectbox(
                    "Select Your Name", 
                    employee_names, 
                    key="employee_select"
                )
                passkey = st.text_input(
                    "Enter Your Employee Code", 
                    type="password", 
                    key="passkey_input"
                )

                login_button = st.button(
                    "Log in", 
                    key="login_button",
                    use_container_width=True
                )

                if login_button:
                    if authenticate_employee(employee_name, passkey):
                        st.session_state.authenticated = True
                        st.session_state.employee_name = employee_name
                        
                        # Get location immediately after login
                        location_link = get_location()
                        if location_link:
                            st.success("Location captured for attendance purposes")
                        st.rerun()
                    else:
                        st.error("Invalid Password. Please try again.")
    else:
        # Show option boxes after login
        st.title("Employee Portal")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Attendance", use_container_width=True, key="attendance_mode"):
                st.session_state.selected_mode = "Attendance"
                st.rerun()

        with col2:
            if st.button("Resources", use_container_width=True, key="resources_mode"):
                st.session_state.selected_mode = "Resources"
                st.rerun()

        if st.session_state.selected_mode:
            add_back_button()

            if st.session_state.selected_mode == "Attendance":
                attendance_page()
            elif st.session_state.selected_mode == "Resources":
                resources_page()

if __name__ == "__main__":
    main()
