import json
import os


class Config:
    def __init__(self, config_path="./config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    @classmethod
    def load_config(cls, config_path="./config.json") -> dict:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    config:dict = json.load(f)
                    # Normalize every model field within the llm section
                    if "llm" in config:
                        for agent in config["llm"].values():
                            if "model" in agent:
                                agent["model"] = "openai/" + agent["model"]
                    return config
                except json.JSONDecodeError:
                    raise ValueError(f"Configuration file {config_path} is not valid JSON")
        else:
            raise ValueError(f"Configuration file {config_path} was not found")

    @classmethod
    def get_tool_config(cls, tool_name: str, config_path="./config.json") -> dict:
        config = cls.load_config(config_path)
        return config["tool_config"][tool_name]

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
