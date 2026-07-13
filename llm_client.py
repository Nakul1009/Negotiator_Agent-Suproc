from langchain_nvidia_ai_endpoints import ChatNVIDIA
import os
from dotenv import load_dotenv
load_dotenv()
def llm_call(prompt):
    client = ChatNVIDIA(
    model="nvidia/nemotron-3-ultra-550b-a55b",
    api_key= os.getenv("NVIDIA_API_KEY"), 
    temperature=1,
    top_p=0.95,
    max_tokens=16384,
    chat_template_kwargs={"enable_thinking":True},
    )

    return client.invoke(prompt).content