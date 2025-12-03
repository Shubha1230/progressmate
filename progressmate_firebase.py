# progressmate_firebase.py

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from io import BytesIO
import pyrebase
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import html

# -----------------------------------------------------
# Firebase config
# -----------------------------------------------------
firebase_cfg = st.secrets.get("firebase", None)
if firebase_cfg is None:
    st.error("Firebase config missing in secrets.toml")
    st.stop()

firebase = pyrebase.initialize_app(firebase_cfg)
auth = firebase.auth()
db = firebase.database()

# -----------------------------------------------------
# Local Excel Backup
# -----------------------------------------------------
FILE_NAME = Path("ProgressMate_Data.xlsx")

def ensure_local_excel():
    if not FILE_NAME.exists():
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Date","Project Name","Quate","Target for Month","Target Achieved","UserEmail","DisplayName","FKey"])
        wb.save(FILE_NAME)

def append_local(row):
    ensure_local_excel()
    df = pd.read_excel(FILE_NAME)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_excel(FILE_NAME, index=False)

# -----------------------------------------------------
# Database Operations
# -----------------------------------------------------
def push_entry(entry):
    res = db.child("entries").push(entry)
    key = res.get("name")
    if key:
        db.child("entries").child(key).update({"FKey": key})
        entry["FKey"] = key
    append_local(entry)

def fetch_all_entries():
    raw = db.child("entries").get().val()
    if not raw:
        ensure_local_excel()
        return pd.read_excel(FILE_NAME)

    rows = []
    for k, v in raw.items():
        item = dict(v)
        item["FKey"] = item.get("FKey", k)
        rows.append(item)

    df = pd.DataFrame(rows)
    expected = ["Date","Project Name","Quate","Target for Month","Target Achieved","UserEmail","DisplayName","FKey"]
    for c in expected:
        if c not in df.columns:
            df[c] = None

    try:
        df["DateTime"] = pd.to_datetime(df["Date"])
    except:
        df["DateTime"] = pd.NaT

    df = df.sort_values("DateTime", ascending=False).reset_index(drop=True)
    return df

# -----------------------------------------------------
# PDF Export
# -----------------------------------------------------
def export_pdf_bytes(df):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkgray),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.black),
    ]))
    pdf.build([table])
    buffer.seek(0)
    return buffer

# -----------------------------------------------------
# Login / Signup / Reset (Fully Fixed)
# -----------------------------------------------------
def login_ui():
    st.title("🔐 Login / Signup")

    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Forgot Password"])

    # ------------------------ LOGIN ------------------------
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            pwd = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

        if submit:
            try:
                user = auth.sign_in_with_email_and_password(email, pwd)
                st.session_state["user"] = user
                st.success("Logged in!")
                st.rerun()
            except:
                st.error("Invalid email or password")

    # ------------------------ SIGNUP ------------------------
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("New Email")
            pwd = st.text_input("New Password", type="password")
            submit = st.form_submit_button("Create Account")

        if submit:
            try:
                auth.create_user_with_email_and_password(email, pwd)
                st.success("Account created! Please login.")
            except:
                st.error("Unable to create account. Try another email.")

    # ------------------------ FORGOT PASSWORD ------------------------
    with tab3:
        with st.form("reset_form"):
            email = st.text_input("Email for reset")
            submit = st.form_submit_button("Send Reset Link")

        if submit:
            try:
                auth.send_password_reset_email(email)
                st.success("Password reset link sent!")
            except:
                st.error("Failed to send reset email.")

# -----------------------------------------------------
# Theme & UI Styling
# -----------------------------------------------------
st.set_page_config(page_title="ProgressMate", layout="wide")

if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def apply_theme():
    theme = st.session_state["theme"]
    if theme == "dark":
        bg = "#111111"; text = "#f1f1f1"; card = "#1a1a1a"; accent = "#4f46e5"
    else:
        bg = "#f6f8ff"; text = "#1a1a1a"; card = "#ffffff"; accent = "#2563eb"

    st.markdown(f"""
    <style>
        body {{ background-color:{bg}; color:{text}; }}
        .card {{ background:{card}; padding:18px; border-radius:12px; 
                 margin-bottom:14px; box-shadow:0 3px 10px rgba(0,0,0,0.1); }}
    </style>
    """, unsafe_allow_html=True)

apply_theme()

# -----------------------------------------------------
# AUTH CHECK
# -----------------------------------------------------
if "user" not in st.session_state:
    st.session_state["user"] = None

if not st.session_state["user"]:
    login_ui()
    st.stop()

# -----------------------------------------------------
# DASHBOARD AFTER LOGIN
# -----------------------------------------------------
st.title("🌟 ProgressMate Dashboard")

colA, colB = st.columns(2)
with colA:
    st.success("You are logged in!")
with colB:
    if st.button("Logout"):
        st.session_state["user"] = None
        st.rerun()

# SEARCH + ADD ENTRY
search = st.text_input("Search projects")

if st.button("➕ Add Entry"):
    st.session_state["add"] = True
    st.rerun()

# ADD ENTRY FORM
if st.session_state.get("add"):
    st.subheader("Add New Entry")
    name = st.text_input("Project Name")
    quate = st.number_input("Quate", min_value=0.0)
    target = st.number_input("Target", min_value=0.0)

    if st.button("Save"):
        if name == "":
            st.warning("Project name required.")
        else:
            entry = {
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Project Name": name,
                "Quate": quate,
                "Target for Month": target,
                "Target Achieved": target - quate,
                "UserEmail": "user",
                "DisplayName": "User"
            }
            push_entry(entry)
            st.success("Saved!")
            st.session_state["add"] = False
            st.rerun()

    if st.button("Cancel"):
        st.session_state["add"] = False
        st.rerun()

# DATA TABLE
df = fetch_all_entries()
if search:
    df = df[df["Project Name"].str.contains(search, case=False, na=False)]

st.subheader("📋 Entries")

for idx, row in df.iterrows():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.write(f"### {row['Project Name']}")
    st.write(f"Quate: {row['Quate']}")
    st.write(f"Target: {row['Target for Month']}")
    st.write(f"Achieved: {row['Target Achieved']}")
    st.write(f"Date: {row['Date']}")

    c1, c2 = st.columns(2)
    if c1.button("Edit", key=f"edit{idx}"):
        st.session_state["edit"] = row
        st.rerun()

    if c2.button("Delete", key=f"del{idx}"):
        delete_entry(row["FKey"])
        st.warning("Entry deleted.")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# EXPORT
st.subheader("📤 Export Data")

if not df.empty:
    excel_buf = BytesIO()
    df.drop(columns=["FKey"], errors="ignore").to_excel(excel_buf, index=False)
    excel_buf.seek(0)
    st.download_button("⬇ Export Excel", excel_buf, "progressmate.xlsx")

    st.download_button("⬇ Export CSV", df.to_csv(index=False), "progressmate.csv")

    pdf_bytes = export_pdf_bytes(df.drop(columns=["FKey"], errors="ignore"))
    st.download_button("⬇ Export PDF", pdf_bytes, "progressmate.pdf", mime="application/pdf")



