# Small Model Optimization Guide

This guide explains how the system is optimized for running tool-calling agents on limited hardware with small language models (3B-7B parameters).

## Current Setup

The system uses **manual tool calling** instead of native function calling, which works with any model size:

1. **Model receives instructions** to output tools in this format:
   ```
   <tool_call name="tool_name">{"arg": "value"}</tool_call>
   ```

2. **Regex parser extracts** tool calls from the model's response

3. **Tools are executed** and results are fed back to the model

4. **Model continues** with the tool results

## Optimizations for Small Models

### 1. **Simplified Instructions** ([llm_core.py:37-48](agent/llm_core.py#L37-L48))
   - Short, clear instructions
   - Concrete example provided
   - Emphasizes stopping and waiting for results

### 2. **Dynamic Tool Listing** ([llm_core.py:172-188](agent/llm_core.py#L172-L188))
   - Shows available tools in the prompt
   - Limits to top 10 tools to save context
   - Truncates long descriptions

### 3. **Model Parameters** ([llm_core.py:24-31](agent/llm_core.py#L24-L31))
   - `temperature=0.1` - Low for consistency, not zero to avoid repetition
   - `num_ctx=4096` - Reasonable context window
   - `repeat_penalty=1.1` - Prevents loops

### 4. **Reduced Iterations** ([llm_core.py:229](agent/llm_core.py#L229))
   - Max 3 tool-calling turns (vs 5 for larger models)
   - Prevents confusion and context overflow

## Recommended Models for Limited Hardware

### Best: Qwen2.5:3b (default)
```bash
ollama pull qwen2.5:3b
```
- Best instruction following in 3B class
- Good at structured outputs
- ~2GB RAM

### Alternative: Phi3:mini
```bash
ollama pull phi3:mini
```
- ~3.8B parameters
- Excellent instruction following
- ~2.5GB RAM

### Smallest: Gemma2:2b
```bash
ollama pull gemma2:2b
```
- Only 2B parameters
- Decent for simple tasks
- ~1.5GB RAM

## Testing Your Setup

1. **Make sure Ollama is running:**
   ```bash
   ollama serve
   ```

2. **Test the model directly:**
   ```bash
   ollama run qwen2.5:3b "When you need information, use: <tool_call name=\"web_search\">{\"query\": \"test\"}</tool_call>"
   ```

3. **Run your agent** and check the logs for:
   ```
   [agent] Using manual tool dispatch with X tools (small model mode)
   [agent] Detected N manual tool calls
   ```

## Troubleshooting

### Model doesn't generate tool calls
- Check if instructions are being added (look for tool instructions in logs)
- Try adding examples to your system prompt
- Consider using phi3:mini instead (better instruction following)

### Model generates invalid JSON
- Small models struggle with complex JSON
- Keep tool arguments simple
- Use single-level dictionaries when possible

### Model gets confused after 2-3 turns
- This is normal for 3B models
- The system limits to 3 turns automatically
- Consider breaking complex tasks into simpler steps

### Out of memory errors
- Reduce `num_ctx` to 2048 in [llm_core.py:29](agent/llm_core.py#L29)
- Use gemma2:2b instead of qwen2.5:3b
- Close other applications

## Performance Expectations

**3B Model Limitations:**
- ✅ Simple tool calls (1-2 arguments)
- ✅ Common tools (search, calculator)
- ⚠️ Complex multi-step reasoning
- ⚠️ Long conversations (context limit)
- ❌ Very complex JSON structures
- ❌ Many simultaneous tools

**When to upgrade:**
If you frequently need complex reasoning or multi-tool orchestration, consider:
- Running a 7B model (qwen2.5:7b, mistral:7b-instruct)
- Using cloud APIs (OpenAI, Anthropic) for important tasks
- Running on a more powerful machine periodically

## Configuration

All settings are in [.env](.env):
```bash
OLLAMA_MODEL=qwen2.5:3b  # Change model here
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Change the model and restart your application to test different models.
