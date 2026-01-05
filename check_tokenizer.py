from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-llm-7b-chat")

# 1. Check the template string directly
print(tokenizer.chat_template)

# 2. Test what it outputs
messages = [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello"}
]
print(tokenizer.apply_chat_template(messages, tokenize=False))