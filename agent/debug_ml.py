import asyncio
import sys
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

async def main():
    print("--- Testing FAISS ---")
    try:
        print(f"Faiss version: {faiss.__version__}")
        d = 64
        index = faiss.IndexFlatL2(d)
        print("Index created.")
        xb = np.random.random((10, d)).astype('float32')
        index.add(xb)
        print(f"Added vectors. ntotal={index.ntotal}")
    except Exception as e:
        print(f"FAISS failed: {e}")

    print("\n--- Testing SentenceTransformer ---")
    try:
        print("Loading SentenceTransformer BAAI/bge-m3...")
        # Force CPU to match what happens in Docker/likely environment
        model = SentenceTransformer("BAAI/bge-m3", device="cpu")
        print("Model loaded.")
        
        texts = ["This is a test sentence.", "Another sentence."]
        print("Encoding...")
        embeddings = model.encode(texts, normalize_embeddings=False)
        print(f"Embeddings shape: {embeddings.shape}")
    except Exception as e:
        print(f"SentenceTransformer failed: {e}")
        import traceback
        traceback.print_exc()

    print("\nSuccess.")

if __name__ == "__main__":
    asyncio.run(main())
