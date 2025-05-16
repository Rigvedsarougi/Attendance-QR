# attendance.py
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
import os
import uuid
from datetime import datetime
import pytz
import cv2
from pyzbar.pyzbar import decode
import numpy as np
from PIL import Image

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

def generate_qr_code(employee_code):
    """Generate QR code for an employee"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(employee_code)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def save_qr_code(employee_code, employee_name):
    """Save QR code to file"""
    img = generate_qr_code(employee_code)
    os.makedirs("qrcodes", exist_ok=True)
    filename = f"qrcodes/{employee_name}_{employee_code}.png"
    img.save(filename)
    return filename

def check_existing_attendance(employee_code):
    """Check if attendance already marked for today"""
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        if existing_data.empty:
            return False
        
        current_date = get_ist_time().strftime("%d-%m-%Y")
        
        existing_records = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date)
        ]
        
        return not existing_records.empty
        
    except Exception as e:
        st.error(f"Error checking existing attendance: {str(e)}")
        return False

def record_attendance(employee_name, employee_code, designation, status, location_link="", leave_reason=""):
    """Record attendance to Google Sheets"""
    try:
        current_date = get_ist_time().strftime("%d-%m-%Y")
        current_datetime = get_ist_time().strftime("%d-%m-%Y %H:%M:%S")
        check_in_time = get_ist_time().strftime("%H:%M:%S")
        
        attendance_id = f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"
        
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
        
        attendance_df = pd.DataFrame([attendance_data], columns=ATTENDANCE_SHEET_COLUMNS)
        
        # Read existing data
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how='all')
        
        # Combine with new data
        updated_data = pd.concat([existing_data, attendance_df], ignore_index=True)
        
        # Write back to Google Sheets
        conn.update(worksheet="Attendance", data=updated_data)
        
        return attendance_id, None
    except Exception as e:
        return None, str(e)

def scan_qr_code():
    """Scan QR code using webcam"""
    st.write("Scan QR Code")
    
    # Start webcam
    cap = cv2.VideoCapture(0)
    FRAME_WINDOW = st.image([])
    
    scanned_data = None
    stop_scanning = st.button("Stop Scanning")
    
    while cap.isOpened() and not stop_scanning:
        ret, frame = cap.read()
        if not ret:
            continue
            
        # Convert frame to RGB for Streamlit
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        FRAME_WINDOW.image(frame_rgb)
        
        # Decode QR codes
        decoded_objects = decode(frame)
        for obj in decoded_objects:
            scanned_data = obj.data.decode('utf-8')
            break
            
        if scanned_data is not None:
            break
            
    cap.release()
    return scanned_data

def employee_view(employee_name, employee_code, designation):
    """View for employees to access their QR code"""
    st.title(f"Welcome, {employee_name}")
    st.subheader("Your Attendance QR Code")
    
    # Check if attendance already marked
    if check_existing_attendance(employee_code):
        st.warning("You have already marked your attendance for today.")
        return
    
    # Generate or load QR code
    qr_code_path = save_qr_code(employee_code, employee_name)
    st.image(qr_code_path, caption="Your unique attendance QR code", width=300)
    
    st.info("Show this QR code to the admin to mark your attendance")

def admin_view():
    """View for admin to scan QR codes"""
    st.title("Admin Attendance Portal")
    
    # Authentication
    admin_pass = st.text_input("Enter Admin Password", type="password")
    if admin_pass != "admin123":  # In production, use secure password handling
        st.warning("Please enter admin password to continue")
        return
    
    st.subheader("QR Code Scanner")
    
    scanned_data = scan_qr_code()
    
    if scanned_data:
        st.success(f"Scanned data: {scanned_data}")
        
        # Load employee data
        try:
            employee_data = conn.read(worksheet="Person", ttl=5)
            employee_data = employee_data.dropna(how='all')
            
            employee = employee_data[employee_data['Employee Code'] == scanned_data]
            
            if not employee.empty:
                employee_name = employee['Employee Name'].values[0]
                designation = employee['Designation'].values[0]
                
                # Check if already marked
                if check_existing_attendance(scanned_data):
                    st.warning(f"{employee_name}'s attendance already marked today")
                else:
                    # Mark attendance
                    attendance_id, error = record_attendance(
                        employee_name,
                        scanned_data,
                        designation,
                        "Present",
                        "Scanned via QR Code"
                    )
                    
                    if error:
                        st.error(f"Error marking attendance: {error}")
                    else:
                        st.success(f"Attendance marked for {employee_name} (ID: {attendance_id})")
                        st.balloons()
            else:
                st.error("Employee not found in database")
        except Exception as e:
            st.error(f"Error accessing employee data: {str(e)}")

def main():
    st.set_page_config(page_title="QR Attendance System", page_icon="📱")
    
    # Authentication - simple for demo (replace with proper auth in production)
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'employee_data' not in st.session_state:
        st.session_state.employee_data = None
    
    # Simple login for demo
    if not st.session_state.authenticated:
        st.title("QR Attendance System Login")
        
        login_type = st.radio("Login as:", ["Employee", "Admin"])
        
        if login_type == "Employee":
            employee_code = st.text_input("Enter your Employee Code")
            
            if st.button("Login"):
                try:
                    employee_data = conn.read(worksheet="Person", ttl=5)
                    employee_data = employee_data.dropna(how='all')
                    
                    employee = employee_data[employee_data['Employee Code'] == employee_code]
                    
                    if not employee.empty:
                        st.session_state.authenticated = True
                        st.session_state.employee_data = {
                            'name': employee['Employee Name'].values[0],
                            'code': employee_code,
                            'designation': employee['Designation'].values[0]
                        }
                        st.rerun()
                    else:
                        st.error("Invalid employee code")
                except Exception as e:
                    st.error(f"Error accessing employee data: {str(e)}")
        else:
            # Admin login
            admin_pass = st.text_input("Enter Admin Password", type="password")
            
            if st.button("Login as Admin"):
                if admin_pass == "admin123":  # In production, use secure password handling
                    st.session_state.authenticated = True
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Invalid admin password")
    else:
        # Logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.employee_data = None
            if 'is_admin' in st.session_state:
                del st.session_state.is_admin
            st.rerun()
        
        # Show appropriate view
        if 'is_admin' in st.session_state and st.session_state.is_admin:
            admin_view()
        elif st.session_state.employee_data:
            employee_view(
                st.session_state.employee_data['name'],
                st.session_state.employee_data['code'],
                st.session_state.employee_data['designation']
            )

if __name__ == "__main__":
    main()
