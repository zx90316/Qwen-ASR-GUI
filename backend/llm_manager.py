import os
import requests
from openai import OpenAI
from google import genai
from typing import List, Dict, Any

class LLMManager:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # Initialize clients
        self.openai_client = None
        if self.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                print(f"Failed to initialize OpenAI client: {e}")

        self.gemini_client = None
        if self.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"Failed to configure Gemini: {e}")

    def get_available_providers_and_models(self) -> Dict[str, List[str]]:
        """回傳目前可用的 providers 與其對應的 models"""
        providers = {}

        # 1. Ollama (Always check if available locally)
        try:
            resp = requests.get(f"{self.ollama_host}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = [model['name'] for model in data.get('models', [])]
                if models:
                    providers['Ollama'] = models
        except Exception:
            pass  # Ollama not running or reachable

        # 2. OpenAI
        if self.openai_client:
            providers['OpenAI'] = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            # To fetch dynamically, could use self.openai_client.models.list() but usually it's better to offer common ones.

        # 3. Gemini
        if self.gemini_client:
            # google-genai doesn't easily return a clean list of just text models immediately without filtering thoroughly, 
            # so providing the common ones is better, or we can use standard known names
            providers['Gemini'] = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

        return providers

    def build_system_prompt(self, action: str) -> str:
        """建立共用的 System Prompt"""
        if action == "polish":
            return (
                "你是一個專業的字幕編輯。請幫我「潤飾」以下傳入的字幕句子，"
                "修正錯字、改善語句流暢度與標點符號，但必須「保持原意」並且「字數相近」。"
                "請直接回答潤飾後的句子，不要包含任何額外的解釋或說明，也不要加上對話引號。"
                "若覺得不需要潤飾，請直接回傳原句。"
            )
        elif action == "translate":
            return (
                "你是一個專業的翻譯專家。請幫我將以下傳入的字幕句子翻譯成「繁體中文」。"
                "請確保翻譯自然流暢，適合做為影片字幕。"
                "請直接回答翻譯後的句子，不要包含任何額外的解釋或說明，也不要加上對話引號。"
            )
        else:
            return "請處理以下文字。"

    def process_sentence(self, text: str, provider: str, model: str, action: str, custom_prompt: str = "") -> str:
        """處理單一句句話 (潤飾或翻譯)"""
        if not text.strip():
            return text

        system_prompt = custom_prompt.strip() if custom_prompt and custom_prompt.strip() else self.build_system_prompt(action)

        if provider == "Ollama":
            return self._process_ollama(text, model, system_prompt)
        elif provider == "OpenAI":
            return self._process_openai(text, model, system_prompt)
        elif provider == "Gemini":
            return self._process_gemini(text, model, system_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _process_ollama(self, text: str, model: str, system_prompt: str) -> str:
        url = f"{self.ollama_host}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": False
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get('message', {}).get('content', '').strip()
        except requests.exceptions.RequestException as e:
            print(f"Ollama API Error: {e}")
            return text

    def _process_openai(self, text: str, model: str, system_prompt: str) -> str:
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized.")
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return text

    def _process_gemini(self, text: str, model: str, system_prompt: str) -> str:
        if not self.gemini_client:
            raise ValueError("Gemini client is not configured.")
        try:
            response = self.gemini_client.models.generate_content(
                model=model,
                contents=text,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                ),
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return text

llm_manager = LLMManager()
