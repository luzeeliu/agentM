import trl
import inspect

print(f"TRL version: {trl.__version__}")

try:
    from trl import DataCollatorForCompletionOnlyLM
    print("DataCollatorForCompletionOnlyLM found in trl")
except ImportError:
    print("DataCollatorForCompletionOnlyLM NOT found in trl")

try:
    from trl.trainer import DataCollatorForCompletionOnlyLM
    print("DataCollatorForCompletionOnlyLM found in trl.trainer")
except ImportError:
    print("DataCollatorForCompletionOnlyLM NOT found in trl.trainer")

try:
    from trl.trainer.utils import DataCollatorForCompletionOnlyLM
    print("DataCollatorForCompletionOnlyLM found in trl.trainer.utils")
except ImportError:
    print("DataCollatorForCompletionOnlyLM NOT found in trl.trainer.utils")

try:
    from trl import DataCollatorForChatML
    print("DataCollatorForChatML found in trl")
except ImportError:
    print("DataCollatorForChatML NOT found in trl")

try:
    from trl.trainer.utils import DataCollatorForChatML
    print("DataCollatorForChatML found in trl.trainer.utils")
except ImportError:
    print("DataCollatorForChatML NOT found in trl.trainer.utils")
