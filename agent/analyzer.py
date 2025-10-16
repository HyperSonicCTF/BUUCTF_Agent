import yaml
import json
import litellm
from . import utils
from typing import Dict
from .memory import Memory
from jinja2 import Environment, FileSystemLoader
from .utils import optimize_text

litellm.enable_json_schema_validation = True


class Analyzer:
    def __init__(self, config: dict, problem: str):
        self.config: dict = config
        self.env = Environment(loader=FileSystemLoader("."))
        self.llm_config: dict = self.config["llm"]["analyzer"]
        self.problem = problem
        self.prompt: dict = yaml.safe_load(open("./prompt.yaml", "r", encoding="utf-8"))
        litellm.enable_json_schema_validation = True

    def problem_analyze(self):
        prompt = self.prompt["problem_analyze"].replace("{question}", self.problem)
        message = [{"role": "user", "content": optimize_text(prompt)}]
        response = litellm.completion(
            model=self.llm_config.get("model"),
            api_key=self.llm_config.get("api_key"),
            api_base=self.llm_config.get("api_base"),
            messages=message,
        )
        msg_result = response.choices[0].message.content
        try:
            analyze_result = json.loads(msg_result)
        except (json.JSONDecodeError, KeyError) as e:
            msg_result = utils.fix_json_with_llm(msg_result, e)
            analyze_result = json.loads(msg_result)

        return analyze_result

    def analyze_step_output(
        self,
        memory: Memory,
        step_num: int,
        content: str,
        output: str,
        solution_plan: str,
    ) -> Dict:
        """
        Analyse the output of a solving step with the LLM.
        :param step_num: Step number.
        :param content: Executed content (e.g., command).
        :param output: Command output.
        :param solution_plan: Current solution plan.
        :return: Analysis dictionary.
        """
        # Summarise historical context
        history_summary = memory.get_summary()

        # Render the prompt with Jinja2
        template = self.env.from_string(self.prompt.get("step_analysis", ""))
        prompt = template.render(
            question=self.problem,
            step_num=step_num,
            content=content,
            output=output[:4096],
            solution_plan=solution_plan,
            history_summary=history_summary,
        )

        # Query the LLM for the analysis
        response = litellm.completion(
            model=self.llm_config["model"],
            api_key=self.llm_config["api_key"],
            api_base=self.llm_config["api_base"],
            messages=[{"role": "user", "content": optimize_text(prompt)}],
        )
        # Parse and return the analysis result
        try:
            result = json.loads(response.choices[0].message.content)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, KeyError) as e:
            content = utils.fix_json_with_llm(response.choices[0].message.content, e)
            result = json.loads(content)
            return result
