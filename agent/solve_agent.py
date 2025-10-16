import litellm
import json
import time
import yaml
import os
import logging
import inspect
import importlib
from ctf_tool.base_tool import BaseTool
from litellm import ModelResponse
from .analyzer import Analyzer
from typing import Dict, Tuple, Optional, List
from .memory import Memory
from .utils import optimize_text
from . import utils
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)
litellm.enable_json_schema_validation = True


class SolveAgent:
    def __init__(self, config: dict, problem: str):
        self.config = config
        self.llm_config = self.config["llm"]["solve_agent"]
        self.problem = problem
        self.prompt: dict = yaml.safe_load(open("./prompt.yaml", "r", encoding="utf-8"))
        if self.config is None:
            raise ValueError("Configuration file not found")

        # Initialise the Jinja2 template environment
        self.env = Environment(loader=FileSystemLoader("."))

        # Initialise the memory system
        self.memory = Memory(
            config=self.config,
            max_steps=self.config.get("max_history_steps", 10),
            compression_threshold=self.config.get("compression_threshold", 5),
        )

        # Dynamically loaded tools
        self.tools: Dict[str, BaseTool] = {}  # Tool name -> tool instance
        self.function_configs: List[Dict] = []  # Function-call configurations
        self.analyzer = Analyzer(config=self.config, problem=self.problem)

        # Load all tools from the ctf_tool package
        self._load_tools()

        # Let the user choose the operating mode
        self._select_mode()

        # Workflow will inject the flag confirmation callback
        self.confirm_flag_callback = None

    def _select_mode(self):
        """Prompt the user to choose between automatic and manual modes."""
        print("\nSelect a run mode:")
        print("1. Automatic mode (the agent generates and executes every command)")
        print("2. Manual mode (each step requires approval)")

        while True:
            choice = input("Enter the option number: ").strip()
            if choice == "1":
                self.auto_mode = True
                logger.info("Automatic mode selected.")
                return
            elif choice == "2":
                self.auto_mode = False
                logger.info("Manual mode selected.")
                return
            else:
                print("Invalid option, please try again.")

    def _load_tools(self):
        """Dynamically import every tool module."""
        tools_dir = os.path.join(os.path.dirname(__file__), "..", "ctf_tool")

        for file_name in os.listdir(tools_dir):
            if (
                file_name.endswith(".py")
                and file_name != "__init__.py"
                and file_name != "base_tool.py"
            ):
                module_name = file_name[:-3]  # Strip the .py suffix
                try:
                    # Import the module
                    module = importlib.import_module(f"ctf_tool.{module_name}")

                    # Find every class inheriting from BaseTool
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, BaseTool)
                            and obj != BaseTool
                        ):
                            # Instantiate with custom config when provided
                            if name in self.config.get("tool_config", {}):
                                tool_config = self.config["tool_config"][name]
                                tool_instance = obj(tool_config)
                            else:
                                tool_instance = obj()

                            # Register the tool
                            tool_name = tool_instance.function_config["function"][
                                "name"
                            ]
                            self.tools[tool_name] = tool_instance

                            # Collect its function-call schema
                            self.function_configs.append(tool_instance.function_config)

                            logger.info(f"Loaded tool: {tool_name}")
                except Exception as e:
                    logger.warning(f"Failed to load tool module {module_name}: {str(e)}")

    def solve(self, problem_class: str, solution_plan: str) -> str:
        """
        Main solving loop that executes step-by-step.
        :param problem_class: Challenge category (Web/Crypto/Reverse/etc.).
        :param solution_plan: Solving strategy provided by the analyzer.
        :return: The confirmed flag, or a status string if unsuccessful.
        """
        step_count = 0

        while True:
            step_count += 1
            print(f"\nThinking through step {step_count}...")

            # Generate the next action
            next_step = None
            while next_step is None:
                next_step = self.generate_next_step(problem_class, solution_plan)
                if next_step:
                    break
                print("Failed to generate an action. Retrying in 10 seconds...")
                time.sleep(10)

            # Extract the tool name and arguments
            tool_name = next_step.get("tool_name")
            arguments: dict = next_step.get("arguments", {})
            content = arguments.get("content", "")

            # Manual mode: request confirmation before running the command
            if not self.auto_mode:
                approved, next_step = self.manual_approval_step(next_step)
                if not approved:
                    print("Challenge solving aborted by the user.")
                    return "Solving aborted"
                # Refresh values in case the user requested a revision
                tool_name = next_step.get("tool_name")
                arguments = next_step.get("arguments", {})
                content = arguments.get("content", "")

            # Execute the command
            output = ""
            if tool_name in self.tools:
                try:
                    tool = self.tools[tool_name]
                    result = tool.execute(arguments)
                    stdout, stderr = result
                    output = stdout + stderr
                except Exception as e:
                    output = f"Tool execution error: {str(e)}"
            else:
                output = f"Error: tool '{tool_name}' was not found"

            logger.info(f"Command output:\n{output}")

            # Analyse the output with the LLM
            analysis_result = self.analyzer.analyze_step_output(
                self.memory, step_count, content, output, solution_plan
            )

            # Check whether the LLM detected a flag
            if analysis_result.get("flag_found", False):
                flag_candidate = analysis_result.get("flag", "")
                logger.info(f"LLM reported a potential flag: {flag_candidate}")

                # Confirm the flag through the callback
                if self.confirm_flag_callback and self.confirm_flag_callback(
                    flag_candidate
                ):
                    return flag_candidate
                else:
                    logger.info("Flag rejected by the user. Continuing...")

            # Store the step in memory
            self.memory.add_step(
                {
                    "step": step_count,
                    "purpose": arguments.get("purpose", "unspecified"),
                    "content": content,
                    "output": output,
                    "analysis": analysis_result,
                }
            )

            # Respect early termination advice
            if analysis_result.get("terminate", False):
                print("LLM advised stopping early.")
                return "Flag not found: terminated early"

    def manual_approval_step(self, next_step: Dict) -> Tuple[bool, Optional[Dict]]:
        """Manual mode: gather feedback until the user approves or aborts."""
        while True:
            arguments: dict = next_step.get("arguments", {})
            purpose = arguments.get("purpose", "unspecified")

            print("1. Approve and execute")
            print("2. Provide feedback and rethink")
            print("3. Abort solving")
            choice = input("Enter the option number: ").strip()

            if choice == "1":
                return True, next_step
            elif choice == "2":
                feedback = input("Enter your feedback or suggested changes: ").strip()
                next_step = self.reflection(purpose, feedback)
                if not next_step:
                    print("(Generation failed. Provide more feedback or choose option 3 to abort.)")
            elif choice == "3":
                return False, None
            else:
                print("Invalid option, please try again.")

    def reflection(self, purpose: str, feedback: str) -> Dict:
        """
        Regenerate a command based on user feedback.
        Returns the revised next_step for further confirmation.
        """
        history_summary = self.memory.get_summary()

        template = self.env.from_string(self.prompt.get("reflection", ""))
        prompt = template.render(
            question=self.problem,
            original_purpose=purpose,
            feedback=feedback,
            history_summary=history_summary,
            tools=self.tools.values(),
        )

        response = litellm.completion(
            model=self.llm_config["model"],
            api_key=self.llm_config["api_key"],
            api_base=self.llm_config["api_base"],
            messages=[{"role": "user", "content": optimize_text(prompt)}],
            tools=self.function_configs,
            tool_choice="auto",
        )

        # Parsing might fail; propagate None so callers can react
        return self.parse_tool_response(response)

    def generate_next_step(self, problem_class: str, solution_plan: str) -> Dict:
        """
        Ask the LLM for the next action.
        :param problem_class: Challenge category.
        :param solution_plan: Current solution plan.
        :return: A dictionary containing the tool name and arguments.
        """
        # Summarise the memory for context
        history_summary = self.memory.get_summary()

        # Choose the appropriate prompt template for the category
        prompt_key = problem_class.lower() + "_next"
        if prompt_key not in self.prompt:
            prompt_key = "general_next"

        # Render the prompt
        template = self.env.from_string(self.prompt.get(prompt_key, ""))
        prompt = template.render(
            question=self.problem,
            solution_plan=solution_plan,
            history_summary=history_summary,
            tools=self.tools.values(),
        )

        # Request the next action from the LLM
        response = litellm.completion(
            model=self.llm_config["model"],
            api_key=self.llm_config["api_key"],
            api_base=self.llm_config["api_base"],
            messages=[{"role": "user", "content": optimize_text(prompt)}],
            tools=self.function_configs,
            tool_choice="auto",
        )

        # Interpret the tool-call response
        return self.parse_tool_response(response)

    def parse_tool_response(self, response: ModelResponse) -> Dict:
        """Normalise tool-call responses returned by the LLM."""
        message = response.choices[0].message

        # Case 1: tool_calls field populated directly
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_call = message.tool_calls[0]
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                args = utils.fix_json_with_llm(tool_call.function.arguments, e)

            # Ensure purpose and content are available
            args.setdefault("purpose", "Execute action")
            args.setdefault("content", "")

        # Case 2: message content is a JSON string
        else:
            content = message.content.strip()
            # Attempt to parse JSON directly
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                print("Unable to parse tool-call response, attempting repair...")
                content = utils.fix_json_with_llm(content, e)
                data = json.loads(content)
            except Exception as e:
                print(f"Failed to parse tool-call response: {e}")
                return {}
            if "tool_calls" in data and data["tool_calls"]:
                tool_call: dict = data["tool_calls"][0]
                func_name: dict = tool_call.get("name", "tool_parse_failed")
                args: dict = tool_call.get("arguments", {})
                args.setdefault("purpose", "Execute action")
                args.setdefault("content", "")

        logger.info(f"Tool selected: {func_name}")
        logger.info(f"Purpose: {args['purpose']}")
        logger.info(f"Command:\n{args['content']}")
        return {"tool_name": func_name, "arguments": args}
