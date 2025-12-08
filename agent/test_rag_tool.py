import asyncio
import os
import sys
import json
import dotenv

# Ensure the project root is in python path
# Assuming this file is in agent/test_rag_tool.py and we run from project root or inside agent
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agent.tool.local_search.RAG.rag_main import warmup_vanilla_rag
from agent.tool.local_search.rag_tool import VanillaRAGSearchTool
from agent.tool.local_search.RAG.rag_main import _DEFAULT_SERVICE

dotenv.load_dotenv()
warmup_vanilla_rag(auto_build=True)

async def main():
    print("Forcing RAG build from shards...")
    #build_result = await _DEFAULT_SERVICE.build_from_shards()
    #print(f"Build result: {build_result}")

    print("Initializing VanillaRAGSearchTool...")
    tool = VanillaRAGSearchTool()
    
    query = "Timeline of representative open-source and closed-source reasoning models"
    print(f"Running query: '{query}'")
    
    # The tool's _arun method handles the async execution
    result = await tool._arun(query)
    
    print("\n--- Result (Raw JSON length) ---")
    print(len(result))
    
    try:
        parsed = json.loads(result)
        print(f"Number of hits: {len(parsed)}")
        for i, item in enumerate(parsed):
            images = item.get("images", [])
            print(f"Hit {i}: Source={item.get('source')} | Images found: {len(images)}")
            for img in images:
                path = img.get("path")
                data_url = img.get("data_url")
                print(f"  - Path: {path}")
                print(f"  - Data URL length: {len(data_url) if data_url else 0}")
                if not data_url:
                    print("    [WARNING] Data URL is empty!")
                else:
                    print("    [SUCCESS] Data URL present.")
    except json.JSONDecodeError:
        print("Result is not valid JSON")
        print(result)

    print("--------------")

    if "No relevant passages found" in result:
        print("Test Failed: No results found. Ensure PDF is indexed.")
    else:
        print("Test Passed: Results returned.")

if __name__ == "__main__":
    asyncio.run(main())
