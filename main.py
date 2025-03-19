import streamlit as st
from openai import OpenAI

import os
os.environ['OPENAI_API_KEY'] = 'sk-proj-key'

# Simulated user credentials (Replace with real authentication)
VALID_CREDENTIALS = {"admin": "password123", "user": "test123"}

# Initialize OpenAI client
client = OpenAI()

# Session state for authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Sidebar - Authentication
st.sidebar.title("Login")
username = st.sidebar.text_input("User:")
password = st.sidebar.text_input("Password:", type="password", key="password", help="Enter your password securely")
login_button = st.sidebar.button("Login")

if login_button:
    if username in VALID_CREDENTIALS and VALID_CREDENTIALS[username] == password:
        st.session_state.authenticated = True
        st.sidebar.success("User authenticated successfully.")
    else:
        st.sidebar.error("Invalid username or password.")

# Main Chat UI - Only visible after authentication
if st.session_state.authenticated:
    st.title("Chat with ChatGPT")

    # Initialize conversation history if not present
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]

    # Display chat history properly
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        elif msg["role"] == "assistant":
            with st.chat_message("assistant"):
                st.write(msg["content"])

    # User input for chat
    user_input = st.chat_input("Ask a question...")

    if user_input:
        # Show user input in chat UI
        with st.chat_message("user"):
            st.write(user_input)

        # Append user message to session state
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Generate AI response with loading indicator
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):  # <--- Loading indicator
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=st.session_state.messages,
                    max_tokens=500
                )
                bot_response = completion.choices[0].message.content

            # Display assistant response
            st.write(bot_response)

        # Append assistant response to session state
        st.session_state.messages.append({"role": "assistant", "content": bot_response})
else:
    st.warning("Please log in to access the chat.")
