import os
import sys
import asyncio
import dotenv
dotenv.load_dotenv()

# Add the current directory to sys.path to allow importing the agent package
sys.path.append(os.getcwd())

from agent.agent_runner import run_query, initialize

def main():
    # Simple query to test memory and basic response
    task = initialize()
    if task:
        asyncio.run(task)
    try:
        """
        print("\n--- Follow Up ---")
        query3 = "call tool agent let it use vanilla rag tool search what the overview of Fraud Examination Fundamentals?(if can't find facts by using this tools just answer no relative facts found do not use other tools)"
        print(f"Running query: '{query3}'")
        result3 = run_query(query3)
        print(result3.get("output"))
        """
        
        print("\n--- Follow Up ---")
        query4 = "dont use tool answer what is the overview of Fraud Examination Fundamentals? (you need use remembered facts to answer this question is not include in remembered facts output u cant find it in remembered facts)"
        print(f"Running query: '{query4}'")
        result4 = run_query(query4)
        print(result4.get("output"))
        
        print("\n--- Follow Up ---")
        query5 = "what is my previous questions and your answers?"
        result5 = run_query(query5)
        print(result5.get("output"))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
