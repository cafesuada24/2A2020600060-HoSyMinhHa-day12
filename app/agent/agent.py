import os
import re
from typing import List, Dict, Any
from app.core.llm_provider import LLMProvider
from app.telemetry.logger import logger
from app.telemetry.metrics import tracker
from pathlib import Path


class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 5,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """Load the prompt template with tools filled in (no user_input yet)."""
        tool_descriptions = "\n".join(
            [f"- {t['name']}: {t['description']}" for t in self.tools]
        )
        tools_list = ", ".join(t["name"] for t in self.tools)
        raw = (
            Path(os.environ.get("REACT_PROMPT", "app/prompts/ReAct.v2.txt"))
            .read_text()
        )
        # Support both v1 ({tools_list}) and v2 ({tools}) placeholders
        return raw.format(tools=tool_descriptions, tools_list=tools_list)

    def run(self, user_input: str) -> str:
        """Run the ReAct loop for a single query."""
        logger.log_event(
            "AGENT_START", {"input": user_input, "model": self.llm.model_name}
        )

        template = self.get_system_prompt()
        current_prompt = template + f"\nQuery: {user_input}\n"
        steps = 0
        final_answer = (
            "Agent failed to solve the problem within the iteration limit."
        )

        while steps < self.max_steps:
            steps += 1
            print(f"--- Iteration {steps} ---")

            response = self.llm.generate(current_prompt)
            llm_response = response["content"]
            print(llm_response)

            # Track metrics via PerformanceTracker
            tracker.track_request(
                provider=type(self.llm).__name__,
                model=self.llm.model_name,
                usage=response.get("usage", {}),
                latency_ms=response.get("latency_ms", 0),
            )

            if "Final Answer:" in llm_response:
                final_answer = llm_response.split("Final Answer:")[-1].strip()
                break

            action_match = re.search(r"Action:\s*(.*?)(?:\n|$)", llm_response)
            action_input_match = re.search(
                r"Action Input:\s*(.*?)(?:\n|$)", llm_response
            )

            if not action_match or not action_input_match:
                error_msg = "Error - Could not parse Action and Action Input. Please use the strict format."
                current_prompt += error_msg + "\n"
                continue

            action = action_match.group(1).strip()
            action_input = action_input_match.group(1).strip()

            observation = self._execute_tool(action, action_input)

            current_prompt += llm_response + "\nObservation: " + observation + "\n"

        logger.log_event(
            "AGENT_END",
            {"steps": steps, "final_answer": final_answer[:200]},
        )
        return final_answer

    def _execute_tool(self, tool_name: str, args: str) -> str:
        for tool in self.tools:
            if tool["name"] == tool_name:
                return tool["func"](args)
        return f"Tool {tool_name} not found."
