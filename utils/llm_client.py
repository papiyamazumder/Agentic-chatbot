"""
Centralized LLM Client Factory — supports Groq and Local Ollama.
Set LLM_PROVIDER in .env to 'groq' or 'ollama'.
"""
import os
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class OllamaClient:
    """Mock client wrapper for Ollama to match Groq's interface partially."""
    def __init__(self, base_url="http://localhost:11434/api/chat"):
        self.base_url = base_url
        self.model = os.getenv("OLLAMA_MODEL") or "llama3"

    class Chat:
        def __init__(self, parent):
            self.parent = parent
            self.completions = self.Completions(parent)

        class Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, model, messages, temperature=0.7, max_tokens=1024):
                payload = {
                    "model": model or self.parent.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
                response = requests.post(self.parent.base_url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Wrap in a mock response object to match Groq's structure
                class MockMessage:
                    def __init__(self, content):
                        self.content = content
                
                class MockChoice:
                    def __init__(self, content):
                        self.message = MockMessage(content)
                
                class MockResponse:
                    def __init__(self, content):
                        self.choices = [MockChoice(content)]
                
                return MockResponse(data.get("message", {}).get("content", ""))

    def __init__(self, base_url="http://localhost:11434/api/chat"):
        self.base_url = base_url
        self.model = os.getenv("OLLAMA_MODEL") or "llama3"
        self.chat = self.Chat(self)

def get_llm_client():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    
    if provider == "ollama":
        return OllamaClient()
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env file, and provider is 'groq'")
        return Groq(api_key=api_key)

def get_model_name():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "ollama":
        return os.getenv("OLLAMA_MODEL") or "llama3"
    else:
        return os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"
