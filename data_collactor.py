import torch
from dataclasses import dataclass
from typing import Dict, List, Any, Sequence
from transformers import PreTrainedTokenizerBase

@dataclass
class DataCollator:
    # customer collactor for tool call training
    # we need mask the user input and tool result in the training
    tokenizer: PreTrainedTokenizerBase
    max_length: int = 2048
    
    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        # save the input ids and labels
        # which is the position index 
        input_ids_list = []
        labels_list = []
        attention_mask_list = []
        
        for i in features:
            # mask the human message and show the cot and tool calls
            messages = i["messages"]
            
            input_ids = []
            labels = []
            
            user_template = "<｜begin▁of▁sentence｜>User: {}\n\n"
            assistant_template = "Assistant: {}<｜end▁of▁sentence｜>"
            
            for mes in messages:
                role = mes["type"]
                content = mes["content"]
                
                if "tool_calls" in mes:
                    tool_call_str = f"\n<tool_call>{str(mes['tool_calls'])}</tool_call>\n"
                    content += tool_call_str
                    
                """
                # set the tokenizer include 
                format_data = self.tokenizer.apply_chat_template(
                    [{"role": role, "content": content}],
                    add_generation_prompt=False,
                    tokenize=False
                )
                """

                if role == "human":
                    # mask the human input
                    text = user_template.format(content)
                    tokenized_segment = self.tokenizer(text, add_special_tokens=False).input_ids
                    
                    # mask all human input
                    input_ids.extend(tokenized_segment)
                    labels.extend([-100] * len(tokenized_segment))
                            
                elif role == "ai":
                    text = assistant_template.format(content)
                    tokenized_segment = self.tokenizer(text, add_special_tokens=False).input_ids
                    
                    input_ids.extend(tokenized_segment)
                    labels.extend(tokenized_segment)
                    
                elif role == "tool":
                    tokenized_segment = self.tokenizer(content, add_special_tokens=False).input_ids
                    input_ids.extend(tokenized_segment)
                    labels.extend([-100] * len(tokenized_segment))
                    
                else:
                    tokenized_segment = self.tokenizer(content, add_special_tokens=False).input_ids
                    input_ids.extend(tokenized_segment)
                    labels.extend([-100] * len(tokenized_segment))
                    
                # input_ids will store the token ID and label will mix the id and mas
            
            if len(input_ids) > self.max_length:
                input_ids = input_ids[:self.max_length:]
                labels = labels[:self.max_length:]
                
            input_ids_list.append(torch.tensor(input_ids, dtype=torch.long))
            labels_list.append(torch.tensor(labels, dtype=torch.long))
            attention_mask_list.append(torch.ones(len(input_ids), dtype=torch.long))
            
            
        input_ids_padded = torch.nn.utils.rnn.pad_sequence(
            input_ids_list, batch_first=True, padding_value=0
        )
        labels_padded = torch.nn.utils.rnn.pad_sequence(
            labels_list, batch_first=True, padding_value=-100
        )
        attention_mask_padded = torch.nn.utils.rnn.pad_sequence(
            attention_mask_list,
            batch_first=True,
            padding_value=0
        )
        return {
            "input_ids": input_ids_padded,
            "labels": labels_padded,
            "attention_mask": attention_mask_padded
        }