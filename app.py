import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
import uuid
from PIL import Image
from datetime import datetime, time, timedelta
import pytz
import time
from streamlit_js_eval import streamlit_js_eval

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
            st.warning("Logo image not found. Please ensure 'logo.png' exists.")
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
        employee_code = Person.loc[Person['Employee Name'] == employee_name, 'Employee Code'].values[0]
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
        employee_code = Person.loc[Person['Employee Name'] == employee_name, 'Employee Code'].values[0]
        todays_record = existing_data[
            (existing_data['Employee Code'] == employee_code) &
            (existing_data['Date'] == current_date)
        ]
        if todays_record.empty:
            return None, None, None
        return (
            todays_record.iloc[0].get('Check-in Time', None),
            todays_record.iloc[0].get('Check-out Time', None),
            todays_record.iloc[0].get('Total Hours', None)
        )
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
    lat, lng = result.get("latitude"), result.get("longitude")
    if lat and lng:
        return f"https://maps.google.com/?q={lat},{lng}"
    return ""

def resources_page():
    st.title("Company Resources")
    st.markdown("Download important company documents and product catalogs.")
    resources = [
        {"name": "Product Catalogue", "description": "List of all products with specs", "file_path": "Biolume Salon Prices Catalogue.pdf"},
        {"name": "Employee Handbook", "description": "Company policies and guidelines", "file_path": "Biolume Employee Handbook.pdf"},
        {"name": "Facial Treatment Catalogue", "description": "All facial products specs", "file_path": "Biolume's Facial Treatment Catalogue.pdf"}
    ]
    for res in resources:
        st.subheader(res["name"])
        st.markdown(res["description"])
        if os.path.exists(res["file_path"]):
            with open(res["file_path"], "rb") as file:
                st.download_button(f"Download {res['name']}", data=file, file_name=res["file_path"], mime="application/pdf")
        else:
            st.error(f"File not found: {res['file_path']}")
        st.markdown("---")

def attendance_page():
    st.title("Attendance Management")
    selected_employee = st.session_state.employee_name
    check_in, check_out, total_hours = check_todays_attendance(selected_employee)
    tab1, tab2 = st.tabs(["Check-in", "Check-out"])

    with tab1:
        st.subheader("Daily Check-in")
        if check_in:
            st.success(f"Checked in at {check_in}")
            st.write(f"Total hours so far: {total_hours or 'N/A'}")
        else:
            status = st.radio("Select Status", ["Present", "Half Day", "Leave"], index=0, key="attendance_status")
            if status in ["Present", "Half Day"]:
                location_link = get_location()
                if location_link:
                    st.success(f"Location captured: [Map]({location_link})")
                else:
                    st.warning("Enable location services.")
                if st.button("Check-in", key="check_in_button"):
                    if not location_link:
                        st.error("Location required for check-in.")
                    else:
                        attendance_data = {
                            "Attendance ID": generate_attendance_id(),
                            "Employee Name": selected_employee,
                            "Employee Code": Person.loc[Person['Employee Name'] == selected_employee, 'Employee Code'].values[0],
                            "Designation": Person.loc[Person['Employee Name'] == selected_employee, 'Designation'].values[0],
                            "Date": get_ist_time().strftime("%d-%m-%Y"),
                            "Check-in Time": get_ist_time().strftime("%H:%M:%S"),
                            "Check-out Time": "",
                            "Status": status,
                            "Location Link": location_link,
                            "Leave Reason": "",
                            "Total Hours": ""
                        }
                        success, error = log_attendance_to_gsheet(conn, pd.DataFrame([attendance_data]))
                        if success:
                            st.success("Check-in recorded!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"Error: {error}")
            else:
                st.subheader("Leave Details")
                lt = st.selectbox("Leave Type", ["Sick", "Personal", "Vacation", "Other"], key="leave_type")
                lr = st.text_area("Reason", key="leave_reason")
                if st.button("Submit Leave", key="submit_leave_button"):
                    if not lr:
                        st.error("Provide a reason.")
                    else:
                        attendance_data = {
                            "Attendance ID": generate_attendance_id(),
                            "Employee Name": selected_employee,
                            "Employee Code": Person.loc[Person['Employee Name'] == selected_employee, 'Employee Code'].values[0],
                            "Designation": Person.loc[Person['Employee Name'] == selected_employee, 'Designation'].values[0],
                            "Date": get_ist_time().strftime("%d-%m-%Y"),
                            "Check-in Time": get_ist_time().strftime("%H:%M:%S"),
                            "Check-out Time": "",
                            "Status": "Leave",
                            "Location Link": "",
                            "Leave Reason": f"{lt}: {lr}",
                            "Total Hours": ""
                        }
                        success, error = log_attendance_to_gsheet(conn, pd.DataFrame([attendance_data]))
                        if success:
                            st.success("Leave submitted!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"Error: {error}")

    with tab2:
        st.subheader("Daily Check-out")
        if not check_in:
            st.warning("Check in first.")
        elif check_out:
            st.success(f"Checked out at {check_out}")
            st.write(f"Total hours: {total_hours or 'N/A'}")
        else:
            location_link = get_location()
            if location_link:
                st.success(f"Location captured: [Map]({location_link})")
            else:
                st.warning("Enable location services.")
            if st.button("Check-out", key="check_out_button"):
                if not location_link:
                    st.error("Location required for check-out.")
                else:
                    with st.spinner("Recording check-out..."):
                        try:
                            existing_data = conn.read(worksheet="Attendance", ttl=5).dropna(how="all")
                            current_date = get_ist_time().strftime("%d-%m-%Y")
                            employee_code = Person.loc[Person['Employee Name'] == selected_employee, 'Employee Code'].values[0]

                            # <<< FIXED: close parentheses here >>>
                            mask = (
                                (existing_data['Employee Code'] == employee_code) &
                                (existing_data['Date'] == current_date)
                            )
                            if not existing_data.loc[mask].empty:
                                now_str = get_ist_time().strftime("%H:%M:%S")
                                existing_data.loc[mask, 'Check-out Time'] = now_str
                                existing_data.loc[mask, 'Location Link'] = location_link

                                # Calculate total hours
                                ci = existing_data.loc[mask, 'Check-in Time'].iloc[0]
                                try:
                                    fmt = "%H:%M:%S"
                                    ci_dt = datetime.strptime(ci, fmt)
                                    co_dt = datetime.strptime(now_str, fmt)
                                    hours = (co_dt - ci_dt).total_seconds() / 3600
                                    existing_data.loc[mask, 'Total Hours'] = f"{hours:.2f} hours"
                                except:
                                    existing_data.loc[mask, 'Total Hours'] = "N/A"

                                conn.update(worksheet="Attendance", data=existing_data)
                                st.success(f"Check-out recorded at {now_str}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("No check-in record for today.")
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
        for key in ["authenticated", "selected_mode", "employee_name", "location"]:
            st.session_state.pop(key, None)
        st.rerun()

def main():
    # Initialize session state
    for var in ("authenticated", "selected_mode", "employee_name", "location"):
        if var not in st.session_state:
            st.session_state[var] = False if var == "authenticated" else None

    if not st.session_state.authenticated:
        display_login_header()
        names = Person['Employee Name'].tolist()
        emp_col1, emp_col2, emp_col3 = st.columns([1,2,1])
        with emp_col2:
            name = st.selectbox("Select Your Name", names, key="employee_select")
            key_in = st.text_input("Enter Your Employee Code", type="password", key="passkey_input")
            if st.button("Log in", key="login_button"):
                if authenticate_employee(name, key_in):
                    st.session_state.authenticated = True
                    st.session_state.employee_name = name
                    if get_location():
                        st.success("Location captured")
                    st.rerun()
                else:
                    st.error("Invalid code.")
    else:
        st.title("Employee Portal")
        col1, col2 = st.columns(2)
        if col1.button("Attendance", use_container_width=True):
            st.session_state.selected_mode = "Attendance"
            st.rerun()
        if col2.button("Resources", use_container_width=True):
            st.session_state.selected_mode = "Resources"
            st.rerun()

        if st.session_state.selected_mode:
            add_back_button()
            if st.session_state.selected_mode == "Attendance":
                attendance_page()
            else:
                resources_page()

if __name__ == "__main__":
    main()
