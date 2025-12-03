
import streamlit as st
import requests
import time

BACKEND_BASE = "http://127.0.0.1:8000"
UPLOAD_URL = f"{BACKEND_BASE}/process-invoice/"
CHAT_URL = f"{BACKEND_BASE}/chatbot/query/"
REGISTER_URL = f"{BACKEND_BASE}/auth/register"
LOGIN_URL = f"{BACKEND_BASE}/auth/login"

st.set_page_config(page_title="Document Processing Agent", layout="wide")


# --------------------------------------------------------------------
#  SESSION HELPERS
# --------------------------------------------------------------------
def save_token(token: str):
    st.session_state["token"] = token

def is_logged_in():
    return "token" in st.session_state and st.session_state["token"] is not None

def headers_auth():
    return {"Authorization": f"Bearer {st.session_state['token']}"}


# Prevent reprocessing
if "last_uploaded_file_hash" not in st.session_state:
    st.session_state["last_uploaded_file_hash"] = None


# --------------------------------------------------------------------
# LOGIN / REGISTER
# --------------------------------------------------------------------
if not is_logged_in():

    st.markdown("<h1 style='text-align:center;'>🔐 Welcome</h1>", unsafe_allow_html=True)
    tab_login, tab_register = st.tabs(["Login", "Register"])

    # LOGIN
    with tab_login:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):
            res = requests.post(LOGIN_URL, json={"username": username, "password": password})
            try:
                data = res.json()
            except:
                st.error(f"Server error: {res.text}")
                st.stop()

            if res.status_code == 200 and data.get("access_token"):
                save_token(data["access_token"])
                st.success("Login successful! Reloading...")
                st.rerun()   # FIXED
            else:
                st.error(data.get("detail", "Login failed"))

    # REGISTER
    with tab_register:
        r_user = st.text_input("New Username")
        r_email = st.text_input("Email (optional)")
        r_pass = st.text_input("New Password", type="password")

        if st.button("Register"):
            res = requests.post(REGISTER_URL, json={
                "username": r_user,
                "password": r_pass,
                "email": r_email
            })
            try:
                data = res.json()
            except:
                st.error(f"Server error: {res.text}")
                st.stop()

            if res.status_code == 200:
                st.success("Registration successful! Please login.")
            else:
                st.error(data.get("detail", "Registration failed"))

    st.stop()


# --------------------------------------------------------------------
# MAIN UI
# --------------------------------------------------------------------
st.title("📄 Document Processing Agent")
st.write("Secure – Multi-User Invoice Processing + Smart Chatbot ")

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()


# --------------------------------------------------------------------
# INVOICE UPLOAD (NO REPROCESSING)
# --------------------------------------------------------------------
uploaded = st.file_uploader("Upload Invoice", type=["pdf", "jpg", "jpeg", "png"])

if uploaded:
    file_bytes = uploaded.getvalue()
    file_hash = hash(file_bytes)

    # Prevent reprocessing if same file
    if st.session_state["last_uploaded_file_hash"] == file_hash:
        st.info("This invoice was already processed. Not sending again.")
    else:
        with st.spinner("Processing your invoice..."):
            files = {"file": (uploaded.name, file_bytes, uploaded.type)}

            try:
                res = requests.post(UPLOAD_URL, files=files, headers=headers_auth())
                data = res.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

        if res.status_code == 200:
            st.success("Invoice Processed Successfully!")
            st.json(data)

            # Save hash so we never reprocess same invoice again
            st.session_state["last_uploaded_file_hash"] = file_hash
        else:
            st.error(data.get("detail", res.text))


# --------------------------------------------------------------------
# CHATBOT UI (NO REPROCESSING)
# --------------------------------------------------------------------

st.markdown("###  Ask Anything About Your Invoices")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**Bot:** {msg['content']}")


query = st.chat_input("Ask anything about your invoices...")

def typing_effect(text):
    placeholder = st.empty()
    typed = ""
    for ch in text:
        typed += ch
        placeholder.markdown(f"**Bot:** {typed}")
        time.sleep(0.004)
    placeholder.markdown(f"**Bot:** {text}")


if query:
    st.session_state.messages.append({"role": "user", "content": query})
    st.markdown(f"**You:** {query}")

    try:
        with st.spinner("Thinking..."):
            res = requests.post(
                CHAT_URL,
                json={"question": query},
                headers=headers_auth()
            )

            try:
                data = res.json()
                bot_reply = data.get("answer", "No response from server")
            except:
                bot_reply = f"Server returned: {res.text}"

    except Exception as e:
        bot_reply = f"Error: {e}"

    typing_effect(bot_reply)
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})

