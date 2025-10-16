import logging
import litellm
import yaml
from .analyzer import Analyzer
from .solve_agent import SolveAgent
from .utils import optimize_text

logger = logging.getLogger(__name__)


class Workflow:
    def __init__(self, config: dict):
        self.config = config
        self.processor_llm: dict = self.config["llm"]["pre_processor"]
        self.prompt: dict = yaml.safe_load(open("./prompt.yaml", "r", encoding="utf-8"))
        if self.config is None:
            raise ValueError("Configuration file is missing")

    def solve(self, problem: str) -> str:
        problem = self.summary_problem(problem)
        # Analyse the challenge
        analyzer = Analyzer(self.config, problem)
        analysis_result = analyzer.problem_analyze()
        logger.info(
            f"Challenge category: {analysis_result['category']}\nPlan: {analysis_result['solution']}"
        )

        # Create the SolveAgent and attach the flag confirmation callback
        agent = SolveAgent(self.config, problem)
        agent.confirm_flag_callback = self.confirm_flag

        # Pass the category and solution plan to the agent
        return agent.solve(analysis_result["category"], analysis_result["solution"])

    def confirm_flag(self, flag_candidate: str) -> bool:
        """
        Ask the user to confirm whether the candidate flag is correct.
        :param flag_candidate: Candidate flag string.
        :return: True if the user confirms the flag, otherwise False.
        """
        print(f"\nPossible flag detected:\n{flag_candidate}")
        print("Please confirm whether this flag is correct.")

        while True:
            response = input("Enter 'y' to accept, or 'n' if it is incorrect: ").strip().lower()
            if response == "y":
                return True
            elif response == "n":
                return False
            else:
                print("Invalid input. Please respond with 'y' or 'n'.")

    def summary_problem(self, problem: str) -> str:
        """
        Summarise the challenge to shorten long prompts.
        """
        if len(problem) < 128:
            return problem
        prompt = str(self.prompt["problem_summary"]).replace("{question}", problem)
        message = litellm.Message(role="user", content=optimize_text(prompt))
        response = litellm.completion(
            model=self.processor_llm["model"],
            api_key=self.processor_llm["api_key"],
            api_base=self.processor_llm["api_base"],
            messages=[message],
        )
        return response.choices[0].message.content
