from collections.abc import Generator
import os
import random
import time

from app.core.llm_provider import LLMProvider

MOCK_RESPONSES = {
    'default': [
        'Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.',
        'Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.',
        'Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.',
    ],
    'docker': [
        'Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!'
    ],
    'deploy': [
        'Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được.'
    ],
    'health': ['Agent đang hoạt động bình thường. All systems operational.'],
}


class LocalProvider(LLMProvider):
    """LLM Provider for local models using llama-cpp-python.
    Optimized for CPU usage with GGUF models.
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_threads: int | None = None,
    ):
        """Initialize the local Llama model.

        Args:
            model_path: Path to the .gguf model file.
            n_ctx: Context window size.
            n_threads: Number of CPU threads to use. Defaults to all available.
        """
        super().__init__(model_name=os.path.basename(model_path))

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f'Model file not found at {model_path}. Please download it first.'
            )

        # n_threads=None will use all available cores

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, object]:
        start_time = time.time()

        # Phi-3 / Llama-3 style formatting if not handled by a template
        # full_prompt = prompt
        # if system_prompt:
        #     full_prompt = f'<|system|>\n{system_prompt}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>'
        # else:
        #     full_prompt = f'<|user|>\n{prompt}<|end|>\n<|assistant|>'
        #
        # response = self.llm(
        #     full_prompt, max_tokens=1024, stop=['<|end|>', 'Observation:'], echo=False
        # )
        #
        # end_time = time.time()
        # latency_ms = int((end_time - start_time) * 1000)
        #
        # content = response['choices'][0]['text'].strip()
        # usage = {
        #     'prompt_tokens': response['usage']['prompt_tokens'],
        #     'completion_tokens': response['usage']['completion_tokens'],
        #     'total_tokens': response['usage']['total_tokens'],
        # }
        #
        question_lower = prompt.lower()
        for keyword, responses in MOCK_RESPONSES.items():
            if keyword in question_lower:
                content = random.choice(responses)
                break
        else:
            content = random.choice(MOCK_RESPONSES['default'])
        return {
            'content': content,
            'usage': 0,
            'latency_ms': o,
            'provider': 'local',
        }

    def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> Generator[str, None, None]:
        response = self.generate(prompt)
        words = response['content'].split()
        for word in words:
            time.sleep(0.05)
            yield word + ' '
