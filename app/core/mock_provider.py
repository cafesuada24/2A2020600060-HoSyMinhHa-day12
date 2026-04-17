import time
import random
from typing import Dict, Any, Optional, Generator
from app.core.llm_provider import LLMProvider

class MockProvider(LLMProvider):
    def __init__(self, model_name: str = "mock-llm"):
        super().__init__(model_name)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        time.sleep(0.1)  # Simulate latency
        
        # Simple ReAct-style mock response if it sees specific patterns
        content = "I am a mock response."
        if "Action:" in prompt or "Thought:" in prompt:
             content = "Thought: I need to answer the user request.\nAction: get_system_time\nAction Input: None"
             if "Observation:" in prompt:
                 content = "Final Answer: Today is Friday, April 17, 2026 (mock)."

        end_time = time.time()
        return {
            "content": content,
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            "latency_ms": int((end_time - start_time) * 1000),
            "provider": "mock"
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        response = self.generate(prompt, system_prompt)["content"]
        for word in response.split():
            yield word + " "
            time.sleep(0.05)
