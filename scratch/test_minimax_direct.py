import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def test_minimax():
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_LLM_API_KEY")
    )
    
    print("Sending request to MiniMax...")
    completion = client.chat.completions.create(
        model="minimaxai/minimax-m2.5",
        messages=[{"role": "user", "content": "Say hello!"}],
        temperature=1,
        max_tokens=100
    )
    
    print("Response:")
    print(completion.choices[0].message.content)

if __name__ == "__main__":
    test_minimax()
