# frontend/app.py
import streamlit as st
import requests
import time

st.set_page_config(page_title="Document Processing Agent", layout="wide")
st.title("Document Processing Agent")
st.write("Upload your invoice (PDF or Image) to extract, validate, and send to ERP automatically.")


uploaded = st.file_uploader("Upload Invoice", type=["pdf", "jpg", "jpeg", "png"])

if uploaded:
    with st.spinner("Processing your invoice..."):
        # Build multipart/form-data correctly:
        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
        try:
            response = requests.post("http://127.0.0.1:8000/process-invoice/", files=files, timeout=60)
        except Exception as e:
            st.error(f"Request failed: {e}")
            st.stop()

    if response.status_code == 200:
        result = response.json()
        if result.get("status") == "success":
            st.success("Invoice Processed Successfully!")
            st.json(result.get("data"))
        else:
            st.error(f" Error: {result.get('detail') or result.get('message')}")
    else:
        st.error(f"Backend error. Status {response.status_code}: {response.text}")
st.write("##### Time is money . Save both with smart automation...")


# ......................Chat Interface for Natural Language Queries...................................

BACKEND_URL_CHAT = "http://localhost:8000/chatbot/query/"  # Adjust if running on another host/port

st.markdown("### Ask Questions About Invoices & Company Finance")

# Initialize history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]

    if role == "user":
        st.markdown(f"<div class='user-bubble'>{content}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='bot-bubble'>{content}</div>", unsafe_allow_html=True)

# Chat input box
query = st.chat_input("Ask anything... For example: 'Total revenue this month?'")

def typing_effect(text):
    """Realistic bot typing animation"""
    placeholder = st.empty()
    typed = ""
    for ch in text:
        typed += ch
        placeholder.markdown(f"<div class='bot-bubble'>{typed}</div>", unsafe_allow_html=True)
        time.sleep(0.005)
    placeholder.markdown(f"<div class='bot-bubble'>{typed}</div>", unsafe_allow_html=True)

if query:
    # Store and show user message
    st.session_state.messages.append({"role": "user", "content": query})
    st.markdown(f"<div class='user-bubble'>{query}</div>", unsafe_allow_html=True)

    # Backend Request
    try:
        with st.spinner("Analyzing database..."):
            res = requests.post(BACKEND_URL_CHAT, json={"question": query})
            res_data = res.json()

            if res_data.get("status") == "success":
                bot_reply = res_data["answer"]
            else:
                bot_reply = "Unable to fetch data or database empty."

    except Exception as e:
        bot_reply = f"Backend Error: {e}"

    # Typing effect response
    typing_effect(bot_reply)

    # Save to history
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
