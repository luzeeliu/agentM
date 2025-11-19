# tokenizer for gemini and deepseek

# tokenizer interface
class Tokenizer:
    def __init__(self, model_name, tokenizer):
        # initial the tokenizer
        self.tokenizer = tokenizer
        self.model_name = model_name
        
    def encode(self, content: str):
        # encode a string into a list of tokens using underlying tokenizer
        # return a list of interger token
        return self.tokenizer.encode(content)
    
    def decode(self, tokens):
        # decode a list of token into a string using the underlying tokenizer
        # return the decoded string
        return self.tokenizer.decode(tokens)
    
        
class TiktokenTokenizer(Tokenizer):
    """
    A Tokenizer implementation using the tiktoken library.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        """
        Initializes the TiktokenTokenizer with a specified model name.

        Args:
            model_name: The model name for the tiktoken tokenizer to use.  Defaults to "gpt-4o-mini".

        Raises:
            ImportError: If tiktoken is not installed.
            ValueError: If the model_name is invalid.
        """
        try:
            import tiktoken
        except ImportError:
            raise ImportError(
                "tiktoken is not installed. Please install it with `pip install tiktoken` or define custom `tokenizer_func`."
            )

        try:
            tokenizer = tiktoken.encoding_for_model(model_name)
            super().__init__(model_name=model_name, tokenizer=tokenizer)
        except KeyError:
            raise ValueError(f"Invalid model_name: {model_name}.")