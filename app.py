import streamlit as st
import pdfplumber
import json
import requests
from google import genai

# Gemini Client - Uses credentials from .streamlit/secrets.toml
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

# Streamlit UI Configuration
st.set_page_config(page_title="AI Document Orchestrator", layout="wide")
st.title("🚀 AI-Powered Document Orchestrator")
st.markdown("---")

# 1. Sidebar - File Upload and Query
with st.sidebar:
    st.header("Input Section")
    uploaded_file = st.file_uploader(
        "Upload document (PDF or TXT)", 
        type=["pdf", "txt"]
    )
    user_query = st.text_input(
        "What should the AI extract?", 
        placeholder="e.g., Extract total amount and due date"
    )

# Text Extraction Logic
def extract_text(file):
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text
    return file.read().decode("utf-8")

# -------------------------
# STAGE 1: Gemini Extraction
# -------------------------
if uploaded_file and user_query:
    if st.button("🔍 Step 1: Extract Data with Gemini"):
        with st.spinner("Gemini is analyzing the document..."):
            try:
                # Get text and limit to fit context window
                doc_text = extract_text(uploaded_file)
                limited_text = doc_text[:12000] 

                prompt = f"""
                Document Content:
                {limited_text}

                User Instruction:
                {user_query}

                Task: Extract the 5-8 most relevant key-value pairs as JSON.
                Respond ONLY with valid JSON.
                """

                # FIXED: Updated model name to gemini-3-flash
                response = client.models.generate_content(
                    model="gemini-3-flash",
                    contents=prompt
                )

                # Parsing response
                clean_json = response.text.strip().replace("```json", "").replace("```", "")
                try:
                    extracted_json = json.loads(clean_json)
                except:
                    extracted_json = {"raw_output": clean_json}

                # Store in session state for Stage 2
                st.session_state["doc_text"] = doc_text
                st.session_state["extracted_json"] = extracted_json
                st.session_state["user_query"] = user_query
                st.success("Extraction Successful!")

            except Exception as e:
                st.error("Failed to call Gemini API")
                st.exception(e)

# Display Output 1 (Structured Data)
if "extracted_json" in st.session_state:
    st.subheader("① Structured Data Extracted (JSON)")
    st.json(st.session_state["extracted_json"])
    st.markdown("---")

    # -------------------------
    # STAGE 2: n8n Automation
    # -------------------------
    st.subheader("📬 Step 2: Trigger Automation & Analysis")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        recipient_email = st.text_input("Recipient Email for Alerts", placeholder="manager@company.com")
    
    with col2:
        st.write("##") # Alignment
        trigger_n8n = st.button("🚀 Send Alert Mail & Get Analysis")

    if trigger_n8n:
        if not recipient_email:
            st.warning("Please provide a recipient email.")
        else:
            with st.spinner("Executing n8n Workflow..."):
                try:
                    payload = {
                        "text": st.session_state["doc_text"],
                        "extracted_json": st.session_state["extracted_json"],
                        "question": st.session_state["user_query"],
                        "recipient_email": recipient_email
                    }

                    # Call n8n Webhook
                    n8n_response = requests.post(
                        st.secrets["N8N_WEBHOOK_URL"],
                        json=payload
                    )
                    result = n8n_response.json()

                    # Output 2: Analytical Answer
                    st.subheader("② Final Analytical Answer")
                    st.info(result.get("final_answer", "No analysis provided by n8n."))

                    # Output 3: Email Body
                    st.subheader("③ Generated Email Body")
                    st.code(result.get("email_body", "No email draft generated."), language="markdown")

                    # Output 4: Status
                    st.subheader("④ Email Automation Status")
                    status = result.get("status", "Unknown")
                    if "SENT" in status.upper():
                        st.success(f"Status: {status}")
                    else:
                        st.warning(f"Status: {status}")

                except Exception as e:
                    st.error("Error connecting to n8n Webhook")
                    st.exception(e)
else:
    st.info("Upload a file and enter a query to begin.")