import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import pytz
from datetime import datetime
import uuid

# Initialize Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Constants
ATTENDANCE_SHEET_COLUMNS = [
    "Attendance ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Date",
    "Status",
    "Location Link",
    "Leave Reason",
    "Check-in Time",
    "Check-in Date Time"
]

def get_ist_time():
    """Get current time in Indian Standard Time (IST)"""
    utc_now = datetime.now(pytz.utc)
    ist = pytz.timezone('Asia/Kolkata')
    return utc_now.astimezone(ist)

def generate_attendance_id():
    return f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def check_existing_attendance(employee_name):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return False
        
        current_date = get_ist_time().strftime("%d-%m-%Y")
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        
        existing_records = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date)
        ]
        
        return not existing_records.empty
        
    except Exception as e:
        st.error(f"Error checking existing attendance: {str(e)}")
        return False

def record_attendance(employee_name, status, location_link="", leave_reason=""):
    try:
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        designation = Person[Person['Employee Name'] == employee_name]['Designation'].values[0]
        current_date = get_ist_time().strftime("%d-%m-%Y")
        current_datetime = get_ist_time().strftime("%d-%m-%Y %H:%M:%S")
        check_in_time = get_ist_time().strftime("%H:%M:%S")
        
        attendance_id = generate_attendance_id()
        
        attendance_data = {
            "Attendance ID": attendance_id,
            "Employee Name": employee_name,
            "Employee Code": employee_code,
            "Designation": designation,
            "Date": current_date,
            "Status": status,
            "Location Link": location_link,
            "Leave Reason": leave_reason,
            "Check-in Time": check_in_time,
            "Check-in Date Time": current_datetime
        }
        
        attendance_df = pd.DataFrame([attendance_data])
        
        # Read existing data
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        # Concatenate with new data
        updated_data = pd.concat([existing_data, attendance_df], ignore_index=True)
        
        # Write back to Google Sheets
        conn.update(worksheet="Attendance", data=updated_data)
        
        return attendance_id, None
    except Exception as e:
        return None, f"Error creating attendance record: {str(e)}"

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
            <h1 style='margin-bottom: 0;'>Attendance Portal</h1>
            <h2 style='margin-top: 0; color: #555;'>Login</h2>
        </div>
        """, unsafe_allow_html=True)

def authenticate_employee(employee_name, passkey):
    try:
        employee_row = Person[Person['Employee Name'] == employee_name]
        if not employee_row.empty:
            employee_code = employee_row['Employee Code'].values[0]
            return str(passkey) == str(employee_code)
        return False
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return False

def main():
    # Load employee data
    try:
        Person = conn.read(worksheet="Person", ttl=5)
        Person = Person.dropna(how='all')
    except Exception as e:
        st.error(f"Failed to load employee data: {e}")
        st.stop()

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'employee_name' not in st.session_state:
        st.session_state.employee_name = None

    if not st.session_state.authenticated:
        display_login_header()
        
        employee_names = Person['Employee Name'].dropna().tolist()
        
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
                        st.rerun()
                    else:
                        st.error("Invalid Password. Please try again.")
    else:
        st.title("Attendance Management")
        selected_employee = st.session_state.employee_name
        
        if check_existing_attendance(selected_employee):
            st.warning("You have already marked your attendance for today.")
            return
        
        st.subheader("Attendance Status")
        status = st.radio("Select Status", ["Present", "Half Day", "Leave"], index=0, key="attendance_status")
        
        if status in ["Present", "Half Day"]:
            st.subheader("Location Verification")
            col1, col2 = st.columns([3, 1])
            with col1:
                live_location = st.text_input("Enter your current location (Google Maps link or address)", 
                                            help="Please share your live location for verification",
                                            key="location_input")

            
            if st.button("Mark Attendance", key="mark_attendance_button"):
                if not live_location:
                    st.error("Please provide your location")
                else:
                    with st.spinner("Recording attendance..."):
                        attendance_id, error = record_attendance(
                            selected_employee,
                            status,  # Will be "Present" or "Half Day"
                            location_link=live_location
                        )
                        
                        if error:
                            st.error(f"Failed to record attendance: {error}")
                        else:
                            st.success(f"Attendance recorded successfully! ID: {attendance_id}")
                            st.balloons()
        
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
                        attendance_id, error = record_attendance(
                            selected_employee,
                            "Leave",
                            leave_reason=full_reason
                        )
                        
                        if error:
                            st.error(f"Failed to submit leave request: {error}")
                        else:
                            st.success(f"Leave request submitted successfully! ID: {attendance_id}")

if __name__ == "__main__":
    main()
