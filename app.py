import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time
import os
import uuid
from PIL import Image
from datetime import datetime, time, timedelta
import pytz

import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pytz
import time
import pandas as pd



def log_location_history(conn, employee_name, lat, lng):
    employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
    designation = Person[Person['Employee Name'] == employee_name]['Designation'].values[0]
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    date_str = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%H:%M")
    gmaps_link = f"https://maps.google.com/?q={lat},{lng}"
    entry = {
        "Employee Name": employee_name,
        "Employee Code": employee_code,
        "Designation": designation,
        "Date": date_str,
        "Time": time_str,
        "Latitude": lat,
        "Longitude": lng,
        "Google Maps Link": gmaps_link
    }
    try:
        existing = conn.read(worksheet="LocationHistory", usecols=list(range(len(LOCATION_HISTORY_COLUMNS))), ttl=5)
        existing = existing.dropna(how="all")
        new_df = pd.DataFrame([entry], columns=LOCATION_HISTORY_COLUMNS)
        updated = pd.concat([existing, new_df], ignore_index=True)
        conn.update(worksheet="LocationHistory", data=updated)
        return True, None
    except Exception as e:
        return False, str(e)


def hourly_location_auto_log(conn, selected_employee):
    if not selected_employee:
        return
    result = streamlit_js_eval(
        js_expressions="""
            new Promise((resolve) => {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude, ts: Date.now()}),
                        err => resolve({latitude: null, longitude: null, ts: Date.now()})
                    );
                } else {
                    resolve({latitude: null, longitude: null, ts: Date.now()});
                }
            });
        """,
        key=f"geo_hourly_{int(time.time() // 3600)}"
    ) or {}

    lat = result.get("latitude")
    lng = result.get("longitude")

    if lat and lng:
        current_hour = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H")
        logged_key = f"hourly_logged_{selected_employee}_{current_hour}"
        if not st.session_state.get(logged_key, False):
            success, error = log_location_history(conn, selected_employee, lat, lng)
            if success:
                st.session_state[logged_key] = True

st.set_page_config(page_title="Location Logger", layout="centered")

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
            st.image(logo, use_container_width=True)
        except FileNotFoundError:
            st.warning("Logo image not found. Please ensure 'logo.png' exists in the same directory.")
        except Exception as e:
            st.warning(f"Could not load logo: {str(e)}")
        
        st.markdown("""
        <div style='text-align: center; margin-bottom: 30px;'>
            <h1 style='margin-bottom: 0;'>Employee Portal</h1>
            <h2 style='margin-top: 0; color: #555;'>Login</h2>
        </div>
        """, unsafe_allow_html=True)



hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stActionButton > button[title="Open source on GitHub"] {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

hide_footer_style = """
    <style>
    footer {
        visibility: hidden;
    }
    footer:after {
        content: '';
        display: none;
    }
    .css-15tx938.e8zbici2 {  /* This class targets the footer in some Streamlit builds */
        display: none !important;
    }
    </style>
"""

st.markdown(hide_footer_style, unsafe_allow_html=True)


def validate_data_before_write(df, expected_columns):
    """Validate data structure before writing to Google Sheets"""
    if not isinstance(df, pd.DataFrame):
        raise ValueError("Data must be a pandas DataFrame")
    
    missing_cols = set(expected_columns) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    if df.empty:
        raise ValueError("Cannot write empty dataframe")
    
    return True

def backup_sheet(conn, worksheet_name):
    """Create a timestamped backup of the worksheet"""
    try:
        data = conn.read(worksheet=worksheet_name, ttl=1)
        timestamp = get_ist_time().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{worksheet_name}_backup_{timestamp}"
        conn.update(worksheet=backup_name, data=data)
    except Exception as e:
        st.error(f"Warning: Failed to create backup - {str(e)}")

def attempt_data_recovery(conn, worksheet_name):
    """Attempt to recover from the most recent backup"""
    try:
        # Get list of all worksheets
        all_sheets = conn.list_worksheets()
        backups = [s for s in all_sheets if s.startswith(f"{worksheet_name}_backup")]
        
        if backups:
            # Sort backups by timestamp (newest first)
            backups.sort(reverse=True)
            latest_backup = backups[0]
            
            # Restore from backup
            backup_data = conn.read(worksheet=latest_backup)
            conn.update(worksheet=worksheet_name, data=backup_data)
            return True
        return False
    except Exception as e:
        st.error(f"Recovery failed: {str(e)}")
        return False

def safe_sheet_operation(operation, *args, **kwargs):
    """Wrapper for safe sheet operations with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"Operation failed after {max_retries} attempts: {str(e)}")
                if "Sales" in str(args) or "Visits" in str(args) or "Attendance" in str(args):
                    worksheet_name = [a for a in args if isinstance(a, str) and ("Sales" in a or "Visits" in a or "Attendance" in a)][0]
                    if attempt_data_recovery(conn, worksheet_name):
                        st.success("Data recovery attempted from backup")
                raise
            time.sleep(1 * (attempt + 1))  # Exponential backoff

# Constants
SALES_SHEET_COLUMNS = [
    "Invoice Number",
    "Invoice Date",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Discount Category",
    "Transaction Type",
    "Outlet Name",
    "Outlet Contact",
    "Outlet Address",
    "Outlet State",
    "Outlet City",
    "Distributor Firm Name",
    "Distributor ID",
    "Distributor Contact Person",
    "Distributor Contact Number",
    "Distributor Email",
    "Distributor Territory",
    "Product ID",
    "Product Name",
    "Product Category",
    "Quantity",
    "Unit Price",
    "Product Discount (%)",
    "Discounted Unit Price",
    "Total Price",
    "GST Rate",
    "CGST Amount",
    "SGST Amount",
    "Grand Total",
    "Overall Discount (%)",
    "Amount Discount (INR)",
    "Payment Status",
    "Amount Paid",
    "Payment Receipt Path",
    "Employee Selfie Path",
    "Invoice PDF Path",
    "Remarks",
    "Delivery Status"  # Added new column for delivery status
]

LOCATION_HISTORY_COLUMNS = [
    "Employee Name",
    "Employee Code",
    "Designation",
    "Date",
    "Time",
    "Latitude",
    "Longitude",
    "Google Maps Link"
]

VISIT_SHEET_COLUMNS = [
    "Visit ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Outlet Name",
    "Outlet Contact",
    "Outlet Address",
    "Outlet State",
    "Outlet City",
    "Visit Date",
    "Entry Time",
    "Exit Time",
    "Visit Duration (minutes)",
    "Visit Purpose",
    "Visit Notes",
    "Visit Selfie Path",
    "Visit Status",
    "Remarks"
]

ATTENDANCE_SHEET_COLUMNS = [
    "Attendance ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Date",
    "Status",
    "Check-in Location Link",
    "Check-out Location Link",
    "Leave Reason",
    "Check-in Time",
    "Check-out Time",
    "Duration (hours)",
    "Check-in Date Time"
]

# Add these constants at the top of app.py with other constants
TICKET_SHEET_COLUMNS = [
    "Ticket ID",
    "Raised By (Employee Name)",
    "Raised By (Employee Code)",
    "Raised By (Designation)",
    "Raised By (Email)",
    "Raised By (Phone)",
    "Category",
    "Subject",
    "Details",
    "Status",
    "Date Raised",
    "Time Raised",
    "Resolution Notes",
    "Date Resolved",
    "Priority"
]

TRAVEL_HOTEL_COLUMNS = [
    "Request ID",
    "Request Type",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Email",
    "Phone",
    "Adhara Number",
    "Hotel Name",
    "Check In Date",
    "Check Out Date",
    "Travel Mode",
    "From Location",
    "To Location",
    "Booking Date",
    "Remarks",
    "Status",
    "Date Requested",
    "Time Requested"
]

DEMO_SHEET_COLUMNS = [
    "Demo ID",
    "Employee Name",
    "Employee Code",
    "Designation",
    "Partner Employee",
    "Partner Employee Code",
    "Outlet Name",
    "Outlet Contact",
    "Outlet Address",
    "Outlet State",
    "Outlet City",
    "Demo Date",
    "Check-in Time",
    "Check-out Time",
    "Check-in Date Time",
    "Duration (minutes)",
    "Outlet Review",
    "Remarks",
    "Status",
    "Products",
    "Quantities"
]


TICKET_CATEGORIES = [
    "HR Department",
    "MIS & Back Office",
    "Digital & Marketing",
    "Co-founders",
    "Accounts",
    "Admin Department",
    "Travel Issue",
    "Product - Delivery/Quantity/Quality/Missing",
    "Others"
]

PRIORITY_LEVELS = ["Low", "Medium", "High", "Critical"]
TRAVEL_MODES = ["Bus", "Train", "Flight", "Taxi", "Other"]
REQUEST_TYPES = ["Hotel", "Travel", "Travel & Hotel"]

# Establishing a Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Load data
Products = pd.read_csv('Invoice - Products.csv')
Outlet = pd.read_csv('Invoice - Outlet.csv')
Person = pd.read_csv('Invoice - Person.csv')
Distributors = pd.read_csv('Invoice - Distributors.csv')

# Company Details with ALLGEN TRADING logo
company_name = "BIOLUME SKIN SCIENCE PRIVATE LIMITED"
company_address = """Ground Floor Rampal Awana Complex,
Rampal Awana Complex, Indra Market,
Sector-27, Atta, Noida, Gautam Buddha Nagar,
Uttar Pradesh 201301
GSTIN/UIN: 09AALCB9426H1ZA
State Name: Uttar Pradesh, Code: 09
"""
company_logo = 'ALLGEN TRADING logo.png'
bank_details = """
Disclaimer: This Proforma Invoice is for estimation purposes only and is not a demand for payment. 
Prices, taxes, and availability are subject to change. Final billing may vary. 
Goods/services will be delivered only after confirmation and payment. No legal obligation is created by this document.
"""

# Create directories for storing uploads
os.makedirs("employee_selfies", exist_ok=True)
os.makedirs("payment_receipts", exist_ok=True)
os.makedirs("invoices", exist_ok=True)
os.makedirs("visit_selfies", exist_ok=True)

# Custom PDF class
class PDF(FPDF):
    def header(self):
        if company_logo:
            try:
                self.image(company_logo, 10, 8, 33)
            except:
                pass
        
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, company_name, ln=True, align='C')
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, company_address, align='C')
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Proforma Invoice', ln=True, align='C')
        self.line(10, 50, 200, 50)
        self.ln(1)

def generate_invoice_number():
    return f"INV-{get_ist_time().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

def generate_visit_id():
    return f"VISIT-{get_ist_time().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

def generate_attendance_id():
    return f"ATT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def generate_ticket_id():
    return f"TKT-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def generate_request_id():
    return f"REQ-{get_ist_time().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def save_uploaded_file(uploaded_file, folder):
    if uploaded_file is not None:
        file_ext = os.path.splitext(uploaded_file.name)[1]
        file_path = os.path.join(folder, f"{str(uuid.uuid4())}{file_ext}")
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None


def demo_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Demo Management")
    selected_employee = st.session_state.employee_name

    tab1, tab2 = st.tabs(["New Demo", "Demo History"])

    # --- New Demo Tab ---
    with tab1:
        st.subheader("Partner Employee")
        partner_employee = st.selectbox(
            "Select Partner Employee",
            [n for n in Person['Employee Name'] if n != selected_employee],
            key="partner_employee"
        )

        st.subheader("Outlet Details")
        outlet_option = st.radio("Outlet Selection", ["Enter manually", "Select from list"], key="demo_outlet_option")
        if outlet_option == "Select from list":
            outlet_names = Outlet['Shop Name'].tolist()
            selected_outlet = st.selectbox("Select Outlet", outlet_names, key="demo_outlet_select")
            od = Outlet[Outlet['Shop Name'] == selected_outlet].iloc[0]
            outlet_name, outlet_contact = selected_outlet, od['Contact']
            outlet_address, outlet_state, outlet_city = od['Address'], od['State'], od['City']
            st.text_input("Contact", value=outlet_contact, disabled=True, key="demo_outlet_contact_display")
            st.text_input("Address", value=outlet_address, disabled=True, key="demo_outlet_address_display")
            st.text_input("State", value=outlet_state, disabled=True, key="demo_outlet_state_display")
            st.text_input("City", value=outlet_city, disabled=True, key="demo_outlet_city_display")
        else:
            outlet_name    = st.text_input("Outlet Name", key="demo_outlet_name")
            outlet_contact = st.text_input("Outlet Contact", key="demo_outlet_contact")
            outlet_address = st.text_area("Outlet Address", key="demo_outlet_address")
            outlet_state   = st.text_input("Outlet State", "", key="demo_outlet_state")
            outlet_city    = st.text_input("Outlet City", "", key="demo_outlet_city")

        st.subheader("Demo Details")
        demo_date     = st.date_input("Demo Date", key="demo_date")
        outlet_review = st.selectbox("Outlet Review", ["Excellent", "Good", "Average", "Poor"], key="outlet_review")
        remarks       = st.text_area("Remarks", key="demo_remarks")

        st.subheader("Time Tracking")
        col1, col2 = st.columns(2)
        with col1:
            check_in_time = st.time_input("Check-in Time", value=None, key="demo_check_in_time")
        with col2:
            check_out_time = st.time_input("Check-out Time", value=None, key="demo_check_out_time")

        st.subheader("Products Demonstrated")
        product_names      = Products['Product Name'].tolist()
        selected_products  = st.multiselect("Select Products Demonstrated", product_names, key="demo_product_selection")
        quantities         = []
        if selected_products:
            st.markdown("### Product Quantities")
            for i, prod in enumerate(selected_products):
                qty = st.number_input(f"Qty for {prod}", min_value=1, value=1, step=1, key=f"demo_qty_{i}")
                quantities.append(str(qty))

        if st.button("Record Demo", key="record_demo_button"):
            if outlet_name and selected_products:
                now = get_ist_time()
                # fallback to now if times are None
                if check_in_time  is None: check_in_time  = now.time()
                if check_out_time is None: check_out_time = now.time()
                ci = datetime.combine(demo_date, check_in_time)
                co = datetime.combine(demo_date, check_out_time)
                duration = (co - ci).total_seconds() / 60.0
                demo_id  = f"DEMO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

                demo_data = {
                    "Demo ID": demo_id,
                    "Employee Name": selected_employee,
                    "Employee Code": Person.loc[Person['Employee Name']==selected_employee,'Employee Code'].iat[0],
                    "Designation": Person.loc[Person['Employee Name']==selected_employee,'Designation'].iat[0],
                    "Partner Employee": partner_employee,
                    "Partner Employee Code": Person.loc[Person['Employee Name']==partner_employee,'Employee Code'].iat[0],
                    "Outlet Name": outlet_name,
                    "Outlet Contact": outlet_contact,
                    "Outlet Address": outlet_address,
                    "Outlet State": outlet_state,
                    "Outlet City": outlet_city,
                    "Demo Date": demo_date.strftime("%d-%m-%Y"),
                    "Check-in Time": ci.strftime("%H:%M:%S"),
                    "Check-out Time": co.strftime("%H:%M:%S"),
                    "Check-in Date Time": now.strftime("%d-%m-%Y %H:%M:%S"),
                    "Duration (minutes)": round(duration, 2),
                    "Outlet Review": outlet_review,
                    "Remarks": remarks,
                    "Status": "Completed",
                    "Products": "|".join(selected_products),
                    "Quantities": "|".join(quantities)
                }

                try:
                    existing = conn.read(worksheet="Demos", usecols=list(range(len(DEMO_SHEET_COLUMNS))), ttl=5).dropna(how="all")
                    df_new   = pd.DataFrame([demo_data], columns=DEMO_SHEET_COLUMNS)
                    conn.update(worksheet="Demos", data=pd.concat([existing, df_new], ignore_index=True))
                    st.success(f"Demo {demo_id} recorded successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Failed to record demo: {e}")
            else:
                st.error("Please fill all required fields (Outlet + ≥1 product).")

    # --- Demo History Tab ---
    with tab2:
        st.subheader("Demo History")

        @st.cache_data(ttl=300)
        def load_demo_data():
            try:
                df = conn.read(worksheet="Demos", usecols=list(range(len(DEMO_SHEET_COLUMNS))), ttl=5)
                df = df.dropna(how="all")
                # parse dates & cast duration to float
                df['Demo Date']         = pd.to_datetime(df['Demo Date'], dayfirst=True, errors='coerce')
                df['Duration (minutes)']= pd.to_numeric(df['Duration (minutes)'], errors='coerce')
                code = Person.loc[Person['Employee Name']==selected_employee,'Employee Code'].iat[0]
                return df[df['Employee Code']==code].sort_values('Demo Date', ascending=False)
            except Exception as e:
                st.error(f"Error loading demo data: {e}")
                return pd.DataFrame()

        demo_data = load_demo_data()
        if demo_data.empty:
            st.warning("No demo records found for your account")
            return

        # Filters
        with st.expander("🔍 Search Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                fid = st.text_input("Demo ID", key="demo_id_search")
            with c2:
                fdate = st.date_input("Demo Date", key="demo_date_search")
            with c3:
                fout = st.text_input("Outlet Name", key="demo_outlet_search")
            if st.button("Apply Filters", key="search_demo_button"):
                st.rerun()

        filtered = demo_data.copy()
        if fid:  filtered = filtered[filtered['Demo ID'].str.contains(fid, case=False, na=False)]
        if fdate:
            ds = fdate.strftime("%d-%m-%Y")
            filtered = filtered[filtered['Demo Date'].dt.strftime('%d-%m-%Y') == ds]
        if fout: filtered = filtered[filtered['Outlet Name'].str.contains(fout, case=False, na=False)]

        if filtered.empty:
            st.warning("No matching records found")
            return

        st.write(f"📄 Showing {len(filtered)} of your demos")
        summary_cols = [
            'Demo ID','Demo Date','Outlet Name','Partner Employee',
            'Check-in Time','Check-out Time','Duration (minutes)','Outlet Review'
        ]
        st.dataframe(
            filtered[summary_cols],
            column_config={"Demo Date": st.column_config.DateColumn(format="DD/MM/YYYY")},
            use_container_width=True,
            hide_index=True
        )

        sel = st.selectbox("Select demo to view details", filtered['Demo ID'], key="demo_selection")
        details = filtered[filtered['Demo ID']==sel].iloc[0]

        st.subheader(f"Demo {sel} Details")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Date", details['Demo Date'].strftime('%d-%m-%Y'))
            st.metric("Outlet", details['Outlet Name'])
            st.metric("Contact", details['Outlet Contact'])
            st.metric("Partner", details['Partner Employee'])
        with col2:
            st.metric("Check-in", details['Check-in Time'])
            st.metric("Check-out", details['Check-out Time'])
            st.metric("Duration", f"{details['Duration (minutes)']:.1f} minutes")
            st.metric("Review", details['Outlet Review'])

        st.subheader("Products Demonstrated")
        prod_str = str(details.get('Products',''))
        qty_str  = str(details.get('Quantities',''))
        prods = prod_str.split("|") if prod_str else []
        qtys  = qty_str.split("|")  if qty_str  else []
        # pad lists
        L = max(len(prods), len(qtys))
        prods += [""]*(L-len(prods))
        qtys  += [""]*(L-len(qtys))
        df_pd = pd.DataFrame({"Product": prods, "Quantity": qtys})
        st.dataframe(df_pd, use_container_width=True, hide_index=True)

        st.subheader("Remarks")
        st.write(details['Remarks'])

        csv = filtered.to_csv(index=False).encode('utf-8')
        st.download_button("Download Demo History", csv, "demo_history.csv", "text/csv", key='download-demo-csv')


def support_ticket_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Support Ticket Management")
    selected_employee = st.session_state.employee_name
    employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
    designation = Person[Person['Employee Name'] == selected_employee]['Designation'].values[0]
    
    tab1, tab2 = st.tabs(["Raise New Ticket", "My Support Requests"])
    
    with tab1:
        st.subheader("Raise New Support Ticket")
        with st.form("ticket_form"):
            # Employee contact info
            col1, col2 = st.columns(2)
            with col1:
                employee_email = st.text_input(
                    "Your Email*",
                    placeholder="your.email@company.com",
                    help="Please provide your contact email"
                )
            with col2:
                employee_phone = st.text_input(
                    "Your Phone Number*",
                    placeholder="9876543210",
                    help="Please provide your contact number"
                )
            
            # Ticket details
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox(
                    "Department",
                    TICKET_CATEGORIES,
                    help="Select the most relevant category for your ticket"
                )
            with col2:
                priority = st.selectbox(
                    "Priority*",
                    PRIORITY_LEVELS,
                    index=1,  # Default to Medium
                    help="How urgent is this issue?"
                )
            
            subject = st.text_input(
                "Subject*",
                max_chars=100,
                placeholder="Brief description of your ticket",
                help="Keep it concise but descriptive"
            )
            
            details = st.text_area(
                "Details*",
                height=200,
                placeholder="Please provide detailed information about your ticket...",
                help="Include all relevant details to help resolve your issue quickly"
            )
            
            st.markdown("<small>*Required fields</small>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Submit Ticket")
            
            if submitted:
                if not subject or not details or not employee_email or not employee_phone:
                    st.error("Please fill in all required fields (marked with *)")
                elif not employee_email.strip() or "@" not in employee_email:
                    st.error("Please enter a valid email address")
                elif not employee_phone.strip().isdigit() or len(employee_phone.strip()) < 10:
                    st.error("Please enter a valid 10-digit phone number")
                else:
                    with st.spinner("Submitting your ticket..."):
                        ticket_id = generate_ticket_id()
                        current_date = get_ist_time().strftime("%d-%m-%Y")
                        current_time = get_ist_time().strftime("%H:%M:%S")
                        
                        ticket_data = {
                            "Ticket ID": ticket_id,
                            "Raised By (Employee Name)": selected_employee,
                            "Raised By (Employee Code)": employee_code,
                            "Raised By (Designation)": designation,
                            "Raised By (Email)": employee_email.strip(),
                            "Raised By (Phone)": employee_phone.strip(),
                            "Category": category,
                            "Subject": subject,
                            "Details": details,
                            "Status": "Open",
                            "Date Raised": current_date,
                            "Time Raised": current_time,
                            "Resolution Notes": "",
                            "Date Resolved": "",
                            "Priority": priority
                        }
                        
                        ticket_df = pd.DataFrame([ticket_data])
                        success, error = log_ticket_to_gsheet(conn, ticket_df)
                        
                        if success:
                            st.success(f"""
                            Your ticket has been submitted successfully! 
                            We will update you within 48 hours regarding this matter.
                            
                            **Ticket ID:** {ticket_id}
                            **Priority:** {priority}
                            """)
                            st.balloons()
                        else:
                            st.error(f"Failed to submit ticket: {error}")
    
    with tab2:
        st.subheader("My Support Tickets")
        try:
            tickets_data = conn.read(worksheet="Tickets", usecols=list(range(len(TICKET_SHEET_COLUMNS))), ttl=5)
            tickets_data = tickets_data.dropna(how="all")
            
            if not tickets_data.empty:
                my_tickets = tickets_data[
                    tickets_data['Raised By (Employee Name)'] == selected_employee
                ].sort_values(by="Date Raised", ascending=False)
                
                if not my_tickets.empty:
                    pending_count = len(my_tickets[my_tickets['Status'] == "Open"])
                    resolved_count = len(my_tickets[my_tickets['Status'] == "Resolved"])
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Tickets", len(my_tickets))
                    col2.metric("Open", pending_count)
                    col3.metric("Resolved", resolved_count)
                    
                    st.subheader("Filter Tickets")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        status_filter = st.selectbox(
                            "Status",
                            ["All", "Open", "Resolved"],
                            key="status_filter"
                        )
                    with col2:
                        priority_filter = st.selectbox(
                            "Priority",
                            ["All"] + PRIORITY_LEVELS,
                            key="priority_filter"
                        )
                    with col3:
                        category_filter = st.selectbox(
                            "Category",
                            ["All"] + TICKET_CATEGORIES,
                            key="category_filter"
                        )
                    
                    filtered_tickets = my_tickets.copy()
                    if status_filter != "All":
                        filtered_tickets = filtered_tickets[filtered_tickets['Status'] == status_filter]
                    if priority_filter != "All":
                        filtered_tickets = filtered_tickets[filtered_tickets['Priority'] == priority_filter]
                    if category_filter != "All":
                        filtered_tickets = filtered_tickets[filtered_tickets['Category'] == category_filter]
                    
                    for _, row in filtered_tickets.iterrows():
                        with st.expander(f"{row['Subject']} - {row['Status']} ({row['Priority']})"):
                            status_color = "red" if row['Status'] == "Open" else "green"
                            st.markdown(f"""
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>Ticket ID:</strong> {row['Ticket ID']}<br>
                                    <strong>Date Raised:</strong> {row['Date Raised']} at {row['Time Raised']}
                                </div>
                                <div style="color: {status_color}; font-weight: bold;">
                                    {row['Status']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.write("---")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Your Contact Email:** {row['Raised By (Email)']}")
                                st.write(f"**Your Phone Number:** {row['Raised By (Phone)']}")
                                st.write(f"**Category:** {row['Category']}")
                            with col2:
                                st.write(f"**Priority:** {row['Priority']}")
                                if row['Date Resolved']:
                                    st.write(f"**Date Resolved:** {row['Date Resolved']}")
                            
                            st.write("---")
                            st.write("**Details:**")
                            st.write(row['Details'])
                            
                            if row['Status'] == "Resolved" and row['Resolution Notes']:
                                st.write("---")
                                st.write("**Resolution Notes:**")
                                st.write(row['Resolution Notes'])
                    
                    if not filtered_tickets.empty:
                        csv = filtered_tickets.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Download Tickets",
                            csv,
                            "my_support_tickets.csv",
                            "text/csv",
                            key='download-tickets-csv'
                        )
                else:
                    st.info("You haven't raised any support tickets yet.")
            else:
                st.info("No support tickets found in the system.")
                
        except Exception as e:
            st.error(f"Error retrieving support tickets: {str(e)}")

def travel_hotel_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Travel & Hotel Booking")
    selected_employee = st.session_state.employee_name
    employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
    designation = Person[Person['Employee Name'] == selected_employee]['Designation'].values[0]
    
    tab1, tab2, tab3 = st.tabs(["Travel Request", "Hotel Booking Request", "My Booking Requests"])
    
    with tab1:
        st.subheader("New Travel Request")
        with st.form("travel_form"):
            # Employee contact info
            col1, col2 = st.columns(2)
            with col1:
                employee_email = st.text_input(
                    "Your Email*",
                    value=st.session_state.get('employee_email', ''),
                    placeholder="your.email@company.com",
                    help="Please provide your contact email"
                )
            with col2:
                employee_phone = st.text_input(
                    "Your Phone Number*",
                    value=st.session_state.get('employee_phone', ''),
                    placeholder="9876543210",
                    help="Please provide your contact number"
                )
            
            adhara_number = st.text_input(
                "Aadhaar Number*",
                placeholder="Enter your Aadhaar number",
                help="Required for travel bookings"
            )
            
            # Travel details
            travel_mode = st.selectbox("Travel Mode*", TRAVEL_MODES)
            booking_date = st.date_input("Booking Date*", min_value=datetime.now().date())
            
            col1, col2 = st.columns(2)
            with col1:
                from_location = st.text_input("From*", placeholder="Starting location")
            with col2:
                to_location = st.text_input("To*", placeholder="Destination")
            
            remarks = st.text_area(
                "Remarks",
                placeholder="Any special requirements or additional information...",
                height=100
            )
            
            st.markdown("<small>*Required fields</small>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Submit Travel Request")
            
            if submitted:
                if not employee_email or not employee_phone or not adhara_number or not travel_mode or not from_location or not to_location or not booking_date:
                    st.error("Please fill in all required fields (marked with *)")
                elif not employee_email.strip() or "@" not in employee_email:
                    st.error("Please enter a valid email address")
                elif not employee_phone.strip().isdigit() or len(employee_phone.strip()) < 10:
                    st.error("Please enter a valid 10-digit phone number")
                else:
                    with st.spinner("Submitting your travel request..."):
                        request_id = generate_request_id()
                        current_date = get_ist_time().strftime("%d-%m-%Y")
                        current_time = get_ist_time().strftime("%H:%M:%S")
                        
                        request_data = {
                            "Request ID": request_id,
                            "Request Type": "Travel",
                            "Employee Name": selected_employee,
                            "Employee Code": employee_code,
                            "Designation": designation,
                            "Email": employee_email.strip(),
                            "Phone": employee_phone.strip(),
                            "Adhara Number": adhara_number.strip(),
                            "Hotel Name": "",
                            "Check In Date": "",
                            "Check Out Date": "",
                            "Travel Mode": travel_mode,
                            "From Location": from_location,
                            "To Location": to_location,
                            "Booking Date": booking_date.strftime("%d-%m-%Y"),
                            "Remarks": remarks,
                            "Status": "Pending",
                            "Date Requested": current_date,
                            "Time Requested": current_time
                        }
                        
                        request_df = pd.DataFrame([request_data])
                        success, error = log_travel_hotel_request(conn, request_df)
                        
                        if success:
                            st.session_state.employee_email = employee_email.strip()
                            st.session_state.employee_phone = employee_phone.strip()
                            st.success(f"""
                            Your travel request has been submitted successfully! 
                            **Request ID:** {request_id}
                            """)
                            st.balloons()
                        else:
                            st.error(f"Failed to submit request: {error}")
    
    with tab2:
        st.subheader("Hotel Booking Request")
        with st.form("hotel_form"):
            # Employee contact info
            col1, col2 = st.columns(2)
            with col1:
                employee_email = st.text_input(
                    "Your Email*",
                    value=st.session_state.get('employee_email', ''),
                    placeholder="your.email@company.com",
                    help="Please provide your contact email"
                )
            with col2:
                employee_phone = st.text_input(
                    "Your Phone Number*",
                    value=st.session_state.get('employee_phone', ''),
                    placeholder="9876543210",
                    help="Please provide your contact number"
                )
            
            adhara_number = st.text_input(
                "Aadhaar Number*",
                placeholder="Enter your Aadhaar number",
                help="Required for hotel bookings"
            )
            
            hotel_name = st.text_input("Hotel Name*")
            col1, col2 = st.columns(2)
            with col1:
                check_in_date = st.date_input("Check In Date*", min_value=datetime.now().date())
            with col2:
                check_out_date = st.date_input("Check Out Date*", min_value=datetime.now().date())
            
            remarks = st.text_area(
                "Remarks",
                placeholder="Any special requirements or additional information...",
                height=100
            )
            
            st.markdown("<small>*Required fields</small>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Submit Hotel Booking Request")
            
            if submitted:
                if not employee_email or not employee_phone or not adhara_number or not hotel_name or not check_in_date or not check_out_date:
                    st.error("Please fill in all required fields (marked with *)")
                elif not employee_email.strip() or "@" not in employee_email:
                    st.error("Please enter a valid email address")
                elif not employee_phone.strip().isdigit() or len(employee_phone.strip()) < 10:
                    st.error("Please enter a valid 10-digit phone number")
                else:
                    with st.spinner("Submitting your hotel booking request..."):
                        request_id = generate_request_id()
                        current_date = get_ist_time().strftime("%d-%m-%Y")
                        current_time = get_ist_time().strftime("%H:%M:%S")
                        
                        request_data = {
                            "Request ID": request_id,
                            "Request Type": "Hotel",
                            "Employee Name": selected_employee,
                            "Employee Code": employee_code,
                            "Designation": designation,
                            "Email": employee_email.strip(),
                            "Phone": employee_phone.strip(),
                            "Adhara Number": adhara_number.strip(),
                            "Hotel Name": hotel_name,
                            "Check In Date": check_in_date.strftime("%d-%m-%Y"),
                            "Check Out Date": check_out_date.strftime("%d-%m-%Y"),
                            "Travel Mode": "",
                            "From Location": "",
                            "To Location": "",
                            "Booking Date": "",
                            "Remarks": remarks,
                            "Status": "Pending",
                            "Date Requested": current_date,
                            "Time Requested": current_time
                        }
                        
                        request_df = pd.DataFrame([request_data])
                        success, error = log_travel_hotel_request(conn, request_df)
                        
                        if success:
                            st.session_state.employee_email = employee_email.strip()
                            st.session_state.employee_phone = employee_phone.strip()
                            st.success(f"""
                            Your hotel booking request has been submitted successfully! 
                            **Request ID:** {request_id}
                            """)
                            st.balloons()
                        else:
                            st.error(f"Failed to submit request: {error}")
    
    with tab3:
        st.subheader("My Travel & Hotel Requests")
        try:
            requests_data = conn.read(worksheet="TravelHotelRequests", usecols=list(range(len(TRAVEL_HOTEL_COLUMNS))), ttl=5)
            requests_data = requests_data.dropna(how="all")
            
            if not requests_data.empty:
                my_requests = requests_data[
                    requests_data['Employee Name'] == selected_employee
                ].sort_values(by="Date Requested", ascending=False)
                
                if not my_requests.empty:
                    pending_count = len(my_requests[my_requests['Status'] == "Pending"])
                    approved_count = len(my_requests[my_requests['Status'] == "Approved"])
                    rejected_count = len(my_requests[my_requests['Status'] == "Rejected"])
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Requests", len(my_requests))
                    col2.metric("Pending", pending_count)
                    col3.metric("Approved", approved_count)
                    
                    st.subheader("Filter Requests")
                    col1, col2 = st.columns(2)
                    with col1:
                        status_filter = st.selectbox(
                            "Status",
                            ["All", "Pending", "Approved", "Rejected"],
                            key="request_status_filter"
                        )
                    with col2:
                        type_filter = st.selectbox(
                            "Request Type",
                            ["All"] + REQUEST_TYPES,
                            key="request_type_filter"
                        )
                    
                    filtered_requests = my_requests.copy()
                    if status_filter != "All":
                        filtered_requests = filtered_requests[filtered_requests['Status'] == status_filter]
                    if type_filter != "All":
                        filtered_requests = filtered_requests[filtered_requests['Request Type'] == type_filter]
                    
                    for _, row in filtered_requests.iterrows():
                        with st.expander(f"{row['Request Type']} - {row['Status']}"):
                            status_color = "orange" if row['Status'] == "Pending" else "green" if row['Status'] == "Approved" else "red"
                            st.markdown(f"""
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>Request ID:</strong> {row['Request ID']}<br>
                                    <strong>Date Requested:</strong> {row['Date Requested']} at {row['Time Requested']}
                                </div>
                                <div style="color: {status_color}; font-weight: bold;">
                                    {row['Status']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.write("---")
                            st.write(f"**Your Contact Email:** {row['Email']}")
                            st.write(f"**Your Phone Number:** {row['Phone']}")
                            st.write(f"**Adhara Number:** {row['Adhara Number']}")
                            
                            if row['Request Type'] in ["Hotel", "Travel & Hotel"]:
                                st.write("---")
                                st.write("**Hotel Details:**")
                                st.write(f"**Hotel Name:** {row['Hotel Name']}")
                                st.write(f"**Check In Date:** {row['Check In Date']}")
                                st.write(f"**Check Out Date:** {row['Check Out Date']}")
                            
                            if row['Request Type'] in ["Travel", "Travel & Hotel"]:
                                st.write("---")
                                st.write("**Travel Details:**")
                                st.write(f"**Travel Mode:** {row['Travel Mode']}")
                                st.write(f"**From:** {row['From Location']}")
                                st.write(f"**To:** {row['To Location']}")
                                st.write(f"**Booking Date:** {row['Booking Date']}")
                            
                            if row['Remarks']:
                                st.write("---")
                                st.write("**Remarks:**")
                                st.write(row['Remarks'])
                    
                    if not filtered_requests.empty:
                        csv = filtered_requests.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Download Requests",
                            csv,
                            "my_travel_requests.csv",
                            "text/csv",
                            key='download-requests-csv'
                        )
                else:
                    st.info("You haven't made any travel/hotel requests yet.")
            else:
                st.info("No travel/hotel requests found in the system.")
                
        except Exception as e:
            st.error(f"Error retrieving travel/hotel requests: {str(e)}")


def log_ticket_to_gsheet(conn, ticket_data):
    try:
        existing_data = conn.read(worksheet="Tickets", usecols=list(range(len(TICKET_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        updated_data = pd.concat([existing_data, ticket_data], ignore_index=True)
        conn.update(worksheet="Tickets", data=updated_data)
        return True, None
    except Exception as e:
        return False, str(e)

def log_travel_hotel_request(conn, request_data):
    try:
        existing_data = conn.read(worksheet="TravelHotelRequests", usecols=list(range(len(TRAVEL_HOTEL_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        updated_data = pd.concat([existing_data, request_data], ignore_index=True)
        conn.update(worksheet="TravelHotelRequests", data=updated_data)
        return True, None
    except Exception as e:
        return False, str(e)

def log_sales_to_gsheet(conn, sales_data):
    try:
        # Read all existing data first
        existing_sales_data = conn.read(worksheet="Sales", ttl=5)
        existing_sales_data = existing_sales_data.dropna(how="all")
        
        # Ensure columns match (in case sheet structure changes)
        sales_data = sales_data.reindex(columns=SALES_SHEET_COLUMNS)
        
        # Concatenate and drop any potential duplicates
        updated_sales_data = pd.concat([existing_sales_data, sales_data], ignore_index=True)
        updated_sales_data = updated_sales_data.drop_duplicates(subset=["Invoice Number", "Product Name"], keep="last")
        
        # Write back all data
        conn.update(worksheet="Sales", data=updated_sales_data)
        st.success("Sales data successfully logged to Google Sheets!")
    except Exception as e:
        st.error(f"Error logging sales data: {e}")
        st.stop()

def update_delivery_status(conn, invoice_number, product_name, new_status):
    try:
        # Read all existing data
        sales_data = conn.read(worksheet="Sales", ttl=5)
        sales_data = sales_data.dropna(how="all")
        
        # Update the delivery status for the specific record
        mask = (sales_data['Invoice Number'] == invoice_number) & (sales_data['Product Name'] == product_name)
        sales_data.loc[mask, 'Delivery Status'] = new_status
        
        # Write back the updated data
        conn.update(worksheet="Sales", data=sales_data)
        return True
    except Exception as e:
        st.error(f"Error updating delivery status: {e}")
        return False

def log_visit_to_gsheet(conn, visit_data):
    try:
        existing_visit_data = conn.read(worksheet="Visits", ttl=5)
        existing_visit_data = existing_visit_data.dropna(how="all")
        
        visit_data = visit_data.reindex(columns=VISIT_SHEET_COLUMNS)
        
        updated_visit_data = pd.concat([existing_visit_data, visit_data], ignore_index=True)
        updated_visit_data = updated_visit_data.drop_duplicates(subset=["Visit ID"], keep="last")
        
        conn.update(worksheet="Visits", data=updated_visit_data)
        st.success("Visit data successfully logged to Google Sheets!")
    except Exception as e:
        st.error(f"Error logging visit data: {e}")
        st.stop()

def log_attendance_to_gsheet(conn, attendance_data):
    try:
        existing_data = conn.read(worksheet="Attendance", ttl=5)
        existing_data = existing_data.dropna(how="all")
        
        attendance_data = attendance_data.reindex(columns=ATTENDANCE_SHEET_COLUMNS)
        
        updated_data = pd.concat([existing_data, attendance_data], ignore_index=True)
        updated_data = updated_data.drop_duplicates(subset=["Attendance ID"], keep="last")
        
        conn.update(worksheet="Attendance", data=updated_data)
        return True, None
    except Exception as e:
        return False, str(e)


def generate_invoice(customer_name, gst_number, contact_number, address, state, city, selected_products, quantities, product_discounts,
                    discount_category, employee_name, payment_status, amount_paid, employee_selfie_path, payment_receipt_path, invoice_number,
                    transaction_type, distributor_firm_name="", distributor_id="", distributor_contact_person="",
                    distributor_contact_number="", distributor_email="", distributor_territory="", remarks="", invoice_date=None):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    current_date = invoice_date if invoice_date else get_ist_time().strftime("%d-%m-%Y")  # Use provided date or current date


    # Transaction Type
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Transaction Type: {transaction_type.upper()}", ln=True)
    
    # Sales Person
    pdf.ln(0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"Sales Person: {employee_name}", ln=True, align='L')
    
    # Distributor details if available
    if distributor_firm_name:
        pdf.cell(0, 10, f"Distributor: {distributor_firm_name} ({distributor_id})", ln=True, align='L')
        pdf.cell(0, 10, f"Contact: {distributor_contact_person} | {distributor_contact_number}", ln=True, align='L')
        pdf.cell(0, 10, f"Territory: {distributor_territory}", ln=True, align='L')
    
    pdf.ln(5)

    # Customer details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Bill To:", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(100, 6, f"Name: {customer_name}")
    pdf.cell(90, 6, f"Date: {current_date}", ln=True, align='R')
    pdf.cell(100, 6, f"GSTIN/UN: {gst_number}")
    pdf.cell(90, 6, f"Contact: {contact_number}", ln=True, align='R')
    pdf.cell(100, 6, "Address: ", ln=True)
    pdf.multi_cell(0, 6, address)
    pdf.ln(1)
    
    # Invoice number
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"Invoice Number: {invoice_number}", ln=True)
    pdf.ln(5)
    
    # Table header
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(10, 10, "S.No", border=1, align='C', fill=True)
    pdf.cell(70, 10, "Product Name", border=1, align='C', fill=True)
    pdf.cell(20, 10, "HSN/SAC", border=1, align='C', fill=True)
    pdf.cell(20, 10, "Qty", border=1, align='C', fill=True)
    pdf.cell(25, 10, "Rate (INR)", border=1, align='C', fill=True)
    pdf.cell(25, 10, "Discount (%)", border=1, align='C', fill=True)
    pdf.cell(25, 10, "Amount (INR)", border=1, align='C', fill=True)
    pdf.ln()

    # Table rows
    pdf.set_font('Arial', '', 10)
    sales_data = []
    tax_rate = 0.18  # 18% GST
    
    # Calculate subtotal with product discounts
    subtotal = 0
    for idx, (product, quantity, prod_discount) in enumerate(zip(selected_products, quantities, product_discounts)):
        product_data = Products[Products['Product Name'] == product].iloc[0]
        
        if discount_category in product_data:
            unit_price = float(product_data[discount_category])
        else:
            unit_price = float(product_data['Price'])
        
        # Apply product discount
        discounted_unit_price = unit_price * (1 - prod_discount/100)
        item_total = discounted_unit_price * quantity
        subtotal += item_total
        
        pdf.cell(10, 8, str(idx + 1), border=1)
        pdf.cell(70, 8, product, border=1)
        pdf.cell(20, 8, "3304", border=1, align='C')
        pdf.cell(20, 8, str(quantity), border=1, align='C')
        pdf.cell(25, 8, f"{unit_price:.2f}", border=1, align='R')
        pdf.cell(25, 8, f"{prod_discount:.2f}%", border=1, align='R')
        pdf.cell(25, 8, f"{item_total:.2f}", border=1, align='R')
        pdf.ln()

    # Calculate taxes
    tax_amount = subtotal * tax_rate
    cgst_amount = tax_amount / 2
    sgst_amount = tax_amount / 2
    grand_total = subtotal + tax_amount

    # Display totals
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(160, 10, "Subtotal", border=0, align='R')
    pdf.cell(30, 10, f"{subtotal:.2f}", border=1, align='R')
    pdf.ln()
    
    pdf.cell(160, 10, "Taxable Amount", border=0, align='R')
    pdf.cell(30, 10, f"{subtotal:.2f}", border=1, align='R')
    pdf.ln()
    
    pdf.cell(160, 10, "CGST (9%)", border=0, align='R')
    pdf.cell(30, 10, f"{cgst_amount:.2f}", border=1, align='R')
    pdf.ln()
    
    pdf.cell(160, 10, "SGST (9%)", border=0, align='R')
    pdf.cell(30, 10, f"{sgst_amount:.2f}", border=1, align='R')
    pdf.ln()
    
    pdf.cell(160, 10, "Grand Total", border=0, align='R')
    pdf.cell(30, 10, f"{grand_total:.2f} INR", border=1, align='R', fill=True)
    pdf.ln(10)
    
    # Payment Status
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Payment Status: {payment_status.upper()}", ln=True)
    if payment_status == "paid":
        pdf.cell(0, 10, f"Amount Paid: {amount_paid} INR", ln=True)
    pdf.ln(10)
    
    # Details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Details:", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 5, bank_details)
    
    # Prepare sales data for logging
    for idx, (product, quantity, prod_discount) in enumerate(zip(selected_products, quantities, product_discounts)):
        product_data = Products[Products['Product Name'] == product].iloc[0]
        
        if discount_category in product_data:
            unit_price = float(product_data[discount_category])
        else:
            unit_price = float(product_data['Price'])
            
        # Apply product discount
        discounted_unit_price = unit_price * (1 - prod_discount/100)
        item_total = discounted_unit_price * quantity
        
        sales_data.append({
            "Invoice Number": invoice_number,
            "Invoice Date": current_date,
            "Employee Name": employee_name,
            "Employee Code": Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0],
            "Designation": Person[Person['Employee Name'] == employee_name]['Designation'].values[0],
            "Discount Category": discount_category,
            "Transaction Type": transaction_type,
            "Outlet Name": customer_name,
            "Outlet Contact": contact_number,
            "Outlet Address": address,
            "Outlet State": state,
            "Outlet City": city,
            "Distributor Firm Name": distributor_firm_name,
            "Distributor ID": distributor_id,
            "Distributor Contact Person": distributor_contact_person,
            "Distributor Contact Number": distributor_contact_number,
            "Distributor Email": distributor_email,
            "Distributor Territory": distributor_territory,
            "Product ID": product_data['Product ID'],
            "Product Name": product,
            "Product Category": product_data['Product Category'],
            "Quantity": quantity,
            "Unit Price": unit_price,
            "Product Discount (%)": prod_discount,
            "Discounted Unit Price": discounted_unit_price,
            "Total Price": item_total,
            "GST Rate": "18%",
            "CGST Amount": (item_total * tax_rate) / 2,
            "SGST Amount": (item_total * tax_rate) / 2,
            "Grand Total": item_total + (item_total * tax_rate),
            "Payment Status": payment_status,
            "Amount Paid": amount_paid if payment_status == "paid" else 0,
            "Payment Receipt Path": payment_receipt_path if payment_status == "paid" else "",
            "Employee Selfie Path": employee_selfie_path,
            "Invoice PDF Path": f"invoices/{invoice_number}.pdf",
            "Remarks": remarks,
            "Delivery Status": "pending"  # Default status is pending
        })

    # Save the PDF
    pdf_path = f"invoices/{invoice_number}.pdf"
    pdf.output(pdf_path)
    
    # Log sales data to Google Sheets
    sales_df = pd.DataFrame(sales_data)
    log_sales_to_gsheet(conn, sales_df)

    return pdf, pdf_path

def record_visit(employee_name, outlet_name, outlet_contact, outlet_address, outlet_state, outlet_city, 
                 visit_purpose, visit_notes, visit_selfie_path, entry_time, exit_time, remarks=""):
    visit_id = generate_visit_id()
    visit_date = get_ist_time().strftime("%d-%m-%Y")
    
    duration = (exit_time - entry_time).total_seconds() / 60
    
    visit_data = {
        "Visit ID": visit_id,
        "Employee Name": employee_name,
        "Employee Code": Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0],
        "Designation": Person[Person['Employee Name'] == employee_name]['Designation'].values[0],
        "Outlet Name": outlet_name,
        "Outlet Contact": outlet_contact,
        "Outlet Address": outlet_address,
        "Outlet State": outlet_state,
        "Outlet City": outlet_city,
        "Visit Date": visit_date,
        "Entry Time": entry_time.strftime("%H:%M:%S"),
        "Exit Time": exit_time.strftime("%H:%M:%S"),
        "Visit Duration (minutes)": round(duration, 2),
        "Visit Purpose": visit_purpose,
        "Visit Notes": visit_notes,
        "Visit Selfie Path": visit_selfie_path,
        "Visit Status": "completed",
        "Remarks": remarks
    }
    
    visit_df = pd.DataFrame([visit_data])
    log_visit_to_gsheet(conn, visit_df)
    
    return visit_id

def record_attendance(employee_name, status, location_link="", leave_reason=""):
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
            "Check-in Location Link": location_link,
            "Check-out Location Link": "",
            "Leave Reason": leave_reason,
            "Check-in Time": check_in_time,
            "Check-out Time": "",
            "Duration (hours)": "",
            "Check-in Date Time": current_datetime
        }
        
        attendance_df = pd.DataFrame([attendance_data])
        
        success, error = log_attendance_to_gsheet(conn, attendance_df)
        
        if success:
            return attendance_id, None
        else:
            return None, error
            
    except Exception as e:
        return None, f"Error creating attendance record: {str(e)}"

def check_existing_attendance(employee_name):
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        
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

def authenticate_employee(employee_name, passkey):
    try:
        employee_code = Person[Person['Employee Name'] == employee_name]['Employee Code'].values[0]
        return str(passkey) == str(employee_code)
    except:
        return False

def checkout_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Checkout Management")
    selected_employee = st.session_state.employee_name

    # Check if user has checked in today
    try:
        existing_data = conn.read(worksheet="Attendance", usecols=list(range(len(ATTENDANCE_SHEET_COLUMNS))), ttl=5)
        existing_data = existing_data.dropna(how="all")
        
        if existing_data.empty:
            st.error("Please check in first before checking out")
            return
        
        current_date = get_ist_time().strftime("%d-%m-%Y")
        employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
        
        checkin_records = existing_data[
            (existing_data['Employee Code'] == employee_code) & 
            (existing_data['Date'] == current_date)
        ]
        
        if checkin_records.empty:
            st.error("Please check in first before checking out")
            return
            
        if 'Check-out Time' in checkin_records.columns and not checkin_records['Check-out Time'].isna().all():
            st.warning("You have already checked out for today")
            return
    except Exception as e:
        st.error(f"Error checking attendance records: {str(e)}")
        return

    st.subheader("Location Verification (Auto)")

    result = streamlit_js_eval(
        js_expressions="""
            new Promise((resolve) => {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}),
                        err => resolve({latitude: null, longitude: null})
                    );
                } else {
                    resolve({latitude: null, longitude: null});
                }
            });
        """,
        key="geo_checkout"
    ) or {}

    lat = result.get("latitude")
    lng = result.get("longitude")

    if lat and lng:
        gmaps_link = f"https://maps.google.com/?q={lat},{lng}"
        st.success(f"Fetched Location: [View on Google Maps]({gmaps_link})")
    else:
        gmaps_link = ""
        st.info("Waiting for location permission...")

    if lat and lng and st.button("Check Out", key="checkout_button"):
        with st.spinner("Recording checkout..."):
            try:
                # Update the existing attendance record
                existing_data = conn.read(worksheet="Attendance", ttl=5)
                existing_data = existing_data.dropna(how="all")
                
                current_date = get_ist_time().strftime("%d-%m-%Y")
                employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
                
                # Find the record to update
                mask = (
                    (existing_data['Employee Code'] == employee_code) & 
                    (existing_data['Date'] == current_date)
                )
                
                if not mask.any():
                    st.error("No check-in record found for today")
                    return
                
                # Update the record
                existing_data.loc[mask, 'Check-out Time'] = get_ist_time().strftime("%H:%M:%S")
                existing_data.loc[mask, 'Check-out Location Link'] = gmaps_link
                
                # Calculate duration
                checkin_time = pd.to_datetime(existing_data.loc[mask, 'Check-in Time'].iloc[0])
                checkout_time = pd.to_datetime(get_ist_time().strftime("%H:%M:%S"))
                duration = (checkout_time - checkin_time).total_seconds() / 3600  # in hours
                existing_data.loc[mask, 'Duration (hours)'] = round(duration, 2)
                
                # Write back to sheet
                conn.update(worksheet="Attendance", data=existing_data)
                st.success("Checkout recorded successfully!")
                st.balloons()
            except Exception as e:
                st.error(f"Failed to record checkout: {str(e)}")

def resources_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Company Resources")
    st.markdown("Download important company documents and product catalogs.")
    
    # Define the resources
    resources = [
        {
            "name": "Product Catalogue",
            "description": "Complete list of all available products with specifications",
            "file_path": "Biolume Salon Prices Catalogue.pdf"
        },
        {
            "name": "Employee Handbook",
            "description": "Company policies, procedures, and guidelines for employees",
            "file_path": "Biolume Employee Handbook.pdf"
        },
        {
            "name": "Facial Treatment Catalogue",
            "description": "Complete list of all Facial products with specifications",
            "file_path": "Biolume's Facial Treatment Catalogue.pdf"
        }
    ]
    
    # Display each resource in a card-like format
    for resource in resources:
        with st.container():
            st.subheader(resource["name"])
            st.markdown(resource["description"])
            
            # Check if file exists
            if os.path.exists(resource["file_path"]):
                with open(resource["file_path"], "rb") as file:
                    btn = st.download_button(
                        label=f"Download {resource['name']}",
                        data=file,
                        file_name=resource["file_path"],
                        mime="application/pdf",
                        key=f"download_{resource['name']}"
                    )
            else:
                st.error(f"File not found: {resource['file_path']}")
            
            st.markdown("---")  # Divider between resources

def add_back_button():
    st.markdown("""
    <style>
    .back-button {
        position: fixed;
        bottom: 20px;
        left: 20px;
        z-index: 1000;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("← logout", key="back_button"):
        st.session_state.authenticated = False
        st.session_state.selected_mode = None
        st.rerun()

def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_mode' not in st.session_state:
        st.session_state.selected_mode = None
    if 'employee_name' not in st.session_state:
        st.session_state.employee_name = None

    if not st.session_state.authenticated:
        # Display the centered logo and heading
        display_login_header()

        employee_names = Person['Employee Name'].tolist()

        # Create centered form
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
                        # Immediately fetch and log location after login
                        result = streamlit_js_eval(
                            js_expressions="""
                                new Promise((resolve) => {
                                    if (navigator.geolocation) {
                                        navigator.geolocation.getCurrentPosition(
                                            pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}),
                                            err => resolve({latitude: null, longitude: null})
                                        );
                                    } else {
                                        resolve({latitude: null, longitude: null});
                                    }
                                });
                            """,
                            key=f"geo_login_{employee_name}_{int(time.time())}"
                        ) or {}

                        lat = result.get("latitude")
                        lng = result.get("longitude")
                        if lat and lng:
                            log_location_history(conn, employee_name, lat, lng)
                            gmaps_link = f"https://maps.google.com/?q={lat},{lng}"
                            st.success(f"Login location logged: [View on Google Maps]({gmaps_link})")
                            # Brief pause for user to see the message
                            time.sleep(1.5)
                        st.session_state.authenticated = True
                        st.session_state.employee_name = employee_name
                        st.rerun()
                    else:
                        st.error("Invalid Password. Please try again.")
    else:
        # Show option boxes after login
        st.title("Select Mode")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Attendance", use_container_width=True, key="attendance_mode"):
                st.session_state.selected_mode = "Attendance"
                st.rerun()
                
        with col2:  # Add this after the existing columns
            if st.button("Checkout", use_container_width=True, key="checkout_mode"):
                st.session_state.selected_mode = "Checkout"
                st.rerun()
                
        with col3:
            if st.button("Resources", use_container_width=True, key="resources_mode"):
                st.session_state.selected_mode = "Resources"
                st.rerun()



        if st.session_state.selected_mode:
            add_back_button()

            if st.session_state.selected_mode == "Sales":
                sales_page()
            elif st.session_state.selected_mode == "Visit":
                visit_page()
            elif st.session_state.selected_mode == "Attendance":
                attendance_page()
            elif st.session_state.selected_mode == "Resources":
                resources_page()
            elif st.session_state.selected_mode == "Checkout":
                checkout_page()
            elif st.session_state.selected_mode == "Support Ticket":
                support_ticket_page()
            elif st.session_state.selected_mode == "Travel/Hotel":
                travel_hotel_page()
            elif st.session_state.selected_mode == "Demo":
                demo_page()


def sales_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Sales Management")
    selected_employee = st.session_state.employee_name
    sales_remarks = ""
    tab1, tab2 = st.tabs(["New Sale", "Sales History"])
    
    with tab1:
        discount_category = Person[Person['Employee Name'] == selected_employee]['Discount Category'].values[0]
    
        st.subheader("Transaction Details")
        transaction_type = st.selectbox(
            "Transaction Type",
            ["Sold", "Return", "Add On", "Damage", "Expired"],
            key="transaction_type"
        )
    
        st.subheader("Product Details")
        product_names     = Products['Product Name'].tolist()
        selected_products = st.multiselect(
            "Select Products",
            product_names,
            key="product_selection"
        )
    
        quantities = []
        product_discounts = []
    
        if selected_products:
            st.markdown("### Product Prices & Discounts")
            price_cols = st.columns(4)
            with price_cols[0]:
                st.markdown("**Product**")
            with price_cols[1]:
                st.markdown("**Price (INR)**")
            with price_cols[2]:
                st.markdown("**Discount %**")
            with price_cols[3]:
                st.markdown("**Quantity**")
    
            subtotal = 0.0
            for product in selected_products:
                product_data = Products[Products['Product Name'] == product].iloc[0]
                unit_price = float(product_data.get(discount_category, product_data['Price']))
    
                cols = st.columns(4)
                with cols[0]:
                    st.text(product)
                with cols[1]:
                    st.text(f"₹{unit_price:.2f}")
    
                # Discount % placeholder
                with cols[2]:
                    disc_str = st.text_input(
                        "Discount %",
                        key=f"discount_{product}",
                        placeholder="Discount %",
                        label_visibility="collapsed"
                    )
                    try:
                        prod_discount = float(disc_str)
                    except:
                        prod_discount = 0.0
                    product_discounts.append(prod_discount)
    
                # Quantity placeholder
                with cols[3]:
                    qty_str = st.text_input(
                        "Quantity",
                        key=f"qty_{product}",
                        placeholder="Quantity",
                        label_visibility="collapsed"
                    )
                    try:
                        qty = int(qty_str)
                    except:
                        qty = 1
                    quantities.append(qty)
    
                # accumulate subtotal
                subtotal += unit_price * (1 - prod_discount / 100) * qty
    
            # Final amount calculation
            st.markdown("---")
            st.markdown("### Final Amount Calculation")
            st.markdown(f"Subtotal: ₹{subtotal:.2f}")
            tax_amount = subtotal * 0.18
            st.markdown(f"GST (18%): ₹{tax_amount:.2f}")
            st.markdown(f"**Grand Total: ₹{subtotal + tax_amount:.2f}**")
    
        st.subheader("Payment Details")
        payment_status = st.selectbox("Payment Status", ["pending", "paid"], key="payment_status")
        amount_paid = 0.0
        if payment_status == "paid":
            amount_paid = st.number_input(
                "Amount Paid (INR)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="amount_paid"
            )
    
        st.subheader("Distributor Details")
        distributor_option = st.radio("Distributor Selection", ["Select from list", "None"], key="distributor_option")
        distributor_firm_name = distributor_id = distributor_contact_person = ""
        distributor_contact_number = distributor_email = distributor_territory = ""
    
        if distributor_option == "Select from list":
            distributor_names = Distributors['Firm Name'].tolist()
            selected_distributor = st.selectbox("Select Distributor", distributor_names, key="distributor_select")
            dd = Distributors[Distributors['Firm Name'] == selected_distributor].iloc[0]
            distributor_firm_name      = selected_distributor
            distributor_id             = dd['Distributor ID']
            distributor_contact_person = dd['Contact Person']
            distributor_contact_number = dd['Contact Number']
            distributor_email          = dd['Email ID']
            distributor_territory      = dd['Territory']
    
            st.text_input("Distributor ID", value=distributor_id, disabled=True, key="distributor_id_display")
            st.text_input("Contact Person", value=distributor_contact_person, disabled=True, key="distributor_contact_person_display")
            st.text_input("Contact Number", value=distributor_contact_number, disabled=True, key="distributor_contact_number_display")
            st.text_input("Email", value=distributor_email, disabled=True, key="distributor_email_display")
            st.text_input("Territory", value=distributor_territory, disabled=True, key="distributor_territory_display")
    
        st.subheader("Outlet Details")
        outlet_option = st.radio("Outlet Selection", ["Enter manually", "Select from list"], key="outlet_option")
        if outlet_option == "Select from list":
            outlet_names = Outlet['Shop Name'].tolist()
            chosen_outlet = st.selectbox("Select Outlet", outlet_names, key="outlet_select")
            od = Outlet[Outlet['Shop Name'] == chosen_outlet].iloc[0]
            customer_name, gst_number = chosen_outlet, od['GST']
            contact_number, address = od['Contact'], od['Address']
            state, city = od['State'], od['City']
    
            st.text_input("GST Number", value=gst_number, disabled=True, key="outlet_gst_display")
            st.text_input("Contact Number", value=contact_number, disabled=True, key="outlet_contact_display")
            st.text_input("Address", value=address, disabled=True, key="outlet_address_display")
            st.text_input("State", value=state, disabled=True, key="outlet_state_display")
            st.text_input("City", value=city, disabled=True, key="outlet_city_display")
        else:
            customer_name = st.text_input("Outlet Name", key="manual_outlet_name")
            gst_number    = st.text_input("GST Number", key="manual_gst_number")
            contact_number = st.text_input("Contact Number", key="manual_contact_number")
            address        = st.text_area("Address", key="manual_address")
            state          = st.text_input("State", "", key="manual_state")
            city           = st.text_input("City", "", key="manual_city")
    
        if st.button("Generate Invoice", key="generate_invoice_button"):
            if selected_products and customer_name:
                invoice_number = generate_invoice_number()
                pdf, pdf_path = generate_invoice(
                    customer_name, gst_number, contact_number, address, state, city,
                    selected_products, quantities, product_discounts, discount_category,
                    selected_employee, payment_status, amount_paid, None, None,
                    invoice_number, transaction_type,
                    distributor_firm_name, distributor_id, distributor_contact_person,
                    distributor_contact_number, distributor_email, distributor_territory,
                    "",  # remarks
                )
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download Invoice",
                        f,
                        file_name=f"{invoice_number}.pdf",
                        mime="application/pdf",
                        key=f"download_{invoice_number}"
                    )
                st.success(f"Invoice {invoice_number} generated successfully!")
                st.balloons()
            else:
                st.error("Please fill all required fields and select products.")

    
    with tab2:
        st.subheader("Your Sales History")
        
        @st.cache_data(ttl=300)
        def load_sales_data():
            try:
                sales_data = conn.read(worksheet="Sales", ttl=5)
                sales_data = sales_data.dropna(how='all')
                
                # Convert columns to proper types
                sales_data = sales_data.copy()
                sales_data['Outlet Name'] = sales_data['Outlet Name'].astype(str)
                sales_data['Invoice Number'] = sales_data['Invoice Number'].astype(str)
                
                # Convert Invoice Date properly
                try:
                    sales_data['Invoice Date'] = pd.to_datetime(sales_data['Invoice Date'], dayfirst=True, errors='coerce')
                except:
                    # Fallback if date parsing fails
                    sales_data['Invoice Date'] = pd.to_datetime(sales_data['Invoice Date'], errors='coerce')
                
                # Convert numeric columns properly
                numeric_cols = ['Grand Total', 'Unit Price', 'Total Price', 'Product Discount (%)', 'Quantity']
                for col in numeric_cols:
                    if col in sales_data.columns:
                        sales_data[col] = pd.to_numeric(sales_data[col], errors='coerce')
                
                # Filter for current employee
                employee_code = Person[Person['Employee Name'] == st.session_state.employee_name]['Employee Code'].values[0]
                filtered_data = sales_data[sales_data['Employee Code'] == employee_code]
                
                # Ensure we have valid dates
                filtered_data = filtered_data[filtered_data['Invoice Date'].notna()]
                
                return filtered_data
            except Exception as e:
                st.error(f"Error loading sales data: {e}")
                return pd.DataFrame()
    
        sales_data = load_sales_data()
        
        if sales_data.empty:
            st.warning("No sales records found for your account")
            return
            
        with st.expander("🔍 Search Filters", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                invoice_number_search = st.text_input("Invoice Number", key="invoice_search")
            with col2:
                invoice_date_search = st.date_input("Invoice Date", key="date_search")
            with col3:
                outlet_name_search = st.text_input("Outlet Name", key="outlet_search")
            
            if st.button("Apply Filters", key="search_sales_button"):
                st.rerun()
        
        filtered_data = sales_data.copy()
        
        # Apply filters
        if invoice_number_search:
            filtered_data = filtered_data[
                filtered_data['Invoice Number'].str.contains(invoice_number_search, case=False, na=False)
            ]
        
        if invoice_date_search:
            date_str = invoice_date_search.strftime("%d-%m-%Y")
            filtered_data = filtered_data[
                filtered_data['Invoice Date'].dt.strftime('%d-%m-%Y') == date_str
            ]
        
        if outlet_name_search:
            filtered_data = filtered_data[
                filtered_data['Outlet Name'].str.contains(outlet_name_search, case=False, na=False)
            ]
        
        if filtered_data.empty:
            st.warning("No matching records found")
            return
            
        # Calculate correct grand total by invoice
        invoice_summary = filtered_data.groupby('Invoice Number').agg({
            'Invoice Date': 'first',
            'Outlet Name': 'first',
            'Grand Total': 'sum',
            'Payment Status': 'first',
            'Delivery Status': 'first'
        }).reset_index()
        
        # Sort by date descending
        invoice_summary = invoice_summary.sort_values('Invoice Date', ascending=False)
        
        st.write(f"📄 Showing {len(invoice_summary)} of your invoices")
        
        # Display the summary table
        st.dataframe(
            invoice_summary,
            column_config={
                "Grand Total": st.column_config.NumberColumn(
                    format="₹%.2f",
                    help="Sum of all products in the invoice including taxes"
                ),
                "Invoice Date": st.column_config.DateColumn(
                    format="DD/MM/YYYY",
                    help="Date when invoice was generated"
                )
            },
            use_container_width=True,
            hide_index=True
        )
        
        selected_invoice = st.selectbox(
            "Select invoice to view details",
            invoice_summary['Invoice Number'],
            key="invoice_selection"
        )
        
        # Delivery Status Section
        st.subheader("Delivery Status Management")
        
        # Get all products for the selected invoice
        invoice_details = filtered_data[filtered_data['Invoice Number'] == selected_invoice]
        
        if not invoice_details.empty:
            # Create a form for delivery status updates
            with st.form(key='delivery_status_form'):
                # Get current status for the invoice
                current_status = invoice_details.iloc[0].get('Delivery Status', 'Pending')
                
                status_options = ["Pending", "Order Done", "Delivery Done", "Cancelled"]
                new_status = st.selectbox(
                    "Update Delivery Status",
                    status_options,
                    index=status_options.index(current_status) if current_status in status_options else 0,
                    key=f"status_{selected_invoice}"
                )

                
                # Submit button for the form
                submitted = st.form_submit_button("Update Status")
                
                if submitted:
                    with st.spinner("Updating delivery status..."):
                        try:
                            # Get all sales data
                            all_sales_data = conn.read(worksheet="Sales", ttl=5)
                            all_sales_data = all_sales_data.dropna(how='all')
                            
                            # Update the status for all rows with this invoice number
                            mask = all_sales_data['Invoice Number'] == selected_invoice
                            all_sales_data.loc[mask, 'Delivery Status'] = new_status
                            
                            # Write back the updated data
                            conn.update(worksheet="Sales", data=all_sales_data)
                            
                            st.success(f"Delivery status updated to '{new_status}' for invoice {selected_invoice}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating delivery status: {e}")
        
        # Display invoice details
        if not invoice_details.empty:
            invoice_data = invoice_details.iloc[0]
            original_invoice_date = invoice_data['Invoice Date'].strftime('%d-%m-%Y')
            
            st.subheader(f"Invoice {selected_invoice}")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Date", original_invoice_date)
                st.metric("Outlet", str(invoice_data['Outlet Name']))
                st.metric("Contact", str(invoice_data['Outlet Contact']))
            with col2:
                # Calculate correct total for this invoice
                invoice_total = invoice_details['Grand Total'].sum()
                st.metric("Total Amount", f"₹{invoice_total:.2f}")
                st.metric("Payment Status", str(invoice_data['Payment Status']).capitalize())
                st.metric("Delivery Status", str(invoice_data.get('Delivery Status', 'Pending')).capitalize())
            
            st.subheader("Products")
            product_display = invoice_details[[
                'Product Name', 
                'Quantity', 
                'Unit Price', 
                'Product Discount (%)', 
                'Total Price', 
                'Grand Total'
            ]].copy()
            
            # Format display
            product_display['Product Name'] = product_display['Product Name'].astype(str)
            product_display['Quantity'] = product_display['Quantity'].astype(int)
            
            st.dataframe(
                product_display,
                column_config={
                    "Unit Price": st.column_config.NumberColumn(format="₹%.2f"),
                    "Total Price": st.column_config.NumberColumn(format="₹%.2f"),
                    "Grand Total": st.column_config.NumberColumn(format="₹%.2f")
                },
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("🔄 Regenerate Invoice", key=f"regenerate_btn_{selected_invoice}"):
                with st.spinner("Regenerating invoice..."):
                    try:
                        pdf, pdf_path = generate_invoice(
                            str(invoice_data['Outlet Name']),
                            str(invoice_data.get('GST Number', '')),
                            str(invoice_data['Outlet Contact']),
                            str(invoice_data['Outlet Address']),
                            str(invoice_data['Outlet State']),
                            str(invoice_data['Outlet City']),
                            invoice_details['Product Name'].astype(str).tolist(),
                            invoice_details['Quantity'].tolist(),
                            invoice_details['Product Discount (%)'].tolist(),
                            str(invoice_data['Discount Category']),
                            str(invoice_data['Employee Name']),
                            str(invoice_data['Payment Status']),
                            float(invoice_data['Amount Paid']),
                            None,
                            None,
                            str(selected_invoice),
                            str(invoice_data['Transaction Type']),
                            str(invoice_data.get('Distributor Firm Name', '')),
                            str(invoice_data.get('Distributor ID', '')),
                            str(invoice_data.get('Distributor Contact Person', '')),
                            str(invoice_data.get('Distributor Contact Number', '')),
                            str(invoice_data.get('Distributor Email', '')),
                            str(invoice_data.get('Distributor Territory', '')),
                            str(invoice_data.get('Remarks', '')),
                            original_invoice_date 
                        )
                        
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "📥 Download Regenerated Invoice", 
                                f, 
                                file_name=f"{selected_invoice}.pdf",
                                mime="application/pdf",
                                key=f"download_regenerated_{selected_invoice}"
                            )
                        
                        st.success("Invoice regenerated successfully with original date!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error regenerating invoice: {e}")

def visit_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Visit Management")
    selected_employee = st.session_state.employee_name

    # Empty remarks since we removed the location input
    visit_remarks = ""

    tab1, tab2 = st.tabs(["New Visit", "Visit History"])
    
    with tab1:
        st.subheader("Outlet Details")
        outlet_option = st.radio("Outlet Selection", ["Enter manually", "Select from list"], key="visit_outlet_option")
        
        if outlet_option == "Select from list":
            outlet_names = Outlet['Shop Name'].tolist()
            selected_outlet = st.selectbox("Select Outlet", outlet_names, key="visit_outlet_select")
            outlet_details = Outlet[Outlet['Shop Name'] == selected_outlet].iloc[0]
            
            outlet_name = selected_outlet
            outlet_contact = outlet_details['Contact']
            outlet_address = outlet_details['Address']
            outlet_state = outlet_details['State']
            outlet_city = outlet_details['City']
            
            # Show outlet details like distributor details
            st.text_input("Outlet Contact", value=outlet_contact, disabled=True, key="outlet_contact_display")
            st.text_input("Outlet Address", value=outlet_address, disabled=True, key="outlet_address_display")
            st.text_input("Outlet State", value=outlet_state, disabled=True, key="outlet_state_display")
            st.text_input("Outlet City", value=outlet_city, disabled=True, key="outlet_city_display")
        else:
            outlet_name = st.text_input("Outlet Name", key="visit_outlet_name")
            outlet_contact = st.text_input("Outlet Contact", key="visit_outlet_contact")
            outlet_address = st.text_area("Outlet Address", key="visit_outlet_address")
            outlet_state = st.text_input("Outlet State", "", key="visit_outlet_state")
            outlet_city = st.text_input("Outlet City", "", key="visit_outlet_city")

        st.subheader("Visit Details")
        visit_purpose = st.selectbox("Visit Purpose", ["Sales", "Demo", "Product Demonstration", "Relationship Building", "Issue Resolution", "Other"], key="visit_purpose")
        visit_notes = st.text_area("Visit Notes", key="visit_notes")
        
        st.subheader("Time Tracking")
        col1, col2 = st.columns(2)
        with col1:
            entry_time = st.time_input("Entry Time", value=None, key="visit_entry_time")
        with col2:
            exit_time = st.time_input("Exit Time", value=None, key="visit_exit_time")

        if st.button("Record Visit", key="record_visit_button"):
            if outlet_name:
                today = get_ist_time().date()
                
                if entry_time is None:
                    entry_time = get_ist_time().time()
                if exit_time is None:
                    exit_time = get_ist_time().time()
                    
                entry_datetime = datetime.combine(today, entry_time)
                exit_datetime = datetime.combine(today, exit_time)
                
                # No visit selfie upload
                visit_selfie_path = None
                
                visit_id = record_visit(
                    selected_employee, outlet_name, outlet_contact, outlet_address,
                    outlet_state, outlet_city, visit_purpose, visit_notes, 
                    visit_selfie_path, entry_datetime, exit_datetime,
                    visit_remarks
                )
                
                st.success(f"Visit {visit_id} recorded successfully!")
            else:
                st.error("Please fill all required fields.")
    
    with tab2:
        st.subheader("Previous Visits")
        col1, col2, col3 = st.columns(3)
        with col1:
            visit_id_search = st.text_input("Visit ID", key="visit_id_search")
        with col2:
            visit_date_search = st.date_input("Visit Date", key="visit_date_search")
        with col3:
            outlet_name_search = st.text_input("Outlet Name", key="visit_outlet_search")
            
        if st.button("Search Visits", key="search_visits_button"):
            try:
                visit_data = conn.read(worksheet="Visits", ttl=5)
                visit_data = visit_data.dropna(how="all")
                
                employee_code = Person[Person['Employee Name'] == selected_employee]['Employee Code'].values[0]
                filtered_data = visit_data[visit_data['Employee Code'] == employee_code]
                
                if visit_id_search:
                    filtered_data = filtered_data[filtered_data['Visit ID'].str.contains(visit_id_search, case=False)]
                if visit_date_search:
                    date_str = visit_date_search.strftime("%d-%m-%Y")
                    filtered_data = filtered_data[filtered_data['Visit Date'] == date_str]
                if outlet_name_search:
                    filtered_data = filtered_data[filtered_data['Outlet Name'].str.contains(outlet_name_search, case=False)]
                
                if not filtered_data.empty:
                    # Display only the most relevant columns
                    display_columns = [
                        'Visit ID', 'Visit Date', 'Outlet Name', 'Visit Purpose', 'Visit Notes',
                        'Entry Time', 'Exit Time', 'Visit Duration (minutes)', 'Remarks'
                    ]
                    st.dataframe(filtered_data[display_columns])
                    
                    # Add download option
                    csv = filtered_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download as CSV",
                        csv,
                        "visit_history.csv",
                        "text/csv",
                        key='download-visit-csv'
                    )
                else:
                    st.warning("No matching visit records found")
            except Exception as e:
                st.error(f"Error retrieving visit data: {e}")

from streamlit_js_eval import streamlit_js_eval

def attendance_page():
    hourly_location_auto_log(conn, st.session_state.employee_name)
    st.title("Attendance Management")
    selected_employee = st.session_state.employee_name

    if check_existing_attendance(selected_employee):
        st.warning("You have already marked your attendance for today.")
        return

    st.subheader("Attendance Status")
    status = st.radio("Select Status", ["Present", "Half Day", "Leave"], index=0, key="attendance_status")

    if status in ["Present", "Half Day"]:
        st.subheader("Location Verification (Auto)")

        result = streamlit_js_eval(
            js_expressions="""
                new Promise((resolve) => {
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition(
                            pos => resolve({latitude: pos.coords.latitude, longitude: pos.coords.longitude}),
                            err => resolve({latitude: null, longitude: null})
                        );
                    } else {
                        resolve({latitude: null, longitude: null});
                    }
                });
            """,
            key="geo"
        ) or {}

        lat = result.get("latitude")
        lng = result.get("longitude")

        if lat and lng:
            gmaps_link = f"https://maps.google.com/?q={lat},{lng}"
            st.success(f"Fetched Location: [View on Google Maps]({gmaps_link})")
        else:
            gmaps_link = ""
            st.info("Waiting for location permission...")

        if lat and lng and st.button("Mark Attendance", key="mark_attendance_button"):
            with st.spinner("Recording attendance..."):
                attendance_id, error = record_attendance(
                    selected_employee,
                    status,
                    location_link=gmaps_link
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
