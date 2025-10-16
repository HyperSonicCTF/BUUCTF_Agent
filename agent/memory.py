import litellm
import json
import logging
from typing import List, Dict
from .utils import optimize_text

logger = logging.getLogger(__name__)


class Memory:
    def __init__(
        self, config: dict, max_steps: int = 15, compression_threshold: int = 7
    ):
        """
        Memory management helper.
        :param config: Configuration dictionary.
        :param max_steps: Maximum number of detailed steps to retain.
        :param compression_threshold: Number of steps before triggering compression.
        """
        self.config = config
        self.llm_config = self.config["llm"]["solve_agent"]
        self.max_steps = max_steps
        self.compression_threshold = compression_threshold
        self.history: List[Dict] = []  # Full history of recent steps
        self.compressed_memory: List[Dict] = []  # Compressed memory blocks
        self.key_facts: Dict[str, str] = {}  # Structured key facts
        self.failed_attempts: Dict[str, int] = {}  # Failed attempt counters

    def add_step(self, step: Dict) -> None:
        """Add a new step to the history and extract key information."""
        self.history.append(step)

        # Extract key facts (command, output, analysis)
        self._extract_key_facts(step)

        # Track failed attempts
        if "analysis" in step and "success" in step["analysis"]:
            if not step["analysis"]["success"]:
                command = step.get("content", "")
                self.failed_attempts[command] = self.failed_attempts.get(command, 0) + 1

        # Compress the memory when needed
        if len(self.history) >= self.compression_threshold:
            self.compress_memory()

    def _extract_key_facts(self, step: Dict) -> None:
        """Pull key facts from a step and cache them."""
        # Capture the command and a truncated result
        if "content" in step and "output" in step:
            command = step["content"]
            output_summary = step["output"][:256] + (
                "..." if len(step["output"]) > 256 else ""
            )
            self.key_facts["command"] = f"Command: {command}, Result: {output_summary}"

        # Capture analysis conclusions
        if "analysis" in step and "analysis" in step["analysis"]:
            analysis = step["analysis"]["analysis"]
            if isinstance(analysis, str) and any(
                keyword in analysis.lower() for keyword in ("key finding", "key findings")
            ):
                self.key_facts[f"finding:{hash(analysis)}"] = analysis

    def compress_memory(self) -> None:
        """Compress the history into structured memory blocks."""
        logger.info("Compacting memory...")
        if not self.history:
            return

        # Build a detailed compression prompt
        prompt = (
            "You are a CTF solving assistant. Compress the solving history by completing these tasks:\n"
            "1. Identify key technical findings and discoveries.\n"
            "2. Record solutions that were attempted but failed.\n"
            "3. Summarise the current progress and suggest next steps.\n"
            "4. Return a JSON object with the structure:\n"
            "{\n"
            '  "key_findings": ["Finding 1", "Finding 2"],\n'
            '  "failed_attempts": ["Command 1", "Command 2"],\n'
            '  "current_status": "Status description",\n'
            '  "next_steps": ["Suggestion 1", "Suggestion 2"]\n'
            "}\n\n"
            "History:\n"
        )

        # Add key facts as context
        prompt += "Key facts summary:\n"
        for _, value in list(self.key_facts.items())[-5:]:  # Only keep the latest 5
            prompt += f"- {value}\n"

        # Include historical steps
        for i, step in enumerate(self.history[-self.compression_threshold :]):
            prompt += f"\nStep {i+1}:\n"
            prompt += f"- Purpose: {step.get('purpose', 'unspecified')}\n"
            prompt += f"- Command: {step['content']}\n"

            # Append analysis if present
            if "analysis" in step:
                analysis = step["analysis"].get("analysis", "No analysis")
                prompt += f"- Analysis: {analysis}\n"

        try:
            # Call the LLM to produce structured memory
            litellm.enable_json_schema_validation = True
            response = litellm.completion(
                model=self.llm_config["model"],
                api_key=self.llm_config["api_key"],
                api_base=self.llm_config["api_base"],
                messages=[{"role": "user", "content": optimize_text(prompt)}],
                max_tokens=1024,
            )

            # Parse and store the compressed memory block
            json_str = response.choices[0].message.content.strip()
            compressed_data = json.loads(json_str)

            # Update failed attempt counters
            for attempt in compressed_data.get("failed_attempts", []):
                self.failed_attempts[attempt] = self.failed_attempts.get(attempt, 0) + 1

            # Annotate with provenance metadata
            compressed_data["source_steps"] = len(self.history)

            self.compressed_memory.append(compressed_data)
            print(
                f"Memory compression succeeded: captured {len(compressed_data['key_findings'])} key findings."
            )

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Unable to parse compressed memory: {str(e)}")
            # Fall back to storing the raw summary
            fallback = (
                response.choices[0].message.content.strip()
                if "response" in locals()
                else "Compression failed"
            )
            self.compressed_memory.append(
                {"fallback_summary": fallback, "source_steps": len(self.history)}
            )
        except Exception as e:
            print(f"Memory compression failed: {str(e)}")
            self.compressed_memory.append(
                {"error": f"Compression failed: {str(e)}", "source_steps": len(self.history)}
            )

        # Retain the last few detailed steps for context
        keep_last = min(4, len(self.history))
        self.history = self.history[-keep_last:]

    def get_summary(self, include_key_facts: bool = True) -> str:
        """Return a consolidated memory summary."""
        summary = ""

        # 1. Key fact summary
        if include_key_facts and self.key_facts:
            summary += "Key facts:\n"
            for _, value in list(self.key_facts.items())[-10:]:  # Show up to 10 of the latest facts
                summary += f"- {value}\n"
            summary += "\n"

        # 2. Compressed memory blocks
        if self.compressed_memory:
            summary += "Compressed memory blocks:\n"
            for i, mem in enumerate(self.compressed_memory[-3:]):  # Show the latest three blocks
                summary += f"Block #{len(self.compressed_memory)-i}:\n"

                if "key_findings" in mem:
                    summary += f"- Status: {mem.get('current_status', 'unknown')}\n"
                    summary += f"- Key findings: {', '.join(mem['key_findings'][:3])}"
                    if len(mem["key_findings"]) > 3:
                        summary += f" and {len(mem['key_findings']) - 3} more"
                    summary += "\n"

                if "failed_attempts" in mem:
                    summary += f"- Failed attempts: {', '.join(mem['failed_attempts'][:3])}"
                    if len(mem["failed_attempts"]) > 3:
                        summary += f" and {len(mem['failed_attempts']) - 3} more"
                    summary += "\n"

                if "next_steps" in mem:
                    summary += f"- Suggested next step: {mem['next_steps'][0]}\n"

                summary += f"- Source: based on {mem['source_steps']} historical steps\n\n"

        # 3. Recent detailed steps
        if self.history:
            summary += "Recent detailed steps:\n"
            for i, step in enumerate(self.history):
                step_num = len(self.history) - i
                summary += f"Step {step_num}:\n"
                summary += f"- Purpose: {step.get('purpose', 'unspecified')}\n"
                summary += f"- Command: {step['content']}\n"

                # Include output and analysis excerpts
                if "output" in step:
                    output = step["output"]
                    summary += (
                        f"- Output: {output[:512]}{'...' if len(output) > 512 else ''}\n"
                    )

                if "analysis" in step:
                    analysis = step["analysis"].get("analysis", "No analysis")
                    summary += f"- Analysis: {analysis}\n"

                # Show failure counts
                if "content" in step and step["content"] in self.failed_attempts:
                    summary += (
                        f"- Historical failure count: {self.failed_attempts[step['content']]}\n"
                    )

                summary += "\n"
        return summary if summary else "No history"
