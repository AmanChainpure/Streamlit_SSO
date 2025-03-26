import openai
import os
import dotenv
import streamlit as st

dotenv.load_dotenv()

azure_openai_endpoint = os.getenv("OPENAI_ENDPOINT")
azure_openai_key = os.getenv("OPENAI_API_KEY")
azure_openai_api_version = os.getenv("OPENAI_API_VERSION")
gpt_model = os.getenv("AZURE_OPENAI_MODEL")

temperature = os.getenv("TEMPERATURE")
max_token = os.getenv("MAX_TOKENS")
frequency_penalty = os.getenv("FREQUENCY_PENALTY")
presence_penalty = os.getenv("PRESENCE_PENALTY")
top_p = os.getenv("TOP_P")
seed = os.getenv("SEED")


@st.cache_resource(show_spinner=True)
def get_openai_client():
    return openai.AzureOpenAI(
        azure_endpoint=azure_openai_endpoint,
        api_key=azure_openai_key,
        api_version=azure_openai_api_version,
    )


def call_llm_azure_openai_stream(context):
    try:
        client = get_openai_client()

        response_stream = client.chat.completions.create(
            model=gpt_model,
            messages=context,
            temperature=int(temperature),
            max_tokens=int(max_token),
            frequency_penalty=int(frequency_penalty),
            presence_penalty=int(presence_penalty),
            top_p=int(top_p),
            seed=int(seed),
            stream=True
        )

        for chunk in response_stream:
            delta = chunk.choices[0].delta
            content_piece = delta.content if hasattr(delta, "content") else ""
            if content_piece:
                yield content_piece

    except Exception as e:
        print(f"Streaming error: {e}")
        yield "Sorry, I couldn't process your request right now."
