import inspect
try:
    from mem0 import Memory
    print("Memory class found.")
    print("Memory.add signature:", inspect.signature(Memory.add))
    print("Memory.search signature:", inspect.signature(Memory.search))
except ImportError:
    print("mem0 not installed.")
except Exception as e:
    print(f"Error: {e}")
