from .agent_runner import run_query
import sys
import dotenv

dotenv.load_dotenv()

def agent(query: str, session_id: str = "default"):
    
    print(f"\nQuery: {query}")
    print(f"Session ID: {session_id}")
    
    try:
        result = run_query(query, user_id=session_id)
        
        # show results
        print(f"\nAnswer:{result.get('output','No answer')}\n")
        
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("ERROR")
        print("=" * 60)
        print(f"\nAn error occurred: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        
def main():
    print("Starting agent show...")
    session_id = "test_session"
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        lines = [line.strip() for line in data.split("\n") if line.strip()]
        if not lines:
            print("No input provided.")
            return
        for line in lines:
            agent(line, session_id=session_id)
        return
    try:
        while True:
            query = input("> ").strip()
            if not query:
                continue
            agent(query, session_id=session_id)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting agent show.")

if __name__ == "__main__":
    sys.stdin.reconfigure(encoding='utf-8')
    main()