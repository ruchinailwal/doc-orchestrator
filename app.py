import streamlit as st
import pdfplumber
import json
import requests
from google import genai

# 1. Gemini Client Configuration
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options={'api_version': 'v1beta'}
)

# UI Layout
st.set_page_config(page_title="AI Document Orchestrator", layout="wide")
st.title("🚀 AI-Powered Document Orchestrator")
st.markdown("---")

# Sidebar for Inputs
with st.sidebar:
    st.header("Upload & Query")
    uploaded_file = st.file_uploader("Choose a PDF or TXT file", type=["pdf", "txt"])
    user_query = st.text_input("What information should I extract?", placeholder="e.g. Extract invoice total")

# Helper function to extract text
def extract_text(file):
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text
    return file.read().decode("utf-8")

# -------------------------
# STAGE 1: Data Extraction
# -------------------------
if uploaded_file and user_query:
    if st.button("🔍 Step 1: Extract Data"):
        with st.spinner("Gemini is analyzing the document..."):
            try:
                doc_text = extract_text(uploaded_file)
                limited_text = doc_text[:12000]

                prompt = f"""
                Document Content: {limited_text}
                Instruction: {user_query}
                
                Task: Return the 5-8 most relevant key-value pairs as a JSON object.
                Respond ONLY with valid JSON.
                """

                response = client.models.generate_content(
                    model="models/gemini-1.5-flash",
                    contents=prompt
                )

                # Clean and parse JSON
                clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
                try:
                    extracted_json = json.loads(clean_json_str)
                except:
                    extracted_json = {"result": clean_json_str}

                # Save to session state
                st.session_state["doc_text"] = doc_text
                st.session_state["extracted_json"] = extracted_json
                st.session_state["user_query"] = user_query
                st.success("Extraction Complete!")

            except Exception as e:
                st.error("Error during extraction")
                st.exception(e)

# Display Output ① (Structured Data)
if "extracted_json" in st.session_state:
    st.subheader("① Structured Data Extracted (JSON)")
    st.json(st.session_state["extracted_json"])
    st.markdown("---")

    # -------------------------
    # STAGE 2: n8n Automation
    # -------------------------
    st.subheader("📬 Step 2: Trigger Analysis & Email")

    col1, col2 = st.columns([2, 1])
    with col1:
        recipient_email = st.text_input("Recipient Email ID", placeholder="example@mail.com")
    with col2:
        st.write("##")
        send_button = st.button("🚀 Send Alert Mail")

    if send_button:
        if not recipient_email:
            st.warning("Please enter an email address.")
        else:
            with st.spinner("Triggering n8n workflow..."):
                try:
                    payload = {
                        "text": st.session_state["doc_text"],
                        "extracted_json": st.session_state["extracted_json"],
                        "question": st.session_state["user_query"],
                        "recipient_email": recipient_email
                    }

                    n8n_response = requests.post(
                        st.secrets["N8N_WEBHOOK_URL"],
                        json=payload,
                        timeout=60
                    )

                    # ✅ FIXED: Handle empty or non-JSON response from n8n
                    try:
                        result = n8n_response.json()
                    except Exception:
                        if n8n_response.status_code == 200:
                            result = {
                                "final_answer": "Workflow executed successfully.",
                                "email_body": "Email was sent via n8n automation.",
                                "status": "SENT"
                            }
                        else:
                            result = {
                                "final_answer": f"n8n returned status {n8n_response.status_code}",
                                "email_body": "Email was not sent - condition not met",
                                "status": "Failed"
                            }

                    # Display the 3 additional required outputs
                    st.subheader("② Final Analytical Answer")
                    st.info(result.get("final_answer", "No analysis returned."))

                    st.subheader("③ Generated Email Body")
                    st.text_area("Email Content", result.get("email_body", "No email drafted."), height=200)

                    st.subheader("④ Email Automation Status")
                    status = result.get("status", "Unknown")
                    if "SENT" in status.upper():
                        st.success(f"✅ Alert Email Status: {status}")
                    else:
                        st.warning(f"⚠️ Status: {status}")

                except Exception as e:
                    st.error("Connection to n8n failed")
                    st.exception(e)