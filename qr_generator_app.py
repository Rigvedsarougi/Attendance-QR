# qr_generator_app.py

import streamlit as st
st.set_page_config(page_title="QR Generator", layout="centered")

from bokeh.models.widgets import Button
from bokeh.models import CustomJS
from streamlit_bokeh_events import streamlit_bokeh_events
import uuid
import qrcode
from io import BytesIO
import pytz
from datetime import datetime

st.title("🔍 QR Code Generator with Location")

# 1) Button to capture browser geolocation via JS
loc_button = Button(label="Get My Location")
loc_button.js_on_event(
    "button_click",
    CustomJS(code="""
        navigator.geolocation.getCurrentPosition(
            (loc) => {
                document.dispatchEvent(
                    new CustomEvent("GET_LOCATION", {
                        detail: {
                            lat: loc.coords.latitude,
                            lon: loc.coords.longitude
                        }
                    })
                )
            },
            (err) => {
                document.dispatchEvent(
                    new CustomEvent("GEO_ERROR", { detail: err.message })
                )
            }
        )
    """),
)

# 2) Listen for events
evt = streamlit_bokeh_events(
    loc_button,
    events=["GET_LOCATION", "GEO_ERROR"],
    key="geo",
    refresh_on_update=True,
    override_height=75,
    debounce_time=0,
)

if evt:
    # 3a) Error case
    if "GEO_ERROR" in evt:
        st.error(f"Error obtaining location: {evt['GEO_ERROR']['detail']}")
    # 3b) Success case
    elif "GET_LOCATION" in evt:
        lat = evt["GET_LOCATION"]["lat"]
        lon = evt["GET_LOCATION"]["lon"]
        st.success(f"Location captured: {lat:.6f}, {lon:.6f}")

        # 4) Generate a unique code
        unique_code = str(uuid.uuid4())
        st.write(f"🔑 **Your unique code:** `{unique_code}`")

        # 5) Bundle into a payload
        payload = {
            "code": unique_code,
            "latitude": lat,
            "longitude": lon,
            "timestamp": datetime.now(pytz.timezone("Asia/Kolkata")).isoformat()
        }

        # 6) Build the QR
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # 7) Display & let user download
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        st.image(buf, caption="📲 Scan this QR to read your code & location")
        st.download_button(
            "⬇️ Download QR Code",
            data=buf,
            file_name="my_qr_code.png",
            mime="image/png",
        )
else:
    st.info("Click **Get My Location** to generate your QR code.")
