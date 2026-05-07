import streamlit as st
import pdfplumber
import json
import requests
from google import genai

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.title("AI-Powered Document Orchestrator")
st.write("Upload a document, ask a question, and get AI-powered insights!")

uploaded_file = st.file_uploader("Upload your document", type=["pdf", "txt"])
user_query = st.text_input("Ask a question about the document")

def extract_text(file):
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    return file.read().decode("utf-8")

if uploaded_file and user_query:
    if st.button("Extract Data"):
        with st.spinner("Extracting data with Gemini..."):
            doc_text = extract_text(uploaded_file)
            prompt = f"""
            Document: {doc_text[:4000]}
            User Question: {user_query}
            Extract the 5-8 most relevant key-value pairs as JSON to answer the question.
            Respond ONLY with a valid JSON object. No extra text.
            Example: {{"key1": "value1", "key2": "value2"}}
            """
            response = client.models.generate_content(
                model="gemini-1.5-flash-latest",
                contents=prompt
            )
            clean = response.text.strip().replace("```json","").replace("```","")
            extracted_json = json.loads(clean)
            st.session_state["doc_text"] = doc_text
            st.session_state["extracted_json"] = extracted_json
            st.session_state["user_query"] = user_query

        st.subheader("① Structured Data Extracted (JSON)")
        st.json(st.session_state["extracted_json"])

if "extracted_json" in st.session_state:
    st.subheader("Send Alert Email via n8n")
    recipient_email = st.text_input("Enter Recipient Email ID")

    if st.button("Send Alert Mail"):
        with st.spinner("Sending to n8n..."):
            payload = {
                "text": st.session_state["doc_text"],
                "extracted_json": st.session_state["extracted_json"],
                "question": st.session_state["user_query"],
                "recipient_email": recipient_email
            }
            response = requests.post(st.secrets["N8N_WEBHOOK_URL"], json=payload)
            result = response.json()

        st.subheader("② Final Analytical Answer")
        st.write(result.get("final_answer", "No answer returned"))

        st.subheader("③ Generated Email Body")
        st.write(result.get("email_body", "Email was not sent - condition not met"))

        st.subheader("④ Email Automation Status")
        status = result.get("status", "Unknown")
        if "SENT" in status.upper():
            st.success(f"Alert Email Status: {status}")
        else:
            st.warning(f"Status: {status}")