import streamlit as st
from PIL import Image
from pyzbar.pyzbar import decode
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="QR/Barcode Scanner", layout="centered")
st.title("📷 QR/Barcode Scanner & Logger")

# 1) Initialize Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)
worksheet = st.secrets["connections"]["gsheets"]["worksheet"]  # set in ~/.streamlit/secrets.toml

# 2) Use camera to capture code
img_file = st.camera_input("Point your camera at the QR/Barcode")

if img_file:
    image = Image.open(img_file)
    decoded = decode(image)

    if decoded:
        raw = decoded[0].data.decode("utf-8")
        st.success(f"Decoded data:\n```\n{raw}\n```")

        # 3) Try parsing JSON payload
        try:
            import json
            record = json.loads(raw)
        except Exception:
            record = {"raw_data": raw}

        # Add scan timestamp
        record["scanned_at"] = datetime.now().isoformat()

        df = pd.DataFrame([record])
        st.dataframe(df)

        # 4) Append to Google Sheet
        try:
            conn.write(df, sheet=worksheet, include_index=False)
            st.success("✅ Logged to Google Sheet")
        except Exception as e:
            st.error(f"Failed to write to sheet: {e}")

    else:
        st.error("No QR/Barcode detected. Try again.")
else:
    st.info("Use your camera to scan a QR or barcode.")
