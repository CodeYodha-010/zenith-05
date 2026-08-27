import requests
from django.conf import settings
import time
import logging
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rag_app.prompts import SYSTEM_PROMPT

logger = logging.getLogger('rag_pipeline')


class NVIDIALLMService:
    """LLM chat/generation service backed by OpenRouter (OpenAI-compatible API).

    Replaces the previous NVIDIA-hosted LLM. Embeddings (nemotron-3-embed-1b)
    and OCR remain on NVIDIA.
    """

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_url = settings.OPENROUTER_API_URL
        self.model = settings.OPENROUTER_MODEL
    
    def get_llamaindex_llm(self):
        """Returns a LlamaIndex-compatible LLM object pointed at OpenRouter."""
        try:
            from llama_index.llms.openai_like import OpenAILike
            return OpenAILike(
                model=self.model,
                api_key=self.api_key,
                api_base=self.api_url,
                is_chat_model=True,
                temperature=0.4,
                max_tokens=2000,
                timeout=300.0,
            )
        except ImportError:
            logger.error("❌ llama-index-llms-openai-like not installed.")
            return None
    
    def generate(self, prompt, system_prompt=None, temperature=0.4, max_tokens=1024, retry_count=3):
        # IMPROVEMENT: Increase temperature from 0.1 to 0.4
        # WHY: Trade compliance expert persona needs more helpfulness and detail
        # Low temperature (0.1) makes answers too robotic and generic
        # Higher temperature (0.4) encourages helpful, detailed, varied responses
        # Good balance between consistency and helpfulness for RAG applications
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    f"{self.api_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['choices'][0]['message']['content'].strip()
                
                error_data = response.json()
                error_detail = error_data.get('detail', str(error_data))
                
                if 'DEGRADED' in str(error_detail) or response.status_code == 503:
                    print(f"Model degraded, attempt {attempt + 1}/{retry_count}, waiting...")
                    time.sleep(3)
                    continue
                
                if response.status_code == 401:
                    raise Exception("Invalid API key. Please check OPENROUTER_API_KEY in .env")
                
                if response.status_code == 429:
                    raise Exception("Rate limit exceeded. Please wait and try again.")
                
                if 'not found' in str(error_detail).lower():
                    raise Exception(f"Model not found: {self.model}. Please check available models.")
                
                raise Exception(f"LLM API error: {error_detail}")
                
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    print(f"Request timeout, retrying...")
                    time.sleep(2)
                    continue
                raise Exception("Request timeout. Please try again.")
            except requests.exceptions.RequestException as e:
                if attempt < retry_count - 1:
                    print(f"Request error: {e}, retrying...")
                    time.sleep(2)
                    continue
                raise Exception(f"Connection error: {str(e)}")
        
        raise Exception("Model is temporarily unavailable. Please try again later.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def generate_async(self, prompt, max_tokens=1024):
        """Asynchronous LLM generation for fact extraction."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as client:
            try:
                resp = await client.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                )
                
                # Robust error handling
                if resp.status_code == 429:
                    logger.warning("⚠️ [RATE LIMIT] NVIDIA API returned 429. Sleeping...")
                    await asyncio.sleep(5)
                    resp.raise_for_status()
                
                if resp.status_code != 200:
                    error_msg = f"LLM API Error {resp.status_code}: {resp.text[:200]}"
                    logger.error(f"❌ {error_msg}")
                    raise httpx.HTTPStatusError(error_msg, request=resp.request, response=resp)

                data = resp.json()
                return data["choices"][0]["message"]["content"]
                
            except httpx.HTTPStatusError as e:
                # Let tenacity retry
                raise e
            except Exception as e:
                logger.error(f"❌ Async LLM failed: {e}")
                raise e
    
    def summarize(self, text, max_length=200):
        prompt = f"""Summarize the following text in 1-2 sentences. Be concise and capture the main topic.

Text:
{text[:3000]}

Summary:"""
        
        return self.generate(prompt, max_tokens=max_length)
    
    def generate_answer(self, query, context, source_docs):
        system_prompt = SYSTEM_PROMPT

        sources_text = "\n".join([f"- {doc}" for doc in source_docs]) if source_docs else "No specific documents available"

        prompt = f"""User's Question: {query}

Available Information from Knowledge Base:
{sources_text}

Document Content:
{context}

INSTRUCTIONS:
- First, provide a CLEAR and SIMPLE answer to the user's question
- Use easy-to-understand language
- Use bullet points or numbers for multiple items
- If you can't find the answer in the documents, clearly state that

Your Answer:"""

        answer = self.generate(prompt, system_prompt=system_prompt, max_tokens=1200)

        return {
            "answer": answer,
            "sources": source_docs
        }

    def generate_web_answer(self, query, web_results):
        system_prompt = SYSTEM_PROMPT

        web_context = ""
        for i, r in enumerate(web_results, 1):
            web_context += f"\n{i}. {r.get('title', 'N/A')}\n   {r.get('snippet', 'N/A')}\n   URL: {r.get('url', 'N/A')}\n"

        prompt = f"""User Question: {query}

Web Search Results:
{web_context}

Please provide a clear, easy-to-understand answer to the user's question based on these web results. Use bullet points if there are multiple items."""

        answer = self.generate(prompt, system_prompt=system_prompt, max_tokens=1000)
        
        sources = [r.get('title', 'Web') for r in web_results]
        
        return {
            "answer": answer,
            "sources": sources
        }
    
    def generate_stream(self, prompt, system_prompt=None, temperature=0.4, max_tokens=1024):
        """
        Generate text with streaming - yields chunks as they arrive.
        
        Yields:
            str: Chunks of text as they arrive from the API
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=90,
                stream=True
            )
            
            if response.status_code != 200:
                logger.error(f"Streaming API error: {response.status_code}")
                return
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                line = line.decode('utf-8')
                
                # Skip non-data lines
                if not line.startswith('data: '):
                    continue
                
                # Remove 'data: ' prefix
                data_str = line[6:]
                
                # Check for end of stream
                if data_str.strip() == '[DONE]':
                    break
                
                try:
                    import json
                    data = json.loads(data_str)
                    
                    # Extract content from delta
                    choices = data.get('choices', [])
                    if choices:
                        delta = choices[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                            
                except json.JSONDecodeError:
                    continue
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming request error: {e}")
            return
