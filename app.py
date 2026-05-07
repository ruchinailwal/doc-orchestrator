import streamlit as st
import pdfplumber
import json
import requests
from google import genai

# Gemini Client
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

# Streamlit UI
st.title("AI-Powered Document Orchestrator")
st.write(
    "Upload a document, ask a question, and get AI-powered insights!"
)

# Upload + Query
uploaded_file = st.file_uploader(
    "Upload your document",
    type=["pdf", "txt"]
)

user_query = st.text_input(
    "Ask a question about the document"
)

# Function to extract text
def extract_text(file):

    if file.type == "application/pdf":

        with pdfplumber.open(file) as pdf:

            text = "\n".join(
                page.extract_text() or ""
                for page in pdf.pages
            )

        return text

    return file.read().decode("utf-8")


# -------------------------
# Stage 1 - Extract Data
# -------------------------
if uploaded_file and user_query:

    if st.button("Extract Data"):

        with st.spinner("Extracting data with Gemini..."):

            try:

                # Extract text
                doc_text = extract_text(uploaded_file)

                # Limit text size
                limited_text = doc_text[:10000]

                # Prompt
                prompt = f"""
                Document:
                {limited_text}

                User Question:
                {user_query}

                Extract the 5-8 most relevant key-value pairs
                as JSON to answer the question.

                Respond ONLY with a valid JSON object.

                Example:
                {{
                    "key1": "value1",
                    "key2": "value2"
                }}
                """

                # Gemini API Call
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt
                )

                # Clean Gemini response
                clean = (
                    response.text
                    .strip()
                    .replace("```json", "")
                    .replace("```", "")
                )

                # Convert to JSON safely
                try:
                    extracted_json = json.loads(clean)

                except:
                    extracted_json = {
                        "response": clean
                    }

                # Save data in session
                st.session_state["doc_text"] = doc_text
                st.session_state["extracted_json"] = extracted_json
                st.session_state["user_query"] = user_query

                st.success("Data extraction completed!")

            except Exception as e:

                st.error("Gemini API Error")
                st.exception(e)

        # Display extracted JSON
        if "extracted_json" in st.session_state:

            st.subheader(
                "① Structured Data Extracted (JSON)"
            )

            st.json(
                st.session_state["extracted_json"]
            )


# -------------------------
# Stage 2 - Send to n8n
# -------------------------
if "extracted_json" in st.session_state:

    st.subheader("Send Alert Email via n8n")

    recipient_email = st.text_input(
        "Enter Recipient Email ID"
    )

    if st.button("Send Alert Mail"):

        with st.spinner("Sending to n8n..."):

            try:

                payload = {
                    "text": st.session_state["doc_text"],
                    "extracted_json": st.session_state["extracted_json"],
                    "question": st.session_state["user_query"],
                    "recipient_email": recipient_email
                }

                response = requests.post(
                    st.secrets["N8N_WEBHOOK_URL"],
                    json=payload
                )

                result = response.json()

                # Output 1
                st.subheader(
                    "② Final Analytical Answer"
                )

                st.write(
                    result.get(
                        "final_answer",
                        "No answer returned"
                    )
                )

                # Output 2
                st.subheader(
                    "③ Generated Email Body"
                )

                st.write(
                    result.get(
                        "email_body",
                        "Email was not sent - condition not met"
                    )
                )

                # Output 3
                st.subheader(
                    "④ Email Automation Status"
                )

                status = result.get(
                    "status",
                    "Unknown"
                )

                if "SENT" in status.upper():

                    st.success(
                        f"Alert Email Status: {status}"
                    )

                else:

                    st.warning(
                        f"Status: {status}"
                    )

            except Exception as e:

                st.error("n8n Webhook Error")
                st.exception(e)