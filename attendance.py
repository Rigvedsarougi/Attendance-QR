# attendance.py
import streamlit as st
import qrcode
import os
import cv2
from pyzbar.pyzbar import decode
import numpy as np
from datetime import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Initialize Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Constants
ATTENDANCE_COLS = [
    "ID", "Employee Name", "Employee Code", 
    "Date", "Time", "Status", "Method"
]

# Helper functions
def get_current_datetime():
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def save_qr_code(emp_code, emp_name):
    os.makedirs("qrcodes", exist_ok=True)
    img = generate_qr_code(emp_code)
    path = f"qrcodes/{emp_name}_{emp_code}.png"
    img.save(path)
    return path

def scan_qr_code():
    st.write("Scanning QR Code...")
    cap = cv2.VideoCapture(0)
    frame_placeholder = st.empty()
    stop_button = st.button("Stop Scanning")
    
    scanned_data = None
    while cap.isOpened() and not stop_button:
        ret, frame = cap.read()
        if not ret:
            continue
        
        # Display frame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame)
        
        # Decode QR code
        decoded = decode(frame)
        if decoded:
            scanned_data = decoded[0].data.decode("utf-8")
            break
    
    cap.release()
    frame_placeholder.empty()
    return scanned_data

def mark_attendance(emp_code, method="QR Code"):
    try:
        # Get employee data
        emp_data = conn.read(worksheet="Employees", ttl=5)
        emp_data = emp_data.dropna(how="all")
        employee = emp_data[emp_data["Employee Code"] == emp_code]
        
        if employee.empty:
            return False, "Employee not found"
        
        # Check if already marked today
        date, time = get_current_datetime()
        attendance = conn.read(worksheet="Attendance", ttl=5)
        attendance = attendance.dropna(how="all")
        
        if not attendance.empty:
            today_attendance = attendance[
                (attendance["Employee Code"] == emp_code) & 
                (attendance["Date"] == date)
            ]
            if not today_attendance.empty:
                return False, "Attendance already marked today"
        
        # Record attendance
        new_record = pd.DataFrame([{
            "ID": f"ATT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "Employee Name": employee["Employee Name"].values[0],
            "Employee Code": emp_code,
            "Date": date,
            "Time": time,
            "Status": "Present",
            "Method": method
        }])
        
        # Update sheet
        updated = pd.concat([attendance, new_record], ignore_index=True)
        conn.update(worksheet="Attendance", data=updated)
        
        return True, "Attendance marked successfully"
    
    except Exception as e:
        return False, f"Error: {str(e)}"

# User View
def user_view(emp_code, emp_name):
    st.title(f"Welcome, {emp_name}")
    st.subheader("Your Attendance QR Code")
    
    # Generate/Show QR Code
    qr_path = save_qr_code(emp_code, emp_name)
    st.image(qr_path, caption="Scan this code with admin device", width=300)
    
    # Check today's attendance
    date, _ = get_current_datetime()
    attendance = conn.read(worksheet="Attendance", ttl=5)
    attendance = attendance.dropna(how="all")
    
    if not attendance.empty:
        today_attendance = attendance[
            (attendance["Employee Code"] == emp_code) & 
            (attendance["Date"] == date)
        ]
        if not today_attendance.empty:
            st.success("Your attendance is already marked for today")
            st.write(f"Time: {today_attendance['Time'].values[0]}")
        else:
            st.info("Your attendance is not marked yet for today")

# Admin View
def admin_view():
    st.title("Admin Attendance Portal")
    st.subheader("QR Code Scanner")
    
    scanned_data = scan_qr_code()
    
    if scanned_data:
        success, message = mark_attendance(scanned_data)
        if success:
            # Get employee name
            emp_data = conn.read(worksheet="Employees", ttl=5)
            emp_name = emp_data[emp_data["Employee Code"] == scanned_data]["Employee Name"].values[0]
            st.success(f"Attendance marked for {emp_name}")
            st.balloons()
        else:
            st.error(message)

# Main App
def main():
    st.set_page_config(page_title="Attendance System", page_icon="📱")
    
    # Simple authentication
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_type = None
        st.session_state.emp_code = None
        st.session_state.emp_name = None
    
    if not st.session_state.authenticated:
        st.title("Attendance System Login")
        
        login_type = st.radio("Login as:", ["Employee", "Admin"])
        
        if login_type == "Employee":
            emp_code = st.text_input("Enter Employee Code")
            
            if st.button("Login"):
                try:
                    emp_data = conn.read(worksheet="Employees", ttl=5)
                    emp_data = emp_data.dropna(how="all")
                    employee = emp_data[emp_data["Employee Code"] == emp_code]
                    
                    if not employee.empty:
                        st.session_state.authenticated = True
                        st.session_state.user_type = "employee"
                        st.session_state.emp_code = emp_code
                        st.session_state.emp_name = employee["Employee Name"].values[0]
                        st.rerun()
                    else:
                        st.error("Invalid employee code")
                except Exception as e:
                    st.error(f"Database error: {str(e)}")
        else:
            admin_pass = st.text_input("Admin Password", type="password")
            
            if st.button("Login as Admin"):
                if admin_pass == "admin123":  # Change to secure password in production
                    st.session_state.authenticated = True
                    st.session_state.user_type = "admin"
                    st.rerun()
                else:
                    st.error("Incorrect password")
    else:
        # Logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_type = None
            st.session_state.emp_code = None
            st.session_state.emp_name = None
            st.rerun()
        
        # Show appropriate view
        if st.session_state.user_type == "admin":
            admin_view()
        else:
            user_view(st.session_state.emp_code, st.session_state.emp_name)

if __name__ == "__main__":
    main()
