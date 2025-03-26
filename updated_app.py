import streamlit as st
import time
import uuid
import json
import fitz
import logging

from backend.helper import icon_for_webpage, update_context, count_questions_usr, count_tokens
from frontend.page_layout import create_page_basic_dark, create_page_basic_light
from backend.blobdb import (
    show_usr_log_data,
    insert_usr_log_data,
    save_pdf_extracted_txt_data,
    download_and_read_chathistory_from_azure_blob,
    save_chat_history_in_blob
)
from backend.llm import call_llm_azure_openai_stream
from authentication.auth import authenticate

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_MESSAGES = 30  # For context trimming

def page_setup():
    st.set_page_config(
        page_title="ChatGPT",
        page_icon=icon_for_webpage(),
        layout="wide",
        initial_sidebar_state="auto",
    )

def theme_for_page(username):
    theme = "Light"
    try:
        if theme == "Dark":
            return create_page_basic_dark()
        else:
            return create_page_basic_light()
    except Exception as e:
        logger.error(f"Theme error: {e}")
        st.write("Error in loading the interface!")

def process_document_upload(uploaded_files, username):
    try:
        if not isinstance(uploaded_files, list):
            uploaded_files = [uploaded_files]

        extracted_text = ""
        for uploaded_file in uploaded_files:
            logger.info(f"Uploaded file: {uploaded_file.name}")
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"

            text_token_count = count_tokens(text)
            logger.info(f"Text token count: {text_token_count}")

            if text_token_count > 50000:
                st.warning("Please upload a document with fewer pages")
                return "default text"
            else:
                save_pdf_extracted_txt_data(text, username, uploaded_file.name)
                st.success("Process completed successfully.")
                logger.info("PDF data saved to blob")
                extracted_text += text

        return extracted_text

    except Exception as e:
        logger.error(f"File upload error: {e}")
        st.sidebar.write("Error in opening the file.")
        return "default text"

@st.dialog("Confidentiality Agreement")
def confidentiality_agreement():
    st.write("""By accessing this AI assistance, you agree to the following terms:
1) All information accessed through the system is confidential.
2) You will not share information obtained through this system with unauthorized parties.
3) You will use this system only for legitimate business purposes related to underwriting activities.
4) All interactions with the system are logged and may be monitored for compliance.
5) Violation of these terms may result in disciplinary action.
""")
    agree = st.checkbox("I have read and agree to the terms of this agreement")
    if agree:
        if st.button("Submit"):
            st.session_state.agreement = "Agreed"
            st.rerun()

def clear_chat_history():
    st.session_state["session_id"] = str(uuid.uuid4()) + str(time.time())
    st.session_state["context"] = update_context()
    st.session_state["input_token_count"] = 0
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": f"Hello, {st.session_state.get('username', 'User')}! How may I assist you today?",
        }
    ]

def main():
    if "context" not in st.session_state:
        st.session_state["context"] = update_context()
    if "extracted_text" not in st.session_state:
        st.session_state["extracted_text"] = ""
    if "Chatbot" not in st.session_state:
        st.session_state.chatbot = []
    if "ChatbotAnswer" not in st.session_state:
        st.session_state.chatbotanswer = []

    page_setup()

    with st.sidebar:
        user = authenticate()
        if user:
            st.session_state["username"] = user
            if "agreement" not in st.session_state:
                st.write("Please read and agree to the confidentiality agreement before proceeding.")
                if st.button("View"):
                    confidentiality_agreement()

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4()) + str(time.time())
    if "input_token_count" not in st.session_state:
        st.session_state["input_token_count"] = 0

    username = st.session_state.get("username", "")
    uploaded_files = None

    try:
        if username and "agreement" in st.session_state:
            with st.sidebar:
                uploaded_files = st.file_uploader(
                    "Choose new files",
                    accept_multiple_files=False,
                    help="Upload PDF files only",
                    type=["pdf"],
                )

        if uploaded_files:
            if st.button("Upload", use_container_width=True, type="primary"):
                st.session_state["extracted_text"] = ""
                st.session_state["context"] = update_context()
                extracted_text = process_document_upload(uploaded_files, username)
                if not extracted_text:
                    extracted_text = "Default text"

                st.session_state["extracted_text"] += extracted_text
                st.session_state["context"].append({
                    "role": "system",
                    "content": st.session_state["extracted_text"]
                })

    except Exception as e:
        logger.error(f"Error during file upload: {e}")
        st.sidebar.write("Error in processing document upload.")

    if username and "agreement" in st.session_state:
        user_query = theme_for_page(username)

        if "messages" not in st.session_state:
            st.session_state["messages"] = [{
                "role": "assistant",
                "content": f"Hello, {username}! How may I assist you today?",
            }]

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_query:
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            st.session_state["context"].append({
                "role": "user",
                "content": user_query
            })

            # Trim context for performance
            if len(st.session_state["context"]) > MAX_MESSAGES:
                st.session_state["context"] = st.session_state["context"][-MAX_MESSAGES:]

            with st.spinner("Typing..."):
                with st.chat_message("assistant"):
                    full_response = ""

                    def stream_response():
                        nonlocal full_response
                        for chunk in call_llm_azure_openai_stream(st.session_state["context"]):
                            full_response += chunk
                            yield chunk

                    st.write_stream(stream_response)

                    save_chat_history_in_blob(username, user_query, full_response, st.session_state.session_id)
                    st.session_state["input_token_count"] += count_tokens(user_query)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.session_state.context.append({"role": "assistant", "content": full_response})
                    insert_usr_log_data(username, user_query, full_response, 0, 0, 0)

    try:
        st.sidebar.button(
            "New Chat",
            on_click=clear_chat_history,
            type="primary",
            use_container_width=True,
        )
    except Exception as e:
        logger.error(f"New chat session error: {e}")
        st.sidebar.write("Error starting new chat.")

    with st.sidebar:
        history_button = st.button("Chat History", type='primary', use_container_width=True)
        if history_button:
            st.write("**Chat History**")
            try:
                chat_history = download_and_read_chathistory_from_azure_blob(username)
                for session in chat_history:
                    st.sidebar.markdown(f"**Title: {session['title']}**")
                    for conversation in session["conversations"]:
                        st.session_state.chatbot.append(conversation)
                        st.sidebar.markdown(f"**Time:** {conversation.get('Time')}**")
                        st.sidebar.markdown(f"**User:** {conversation.get('User')}**")
                        st.session_state.chatbotanswer.append({"Chatbot": conversation.get('Chatbot')})
                        st.sidebar.write(f"**Assistant:** {conversation.get('Chatbot')}")
            except Exception as e:
                logger.warning(f"No chat history: {e}")
                st.sidebar.write("No chat history found. Start a conversation!")

if __name__ == "__main__":
    main()
