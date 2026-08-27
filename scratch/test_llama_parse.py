import os
import asyncio
from llama_parse import LlamaParse, ResultType
from dotenv import load_dotenv

load_dotenv()

async def test_parse():
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("LLAMA_CLOUD_API_KEY not found")
        return

    parser = LlamaParse(
        api_key=api_key,
        result_type=ResultType.MD,
        verbose=True,
        language="en",
    )
    
    # Just a small dummy file or existing one
    test_file = r"C:\Users\Ashutosh\OneDrive\Desktop\zenith\rag_project\Knowlegebase\rag_documents\rag_documents\11_FSSAI_EPCG_Trade_Compliance.md"
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return

    print(f"Starting parse of {test_file}...")
    try:
        documents = await parser.aload_data(test_file)
        print(f"Success! Got {len(documents)} document objects.")
        for i, doc in enumerate(documents):
            print(f"Page {i+1} length: {len(doc.text)}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_parse())
