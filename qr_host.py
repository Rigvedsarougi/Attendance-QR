def attendance_page():
    st.title("Attendance Management")
    selected_employee = st.session_state.employee_name
    
    if check_existing_attendance(selected_employee):
        st.warning("You have already marked your attendance for today.")
        return
    
    current_time = get_ist_time().time()
    is_after_noon = current_time >= time(12, 0)  # 12:00 PM
    
    # If it's after 12 PM, force Half Day status
    if is_after_noon:
        st.warning("⚠️ It's after 12 PM - Attendance will be marked as Half Day")
        status = "Half Day"
    else:
        st.subheader("Attendance Status")
        status = st.radio("Select Status", ["Present", "Half Day", "Leave"], index=0, key="attendance_status")
    
    if status in ["Present", "Half Day"]:
        st.subheader("Location Verification")
        
        # Google Maps integration
        with st.expander("📍 Get My Location Automatically", expanded=True):
            if GOOGLE_MAPS_API_KEY:
                # HTML for Google Maps geolocation
                location_html = """
                <div id="location-container" style="margin-bottom: 20px;">
                    <button onclick="getLocation()" style="padding: 10px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Get My Current Location
                    </button>
                    <div id="location-result" style="margin-top: 10px;"></div>
                    <div id="map" style="height: 300px; width: 100%; margin-top: 10px; display: none;"></div>
                    <script>
                    function getLocation() {
                        if (navigator.geolocation) {
                            navigator.geolocation.getCurrentPosition(showPosition, showError);
                        } else { 
                            document.getElementById("location-result").innerHTML = "Geolocation is not supported by this browser.";
                        }
                    }
                    
                    function showPosition(position) {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;
                        
                        // Update Streamlit components
                        const latInput = document.getElementById("latitude");
                        const lngInput = document.getElementById("longitude");
                        const addressInput = document.getElementById("address");
                        
                        if (latInput) latInput.value = lat;
                        if (lngInput) lngInput.value = lng;
                        
                        // Reverse geocode to get address
                        fetch(`https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=%s`)
                            .then(response => response.json())
                            .then(data => {
                                if (data.results && data.results[0]) {
                                    const address = data.results[0].formatted_address;
                                    document.getElementById("location-result").innerHTML = 
                                        `<strong>Detected Location:</strong> ${address}`;
                                    if (addressInput) addressInput.value = address;
                                    
                                    // Show map
                                    const mapDiv = document.getElementById("map");
                                    mapDiv.style.display = "block";
                                    new google.maps.Map(mapDiv, {
                                        center: {lat: lat, lng: lng},
                                        zoom: 15,
                                        mapTypeId: 'roadmap'
                                    });
                                    
                                    // Add marker
                                    new google.maps.Marker({
                                        position: {lat: lat, lng: lng},
                                        map: mapDiv._map
                                    });
                                }
                            });
                    }
                    
                    function showError(error) {
                        let message = "Error getting location: ";
                        switch(error.code) {
                            case error.PERMISSION_DENIED:
                                message += "User denied the request for Geolocation.";
                                break;
                            case error.POSITION_UNAVAILABLE:
                                message += "Location information is unavailable.";
                                break;
                            case error.TIMEOUT:
                                message += "The request to get user location timed out.";
                                break;
                            case error.UNKNOWN_ERROR:
                                message += "An unknown error occurred.";
                                break;
                        }
                        document.getElementById("location-result").innerHTML = message;
                    }
                    </script>
                    <script src="https://maps.googleapis.com/maps/api/js?key=%s&callback=Function.prototype"></script>
                </div>
                """ % (GOOGLE_MAPS_API_KEY, GOOGLE_MAPS_API_KEY)
                
                st.components.v1.html(location_html, height=400)
            else:
                st.warning("Google Maps API key not configured. Location services limited.")
        
        # Hidden inputs to store location data
        latitude = st.text_input("Latitude", key="latitude", type="default", label_visibility="collapsed")
        longitude = st.text_input("Longitude", key="longitude", type="default", label_visibility="collapsed")
        address = st.text_area("Your Location", key="address", 
                             help="Verify or edit your detected location")
        
        # Manual location fallback
        st.markdown("---")
        st.markdown("**Alternatively, enter your location manually:**")
        manual_location = st.text_input("Enter your location", key="manual_location")
        
        if st.button("Mark Attendance", key="mark_attendance_button"):
            final_location = ""
            
            if latitude and longitude:
                # Use coordinates if available
                final_location = f"Coordinates: {latitude},{longitude}"
                if address:
                    final_location += f" | Address: {address}"
            elif manual_location:
                # Fallback to manual location
                final_location = f"Manual Entry: {manual_location}"
            else:
                st.error("Please provide your location")
                return
            
            with st.spinner("Recording attendance..."):
                attendance_id, error = record_attendance(
                    selected_employee,
                    status,
                    location_link=final_location
                )
                
                if error:
                    st.error(f"Failed to record attendance: {error}")
                else:
                    st.success(f"Attendance recorded successfully! ID: {attendance_id}")
                    if is_after_noon:
                        st.info("Automatically marked as Half Day because it's after 12 PM")
                    st.balloons()
    
    else:  # Leave status
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
