# app.py
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
import uuid
from PIL import Image
from datetime import datetime, time, timedelta
import pytz
from dateutil.relativedelta import relativedelta

# Initialize Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

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

# Hide Streamlit default UI elements
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stActionButton > button[title="Open source on GitHub"] {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

hide_footer_style = """
    <style>
    footer {
        visibility: hidden;
    }
    footer:after {
        content: '';
        display: none;
    }
    .css-15tx938.e8zbici2 {  /* This class targets the footer in some Streamlit builds */
        display: none !important;
    }
    </style>
"""
st.markdown(hide_footer_style, unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_gsheet_data():
    """Load all required data from Google Sheets"""
    try:
        # Load data from Google Sheets
        Person = conn.read(worksheet="Person", ttl=5)
        
        # Clean data
        Person.dropna(how='all', inplace=True)
        
        # Create a dictionary to hold fill values for each column
        fill_values = {}
        for col in Person.columns:
            if pd.api.types.is_numeric_dtype(Person[col]):
                fill_values[col] = 0  # Fill numeric columns with 0
            else:
                fill_values[col] = ''  # Fill non-numeric with empty string
        
        # Fill all NA values at once using the dictionary
        Person.fillna(value=fill_values, inplace=True)
        
        return Person
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame()

# Load the data
Person = load_gsheet_data()

# Validate data was loaded correctly
if Person.empty:
    st.error("Failed to load required data from Google Sheets. Please check your connection.")
    st.stop()

ATTENDANCE_SHEET_COLUMNS = [
    "Attendance ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Date",
    "Status",
    "Leave Reason",
    "Check-in Time",
    "Check-out Time",
    "Check-in Date Time",
    "Check-out Date Time",
    "Total Working Hours"
]

# Authentication function
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

def check_existing_attendance(employee_name, date=None):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return False
        
        if not date:
            current_date = get_ist_time().strftime("%d-%m-%Y")
        else:
            current_date = date.strftime("%d-%m-%Y")
            
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        
        existing_records = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date)
        ]
        
        return not existing_records.empty
        
    except Exception as e:
        st.error(f"Error checking existing attendance: {str(e)}")
        return False

def check_existing_checkout(employee_name):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return False
        
        current_date = get_ist_time().strftime("%d-%m-%Y")
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        
        existing_records = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date) &
            (existing_data['Check-out Time'] != '')
        ]
        
        return not existing_records.empty
        
    except Exception as e:
        st.error(f"Error checking existing checkout: {str(e)}")
        return False

def check_existing_leave(employee_name, start_date, end_date):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return False
        
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        
        # Create date range to check
        date_range = pd.date_range(start=start_date, end=end_date)
        
        # Check each date in the range
        for date in date_range:
            # Skip weekends
            if date.weekday() >= 5:
                continue
                
            formatted_date = date.strftime("%d-%m-%Y")
            existing_records = existing_data[
                (existing_data['Employee Code'] == employee_code) & 
                (existing_data['Date'] == formatted_date) &
                (existing_data['Status'] == "Leave")
            ]
            
            if not existing_records.empty:
                return True
                
        return False
        
    except Exception as e:
        st.error(f"Error checking existing leave: {str(e)}")
        return True  # Return True to be safe and prevent duplicate submission

def generate_attendance_id():
    return f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def log_attendance_to_gsheet(conn, attendance_data):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        attendance_data = attendance_data.reindex(columns=ATTENDANCE_SHEET_COLUMNS)
        
        updated_data = pd.concat([existing_data, attendance_data], ignore_index=True)
        updated_data = updated_data.drop_duplicates(subset=["Attendance ID"], keep="last")
        
        conn.update(worksheet="Attendance", data=updated_data)
        return True, None
    except Exception as e:
        return False, str(e)

def calculate_working_hours(check_in, check_out):
    try:
        # Parse the time strings into datetime objects
        fmt = "%H:%M:%S"
        check_in_dt = datetime.strptime(check_in, fmt)
        check_out_dt = datetime.strptime(check_out, fmt)
        
        # Calculate the difference
        delta = check_out_dt - check_in_dt
        total_seconds = delta.total_seconds()
        
        # Convert to hours
        hours = total_seconds / 3600
        return round(hours, 2)
    except Exception as e:
        st.error(f"Error calculating working hours: {str(e)}")
        return 0

def determine_status(check_in_time_str, check_out_time_str=None):
    try:
        # Parse check-in time
        check_in_time = datetime.strptime(check_in_time_str, "%H:%M:%S").time()
        
        # Define time thresholds
        mini_half_day_start = time(10, 30)
        half_day_start = time(11, 30)
        early_checkout = time(17, 0)
        
        # Determine status based on check-in time
        if check_in_time >= half_day_start:
            return "Half Day"
        elif check_in_time >= mini_half_day_start:
            return "Mini Half Day"
        
        # If check-out time is provided, check for early checkout
        if check_out_time_str:
            check_out_time = datetime.strptime(check_out_time_str, "%H:%M:%S").time()
            if check_out_time < early_checkout:
                return "Half Day"
        
        return "Present"
    except Exception as e:
        st.error(f"Error determining status: {str(e)}")
        return "Present"

def record_attendance(employee_name, status=None, leave_reason="", is_checkout=False):
    try:
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        designation = Person[Person['Employee Name'] == employee_name]['Designation'].values[0]
        current_date = get_ist_time().strftime("%d-%m-%Y")
        current_datetime = get_ist_time().strftime("%d-%m-%Y %H:%M:%S")
        current_time = get_ist_time().strftime("%H:%M:%S")
        
        if is_checkout:
            # Update existing attendance record with checkout time
            existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
            existing_data = existing_data.dropna(how='all')
            
            today_record = existing_data[
                (existing_data['Employee Code'] == employee_code) & 
                (existing_data['Date'] == current_date)
            ]
            
            if not today_record.empty:
                attendance_id = today_record.iloc[0]['Attendance ID']
                
                # Update the record
                today_record.at[today_record.index[0], 'Check-out Time'] = current_time
                today_record.at[today_record.index[0], 'Check-out Date Time'] = current_datetime
                
                # Calculate working hours
                check_in_time = today_record.iloc[0]['Check-in Time']
                working_hours = calculate_working_hours(check_in_time, current_time)
                today_record.at[today_record.index[0], 'Total Working Hours'] = working_hours
                
                # Determine final status based on check-in and check-out times
                final_status = determine_status(check_in_time, current_time)
                today_record.at[today_record.index[0], 'Status'] = final_status
                
                # Update the sheet
                updated_data = existing_data.copy()
                updated_data.update(today_record)
                conn.update(worksheet="Attendance", data=updated_data)
                
                return attendance_id, None
            else:
                return None, "No attendance record found for today to checkout"
        else:
            # Create new attendance record
            attendance_id = generate_attendance_id()
            
            # Determine status if not provided (for leave)
            if status is None:
                status = determine_status(current_time)
            
            attendance_data = {
                "Attendance ID": attendance_id,
                "Employee Name": employee_name,
                "Employee Code": employee_code,
                "Designation": designation,
                "Date": current_date,
                "Status": status,
                "Leave Reason": leave_reason,
                "Check-in Time": current_time,
                "Check-out Time": "",
                "Check-in Date Time": current_datetime,
                "Check-out Date Time": "",
                "Total Working Hours": ""
            }
            
            attendance_df = pd.DataFrame([attendance_data])
            
            success, error = log_attendance_to_gsheet(conn, attendance_df)
            
            if success:
                return attendance_id, None
            else:
                return None, error
                
    except Exception as e:
        return None, f"Error creating attendance record: {str(e)}"

def record_future_leave(employee_name, start_date, end_date, leave_type, leave_reason):
    try:
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        designation = Person[Person['Employee Name'] == employee_name]['Designation'].values[0]
        
        # Generate a single leave ID for this leave request
        leave_id = f"LEAVE-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"
        
        # Create a date range
        date_range = pd.date_range(start=start_date, end=end_date)
        
        attendance_records = []
        
        for date in date_range:
            # Skip weekends (Saturday=5, Sunday=6)
            if date.weekday() >= 5:
                continue
                
            # Format the date
            formatted_date = date.strftime("%d-%m-%Y")
            
            attendance_id = f"{leave_id}-{date.strftime('%Y%m%d')}"
            
            attendance_data = {
                "Attendance ID": attendance_id,
                "Employee Name": employee_name,
                "Employee Code": employee_code,
                "Designation": designation,
                "Date": formatted_date,
                "Status": "Leave",
                "Leave Reason": f"{leave_type}: {leave_reason}",
                "Check-in Time": "",
                "Check-out Time": "",
                "Check-in Date Time": "",
                "Check-out Date Time": "",
                "Total Working Hours": ""
            }
            
            attendance_records.append(attendance_data)
        
        attendance_df = pd.DataFrame(attendance_records)
        success, error = log_attendance_to_gsheet(conn, attendance_df)
        
        if success:
            return leave_id, None
        else:
            return None, error
            
    except Exception as e:
        return None, f"Error creating future leave records: {str(e)}"

def get_attendance_stats(employee_name):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return {
                "present": 0,
                "half_day": 0,
                "mini_half_day": 0,
                "leave": 0,
                "total_working_hours": 0
            }
        
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        current_month = get_ist_time().strftime("%m-%Y")
        
        # Filter for current month and employee
        employee_data = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'].str.endswith(current_month))
        ]
        
        if employee_data.empty:
            return {
                "present": 0,
                "half_day": 0,
                "mini_half_day": 0,
                "leave": 0,
                "total_working_hours": 0
            }
        
        # Calculate stats
        present = len(employee_data[employee_data['Status'] == "Present"])
        half_day = len(employee_data[employee_data['Status'] == "Half Day"])
        mini_half_day = len(employee_data[employee_data['Status'] == "Mini Half Day"])
        leave = len(employee_data[employee_data['Status'] == "Leave"])
        
        # Calculate total working hours (only for days with check-out)
        working_hours_data = employee_data[employee_data['Total Working Hours'] != '']
        total_hours = working_hours_data['Total Working Hours'].astype(float).sum()
        
        return {
            "present": present,
            "half_day": half_day,
            "mini_half_day": mini_half_day,
            "leave": leave,
            "total_working_hours": round(total_hours, 2)
        }
        
    except Exception as e:
        st.error(f"Error calculating attendance stats: {str(e)}")
        return {
            "present": 0,
            "half_day": 0,
            "mini_half_day": 0,
            "leave": 0,
            "total_working_hours": 0
        }

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

def announcements_page():
    st.title("Company Announcements")
    st.markdown("Stay updated with the latest company news and announcements.")
    
    # Define the announcements (you can also load this from a JSON file or Google Sheet)
    announcements = [
        {
            "Heading": "Biolume Day",
            "Date": "30/05/2025",
            "Description": "Join us for our annual Biolume Day celebration with special events and activities.",
            "file_path": "ALLGEN TRADING logo.png"
        },
        {
            "Heading": "Office Closure",
            "Date": "15/08/2025",
            "Description": "The office will be closed on Independence Day. Wishing everyone a happy holiday!",
            "file_path": "holiday.png"
        },
        {
            "Heading": "New Product Launch",
            "Date": "10/07/2025",
            "Description": "Exciting new product line launching next month. Stay tuned for details!",
            "file_path": "product.png"
        }
    ]
    
    # Display each announcement in a card-like format
    for announcement in announcements:
        with st.container():
            # Create columns for layout (image on left, text on right)
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Display image if available
                if os.path.exists(announcement["file_path"]):
                    try:
                        image = Image.open(announcement["file_path"])
                        st.image(image, use_column_width=True)
                    except Exception as e:
                        st.error(f"Could not load image: {str(e)}")
                else:
                    st.error(f"Image not found: {announcement['file_path']}")
            
            with col2:
                st.subheader(announcement["Heading"])
                st.caption(f"Date: {announcement['Date']}")
                st.write(announcement["Description"])
            
            st.markdown("---")  # Divider between announcements

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
    
    if st.button("← logout", key="back_button"):
        st.session_state.authenticated = False
        st.session_state.selected_mode = None
        st.rerun()

def attendance_page():
    st.title("Attendance Management")
    selected_employee = st.session_state.employee_name
    
    # Display attendance stats for current month
    stats = get_attendance_stats(selected_employee)
    st.subheader("This Month's Attendance Summary")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Present", stats['present'])
    col2.metric("Half Days", stats['half_day'])
    col3.metric("Mini Half Days", stats['mini_half_day'])
    col4.metric("Leaves", stats['leave'])
    col5.metric("Total Hours", stats['total_working_hours'])
    
    st.markdown("---")
    
    # Check if attendance is already marked for today
    today_marked = check_existing_attendance(selected_employee)
    if today_marked:
        # Check if checkout is already done
        if check_existing_checkout(selected_employee):
            st.warning("You have already marked your attendance and checkout for today.")
        else:
            st.info("You have already marked your attendance for today.")
            if st.button("Mark Check-out", key="checkout_button"):
                with st.spinner("Recording checkout..."):
                    attendance_id, error = record_attendance(
                        selected_employee,
                        is_checkout=True
                    )
                    
                    if error:
                        st.error(f"Failed to record checkout: {error}")
                    else:
                        st.success(f"Checkout recorded successfully! ID: {attendance_id}")
                        st.balloons()
                        st.rerun()
    
    # Main attendance options - separate tabs
    tab1, tab2 = st.tabs(["Today's Attendance", "Apply for Leave"])
    
    with tab1:
        if not today_marked:
            st.subheader("Mark Today's Attendance")
            
            if st.button("Check-in", key="checkin_button"):
                with st.spinner("Recording attendance..."):
                    attendance_id, error = record_attendance(selected_employee)
                    
                    if error:
                        st.error(f"Failed to record attendance: {error}")
                    else:
                        st.success(f"Attendance recorded successfully! ID: {attendance_id}")
                        st.balloons()
                        st.rerun()
        else:
            st.info("Today's attendance already marked. Use the 'Apply for Leave' tab for future dates.")
    
    with tab2:
        st.subheader("Apply for Leave")
        
        tomorrow = get_ist_time().date() + timedelta(days=1)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date*",
                min_value=tomorrow,
                value=tomorrow,
                help="Select the first day of your leave (must be future date)"
            )
        with col2:
            end_date = st.date_input(
                "End Date*",
                min_value=tomorrow,
                help="Select the last day of your leave"
            )
        
        if start_date > end_date:
            st.error("End date must be after start date")
        
        leave_types = ["Sick Leave", "Personal Leave", "Vacation", "Other"]
        leave_type = st.selectbox("Leave Type*", leave_types, key="leave_type")
        
        leave_reason = st.text_area(
            "Reason for Leave*",
            placeholder="Please provide details about your leave",
            key="leave_reason"
        )
        
        if st.button("Submit Leave Request", key="submit_leave"):
            if not leave_reason:
                st.error("Please provide a reason for your leave")
            elif start_date > end_date:
                st.error("End date must be after start date")
            else:
                # Check if these dates already have leave applied
                existing_leave = check_existing_leave(selected_employee, start_date, end_date)
                if existing_leave:
                    st.error("You already have leave applied for some or all of these dates")
                else:
                    with st.spinner("Submitting leave request..."):
                        leave_id, error = record_future_leave(
                            selected_employee,
                            start_date,
                            end_date,
                            leave_type,
                            leave_reason
                        )
                        
                        if error:
                            st.error(f"Failed to submit leave request: {error}")
                        else:
                            st.success(f"Leave request submitted successfully from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}")
                            st.balloons()
                            st.rerun()

def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_mode' not in st.session_state:
        st.session_state.selected_mode = None
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
        st.title("Select Mode")
        col1, col2, col3 = st.columns(3)  # Changed to 3 columns
        
        with col1:
            if st.button("Attendance", use_container_width=True, key="attendance_mode"):
                st.session_state.selected_mode = "Attendance"
                st.rerun()
                
        with col2:
            if st.button("Resources", use_container_width=True, key="resources_mode"):
                st.session_state.selected_mode = "Resources"
                st.rerun()
        
        with col3:
            if st.button("Announcements", use_container_width=True, key="announcements_mode"):
                st.session_state.selected_mode = "Announcements"
                st.rerun()
        
        if st.session_state.selected_mode:
            add_back_button()
            
            if st.session_state.selected_mode == "Attendance":
                attendance_page()
            elif st.session_state.selected_mode == "Resources":
                resources_page()
            elif st.session_state.selected_mode == "Announcements":
                announcements_page()

if __name__ == "__main__":
    main()
