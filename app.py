# app.py
import streamlit as st

def main():
    st.set_page_config(page_title="Employee Portal", page_icon="🏢")
    
    st.title("Employee Portal")
    st.write("Please select the module you want to access:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Attendance System (QR Code)"):
            st.switch_page("attendance.py")
    
    with col2:
        if st.button("Main Employee Portal"):
            st.switch_page("main.py")

if __name__ == "__main__":
    main()
