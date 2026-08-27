import os
import django
import sys
import asyncio
import logging

# Setup Django
sys.path.append('C:\\Users\\Ashutosh\\OneDrive\\Desktop\\zenith\\rag_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_project.settings')
django.setup()

from rag_app.services.service_registry import get_agent

async def test_agent_async():
    print("START: Initializing Native Async Agent via Service Registry...")
    try:
        agent_service = get_agent()
        print("SUCCESS: Agent Initialized.")
        
        question = "What are the latest export rules for wheat in India for 2025?"
        print(f"QUERY: {question}")
        
        # Await the async ask() method
        response = await agent_service.ask(question, region="india")
        
        if response.get('success'):
            print("\n" + "="*50)
            print("AGENT ANSWER:")
            print("="*50)
            print(response.get('answer'))
            print("="*50)
        else:
            print(f"ERROR: {response.get('error')}")
            
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_async())
