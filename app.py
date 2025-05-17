import streamlit as st
import pandas as pd
import datetime
import os
from PIL import Image
import time
import cv2
import numpy as np

# Initialize session state
if 'selected_mode' not in st.session_state:
    st.session_state.selected_mode = "Attendance"

# Helper functions
def add_back_button():
    if st.button("Back to Main Menu"):
        st.session_state.selected_mode = None
        st.rerun()

def initialize_attendance_data():
    if not os.path.exists('attendance.csv'):
        columns = [
            'Name', 'ID', 'Date', 'Check-in Time', 
            'Check-out Time', 'Check-in Date Time', 
            'Check-out Date Time', 'Status'
        ]
        pd.DataFrame(columns=columns).to_csv('attendance.csv', index=False)

def mark_attendance(user_id, check_type='in'):
    today = datetime.date.today().strftime('%d-%m-%Y')
    current_time = datetime.datetime.now().strftime('%H:%M:%S')
    current_datetime = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    existing_data = pd.read_csv('attendance.csv')
    
    # Ensure proper dtypes for time columns
    time_columns = ['Check-in Time', 'Check-out Time', 'Check-in Date Time', 'Check-out Date Time']
    for col in time_columns:
        if col in existing_data.columns:
            existing_data[col] = existing_data[col].astype(str)
    
    today_record_index = existing_data[
        (existing_data['ID'] == user_id) & 
        (existing_data['Date'] == today)
    ].index
    
    if check_type == 'in':
        if not today_record_index.empty:
            st.warning("You've already checked in today!")
            return False
        
        new_record = {
            'Name': "User Name",  # Replace with actual user name
            'ID': user_id,
            'Date': today,
            'Check-in Time': current_time,
            'Check-out Time': "",
            'Check-in Date Time': current_datetime,
            'Check-out Date Time': "",
            'Status': "Present"
        }
        existing_data = pd.concat([existing_data, pd.DataFrame([new_record])], ignore_index=True)
    else:
        if today_record_index.empty:
            st.error("No check-in found for today!")
            return False
        
        if pd.notna(existing_data.loc[today_record_index[0], 'Check-out Time']):
            st.warning("You've already checked out today!")
            return False
        
        existing_data.at[today_record_index[0], 'Check-out Time'] = current_time
        existing_data.at[today_record_index[0], 'Check-out Date Time'] = current_datetime
    
    existing_data.to_csv('attendance.csv', index=False)
    return True

def attendance_page():
    st.title("Attendance System")
    
    initialize_attendance_data()
    
    # QR Code Scanner Section
    st.header("Scan QR Code")
    captured_image = st.camera_input("Take a picture of your QR code")
    
    if captured_image is not None:
        # Process QR code (simplified - replace with actual QR decoding)
        try:
            # In a real app, you would decode the QR code here
            user_id = "12345"  # Replace with actual decoded ID
            st.success(f"Detected User ID: {user_id}")
            
            # Check if already checked in/out
            today = datetime.date.today().strftime('%d-%m-%Y')
            existing_data = pd.read_csv('attendance.csv')
            today_record = existing_data[
                (existing_data['ID'] == user_id) & 
                (existing_data['Date'] == today)
            ]
            
            if today_record.empty:
                if st.button("Check In"):
                    if mark_attendance(user_id, 'in'):
                        st.success("Checked in successfully!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
            else:
                if pd.isna(today_record.iloc[0]['Check-out Time']):
                    if st.button("Check Out"):
                        if mark_attendance(user_id, 'out'):
                            st.success("Checked out successfully!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                else:
                    st.info("You've already completed your attendance for today")
        except Exception as e:
            st.error(f"Error processing QR code: {e}")
    
    # Display today's attendance
    st.header("Today's Attendance")
    today = datetime.date.today().strftime('%d-%m-%Y')
    try:
        attendance_data = pd.read_csv('attendance.csv')
        today_data = attendance_data[attendance_data['Date'] == today]
        
        if not today_data.empty:
            # Format the display
            display_cols = ['Name', 'ID', 'Check-in Time', 'Check-out Time', 'Status']
            st.dataframe(today_data[display_cols])
            
            # Show summary stats
            checked_in = len(today_data)
            checked_out = len(today_data[pd.notna(today_data['Check-out Time'])])
            st.write(f"Total Checked In: {checked_in} | Total Checked Out: {checked_out}")
        else:
            st.info("No attendance records for today yet")
    except Exception as e:
        st.error(f"Error loading attendance data: {e}")

def resources_page():
    st.title("Resources")
    add_back_button()
    # Your resources page content here

def announcements_page():
    st.title("Announcements")
    add_back_button()
    # Your announcements page content here

def main():
    st.sidebar.title("Navigation")
    
    if st.session_state.selected_mode is None:
        st.title("Main Menu")
        st.write("Select an option from the sidebar")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Attendance"):
                st.session_state.selected_mode = "Attendance"
                st.rerun()
        with col2:
            if st.button("Resources"):
                st.session_state.selected_mode = "Resources"
                st.rerun()
        with col3:
            if st.button("Announcements"):
                st.session_state.selected_mode = "Announcements"
                st.rerun()
    else:
        add_back_button()
        
        if st.session_state.selected_mode == "Attendance":
            attendance_page()
        elif st.session_state.selected_mode == "Resources":
            resources_page()
        elif st.session_state.selected_mode == "Announcements":
            announcements_page()

if __name__ == "__main__":
    main()
