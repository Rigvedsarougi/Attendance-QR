import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
from datetime import datetime
import pytz
import os
import time
from PIL import Image
import cv2
import numpy as np

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
    "Check-in Date Time",
    "QR Code Scanned"
]

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
            st.image(logo, use_column_width=True)
        except FileNotFoundError:
            st.warning("Logo image not found. Please ensure 'logo.png' exists in the same directory.")
        except Exception as e:
            st.warning(f"Could not load logo: {str(e)}")
        
        st.markdown("""
        <div style='text-align: center; margin-bottom: 30px;'>
            <h1 style='margin-bottom: 0;'>Employee Portal</h1>
            <h2 style='margin-top: 0; color: #555;'>Attendance System</h2>
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

def generate_attendance_id():
    return f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

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

def record_attendance(employee_name, status, location_link="", leave_reason="", qr_scanned=False):
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
            "Check-in Date Time": current_datetime,
            "QR Code Scanned": "Yes" if qr_scanned else "No"
        }
        
        attendance_df = pd.DataFrame([attendance_data], columns=ATTENDANCE_SHEET_COLUMNS)
        
        # Read existing data
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        # Concatenate with new data
        updated_data = pd.concat([existing_data, attendance_df], ignore_index=True)
        
        # Write to Google Sheets
        conn.update(worksheet="Attendance", data=updated_data)
        
        return attendance_id, None
    except Exception as e:
        return None, f"Error creating attendance record: {str(e)}"

def generate_qr_code(data, filename="qrcode.png"):
    """Generate a QR code image from the given data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    return filename

def scan_qr_code():
    """Scan QR code from webcam"""
    st.write("Scanning QR Code...")
    
    # Start webcam
    cap = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()
    scanned_data = None
    
    # Create placeholder for the webcam feed
    image_placeholder = st.empty()
    
    while True:
        _, frame = cap.read()
        
        # Detect and decode QR code
        data, bbox, _ = detector.detectAndDecode(frame)
        
        # If QR code detected
        if bbox is not None:
            # Draw bounding box
            for i in range(len(bbox)):
                cv2.line(frame, 
                         tuple(map(int, bbox[i][0])), 
                         tuple(map(int, bbox[(i+1) % len(bbox)][0])), 
                         color=(255, 0, 0), 
                         thickness=2)
            
            if data:
                scanned_data = data
                cv2.putText(frame, "QR Code Detected!", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                break
        
        # Display webcam feed
        image_placeholder.image(frame, channels="BGR", use_column_width=True)
        
        # Add a small delay
        time.sleep(0.1)
    
    # Release webcam
    cap.release()
    image_placeholder.empty()
    
    return scanned_data

def qr_code_page():
    """Page for generating and scanning QR codes"""
    st.title("QR Code Attendance System")
    
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.warning("Please login first to access the QR code system")
        return
    
    tab1, tab2 = st.tabs(["Generate QR Code", "Scan QR Code"])
    
    with tab1:
        st.subheader("Generate Attendance QR Code")
        
        # Generate a unique session ID for this QR code
        session_id = f"ATT-SESSION-{get_ist_time().strftime('%Y%m%d%H%M%S')}"
        
        # Create QR code
        qr_img_path = generate_qr_code(session_id)
        
        # Display QR code
        st.image(qr_img_path, caption="Scan this QR code to mark attendance", use_column_width=True)
        
        # Add expiration time (5 minutes from now)
        expiry_time = (get_ist_time() + timedelta(minutes=5)).strftime("%H:%M:%S")
        st.info(f"This QR code will expire at {expiry_time} IST")
        
        # Store session ID in session state
        st.session_state.qr_session_id = session_id
        
    with tab2:
        st.subheader("Scan QR Code to Mark Attendance")
        
        if st.button("Start QR Code Scanner"):
            scanned_data = scan_qr_code()
            
            if scanned_data:
                st.success(f"QR Code scanned successfully!")
                
                # Verify the scanned code matches the current session
                if 'qr_session_id' in st.session_state and scanned_data == st.session_state.qr_session_id:
                    # Mark attendance
                    attendance_id, error = record_attendance(
                        st.session_state.employee_name,
                        "Present",
                        qr_scanned=True
                    )
                    
                    if error:
                        st.error(f"Failed to record attendance: {error}")
                    else:
                        st.success(f"Attendance recorded successfully! ID: {attendance_id}")
                        st.balloons()
                else:
                    st.error("Invalid or expired QR code. Please scan a valid code.")

def main():
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
                        st.error("Invalid credentials. Please try again.")
    else:
        st.title("Attendance Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("QR Code Attendance", use_container_width=True):
                st.session_state.selected_mode = "qr_code"
                st.rerun()
        
        with col2:
            if st.button("Manual Attendance", use_container_width=True):
                st.session_state.selected_mode = "manual"
                st.rerun()
        
        if st.button("Logout", key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.selected_mode = None
            st.rerun()
        
        if 'selected_mode' in st.session_state and st.session_state.selected_mode:
            if st.session_state.selected_mode == "qr_code":
                qr_code_page()
            elif st.session_state.selected_mode == "manual":
                manual_attendance_page()

def manual_attendance_page():
    st.title("Manual Attendance")
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
                        status,
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
