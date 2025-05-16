import streamlit as st
import qrcode
from datetime import datetime, timedelta
import pytz
import time

def get_ist_time():
    """Get current time in Indian Standard Time (IST)"""
    utc_now = datetime.now(pytz.utc)
    ist = pytz.timezone('Asia/Kolkata')
    return utc_now.astimezone(ist)

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

def main():
    st.set_page_config(page_title="Attendance QR Code Host", layout="centered")
    
    st.title("Live Attendance QR Code")
    
    # Generate a unique session ID for this QR code
    session_id = f"ATT-SESSION-{get_ist_time().strftime('%Y%m%d%H%M%S')}"
    
    # Create QR code
    qr_img_path = generate_qr_code(session_id)
    
    # Display QR code
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(qr_img_path, caption="Scan this QR code to mark attendance", use_column_width=True)
    
    # Add expiration time (5 minutes from now)
    expiry_time = (get_ist_time() + timedelta(minutes=5)).strftime("%H:%M:%S")
    st.info(f"This QR code will expire at {expiry_time} IST")
    
    # Auto-refresh every 30 seconds to show countdown
    refresh_time = 30  # seconds
    time_left = refresh_time
    
    placeholder = st.empty()
    
    while True:
        current_time = get_ist_time()
        if current_time >= (get_ist_time() + timedelta(minutes=5)):
            st.warning("QR Code has expired. Please refresh the page to generate a new one.")
            break
        
        mins, secs = divmod(time_left, 60)
        placeholder.markdown(f"Refreshing in: {mins:02d}:{secs:02d}")
        time.sleep(1)
        time_left -= 1
        
        if time_left <= 0:
            st.rerun()
            break

if __name__ == "__main__":
    main()
