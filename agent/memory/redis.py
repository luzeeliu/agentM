# use reddis build agent memory
import os
import dotenv
import json
import uuid
from typing import List, Optional
from redis import Redis
from time import time
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import BaseMessage

dotenv.load_dotenv()

# initial redis host 
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", 6379)
redis_db = os.getenv("REDIS_DB", 0)

# short memory for chat, this may replace by mm0
class ShortMMemory:
    def __init__(self, session_id : str = "default"):
        self.memory = RedisChatMessageHistory(
            # sessiion id is the chat session id 
            session_id=session_id,
            url= f"redis://{redis_host}:{redis_port}/{redis_db}"
        )
    
    # add human message
    def add_human_messages(self, message: str):
        self.memory.add_user_message(message)
    
    # add ai message
    def add_ai_messages(self, message: str):
        self.memory.add_ai_message(message)
    
    # get history
    def get_history(self):
        return self.memory.messages
    
    # get recent history
    def get_recent(self, k: int = 3):
        return self.memory.messages[-k:]
    
    # clear history
    def clear_history(self):
        self.memory.clear()
    

# user profile memory - stores user information in Redis which is quickly 
class UserProfile:
    def __init__(self, user_id: str):
        # initial redis host
        self.user_id = user_id
        self.redis_client = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db
        )
        
        self.key = f"user_profile:{user_id}"
        
    # strore user profile by using redis hset wich is hash type
    # the data structure of user profile is dict 
    def store_user_info(self, user_info: dict):
        # Store as JSON string
        info = {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            for k, v in user_info.items()
        }
        
        self.redis_client.hset(self.key, mapping=info)
        # Set expiration to 7 days
        self.redis_client.expire(self.key, 604800)
    
    # get user profile
    def get_user_info(self) -> Optional[dict]:
        data = self.redis_client.hgetall(self.key)
        if not data:
            return None
        user_info = {}
        for k, v in data.items():
            try:
                if isinstance(k, bytes):
                    k = k.decode('utf-8')
                if isinstance(v, bytes):
                    v = v.decode('utf-8')
                user_info[k] = json.loads(v)
            except (ValueError, TypeError, json.JSONDecodeError):
                user_info[k] = v
        return user_info
    
