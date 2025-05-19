import streamlit as st
from bokeh.models.widgets import Button
from bokeh.models import CustomJS
from streamlit_bokeh_events import streamlit_bokeh_events
import qrcode
from PIL import Image
import io


def main():
    # Set up page
    st.set_page_config(page_title="QR Generator", layout="centered")
    st.title("🔍 QR Code Generator with Location")

    # Create a button to fetch geolocation
    loc_button = Button(label="Get Current Location")
    loc_button.js_on_event("button_click", CustomJS(code="""
        navigator.geolocation.getCurrentPosition(
            (loc) => {
                document.dispatchEvent(new CustomEvent("GET_LOCATION", {
                    detail: {lat: loc.coords.latitude, lon: loc.coords.longitude}
                }))
            }
        )
        """))

    # Listen for the GET_LOCATION event
    result = streamlit_bokeh_events(
        loc_button,
        events="GET_LOCATION",
        key="get_location",
        refresh_on_update=False,
        override_height=75,
        debounce_time=0,
    )

    # When location is received, generate QR code
    if result and "GET_LOCATION" in result:
        loc_data = result["GET_LOCATION"]
        lat = loc_data.get('lat')
        lon = loc_data.get('lon')
        st.success(f"Location received: Latitude: {lat}, Longitude: {lon}")

        # Construct a Google Maps URL with the coordinates
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4
        )
        qr.add_data(maps_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Display the QR code
        st.image(img, caption="Scan to view location on map", use_column_width=True)

        # Prepare image for download
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        byte_im = buf.getvalue()

        # Download button
        st.download_button(
            label="Download QR code",
            data=byte_im,
            file_name="location_qr.png",
            mime="image/png"
        )


if __name__ == "__main__":
    main()
