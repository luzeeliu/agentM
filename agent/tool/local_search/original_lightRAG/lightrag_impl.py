import os
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional, List, Any
from dotenv import load_dotenv

# Dependencies
try:
    from lightrag import LightRAG, QueryParam
    from lightrag.utils import EmbeddingFunc
    from lightrag.kg.shared_storage import initialize_pipeline_status
except ImportError:
    raise ImportError("lightrag-hku is not installed. Please run 'pip install lightrag-hku'.")

from langchain_google_genai import ChatGoogleGenerativeAI
from sentence_transformers import SentenceTransformer
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

# Load environment variables
load_dotenv()

# Global variables for caching models
_EMBEDDING_MODEL: Optional[SentenceTransformer] = None

# because the embedding storage have different namespace we need separate vanilla RAG with light
# Configuration
DEFAULT_WORKING_DIR = Path(__file__).parent / "index_data"

async def get_embedding_model(model_name: str = "BAAI/bge-m3") -> SentenceTransformer:
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        # Run in executor to avoid blocking the event loop during load
        loop = asyncio.get_running_loop()
        def load_model():
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading embedding model on: {device}")
            return SentenceTransformer(model_name, device=device)
            
        _EMBEDDING_MODEL = await loop.run_in_executor(None, load_model)
    return _EMBEDDING_MODEL

async def bge_embedding_func(texts: list[str]) -> np.ndarray:
    model = await get_embedding_model()
    # Run encoding in executor
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, 
        lambda: model.encode(texts, normalize_embeddings=True)
    )

async def gemini_llm_func(prompt: str, system_prompt: str = None, history_messages: list = [], **kwargs) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=api_key,
    )

    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    
    # history_messages from LightRAG are typically dictionaries like {'role': 'user', 'content': ...}
    for msg in history_messages:
        role = msg.get('role')
        content = msg.get('content')
        if role == 'user':
            messages.append(HumanMessage(content=content))
        elif role == 'assistant':
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=content))
        elif role == 'system':
            messages.append(SystemMessage(content=content))

    messages.append(HumanMessage(content=prompt))
    
    try:
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as e:
        # Simple error handling
        print(f"Error in Gemini LLM call: {e}")
        return ""

class LightRAGWrapper:
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or str(DEFAULT_WORKING_DIR)
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        
        self.rag = LightRAG(
            working_dir=self.working_dir,
            llm_model_func=gemini_llm_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=8192,
                func=bge_embedding_func
            ),
            vector_storage="FaissVectorDBStorage",
        )
        self.initialized = False

    async def initialize(self):
        if not self.initialized:
            await initialize_pipeline_status()
            await self.rag.initialize_storages()
            self.initialized = True

    async def insert_text(self, text: str):
        await self.initialize()
        await self.rag.ainsert(text)

    async def query(self, query_text: str, mode: str = "global"):
        await self.initialize()
        # modes: "naive", "local", "global", "hybrid"
        return await self.rag.aquery(query_text, param=QueryParam(mode=mode))

async def main():
    # Example usage
    print("Initializing LightRAG with Gemini 2.5 Flash and BGE-M3...")
    wrapper = LightRAGWrapper()
    
    print("Inserting test text...")
    test_text = "Gemini is a family of multimodal AI models developed by Google. It is their most capable model."
    await wrapper.insert_text(test_text)
    
    print("Querying (Local Mode)...")
    result = await wrapper.query("Who developed Gemini?", mode="local")
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())