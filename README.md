# BUUCTF_Agent
![image](https://github.com/MuWinds/BUUCTF_Agent/blob/main/1.png)
## Background

The project started when [@MuWinds](https://github.com/MuWinds) decided to build an AI agent for fun and practice.

The agent is not intended to stay limited to [BUUCTF](https://buuoj.cn), so the challenge descriptions are currently provided manually (mostly because of laziness).

Vision: become the trusted teammate of every CTF player—and if the agent can eventually solve challenges on its own, even better.

## Features

1. End-to-end automated solving, including problem analysis, target exploration, code execution, and flag extraction.
2. Interactive solving flow in the command line.
3. Built-in tooling to run Python locally or over SSH on a prepared Linux host.
4. Extensible framework for adding CTF tools.
5. Customisable prompts and model configurations.

## Deployment & Usage

1. Clone the repository
```
git clone https://github.com/MuWinds/BUUCTF_Agent.git
```
2. Install dependencies
```
pip install -r .\requirements.txt
```
3. (Optional) Configure a Docker container. This sets up the execution environment for the agent. You can prepare your own virtual machine, or use the provided Dockerfile—just make sure Docker is installed first.  
   (1) Build the image:
   ```bash
   docker build -t ctf_agent .
   ```
   (2) Run the image and map the container’s SSH port 22 to port 2201 on the host:
   ```bash
   docker run -itd -p 2201:22 ctf_agent
   ```
   If you create the container by using the Dockerfile in this repository, the SSH user is `root` and the password is `ctfagent`.
4. Update the configuration file `config.json` with your tooling preferences.  
   Below is an example that uses the SiliconFlow API (OpenAI-compatible mode):
   ```json
    {
        "llm":{
            "analyzer":{
                "model": "deepseek-ai/DeepSeek-R1",
                "api_key": "",
                "api_base": "https://api.siliconflow.cn/"
            },
            "solve_agent":{
                "model": "deepseek-ai/DeepSeek-V3",
                "api_key": "",
                "api_base": "https://api.siliconflow.cn/"
            },
            "pre_processor":{
                "model": "Qwen/Qwen3-8B",
                "api_key": "",
                "api_base": "https://api.siliconflow.cn/"
            }
        },
        "max_history_steps": 15,
        "compression_threshold": 7,
        "tool_config":{
            "ssh_shell": 
            {
                "host": "127.0.0.1",
                "port": 22,
                "username": "",
                "password": ""
            },
            "python":
            {
            }
        }
    }
   ```
   In the `llm` section, `analyzer` handles reasoning about outputs, `solve_agent` executes the solving steps, and `pre_processor` performs lightweight text pre-processing—use a small, cost-effective model here. A chain-of-thought style model is recommended for `analyzer` to improve the quality of reasoning.
   
   The project currently **only supports OpenAI-compatible APIs**.
5. Run the agent:
```
python .\main.py
```


## Roadmap
- ~~Allow running Python code in the local environment~~ (done)
- Support more tooling, e.g. binary analysis, beyond web and crypto challenges
- Provide a polished interface such as a web front-end or Qt desktop GUI
- Add a RAG knowledge base
- ~~Use different LLMs for different tools or tasks (reasoning vs. code generation)~~ (done)
- Improve MCP support
- Automate interactions with additional online judges so challenge text does not need to be entered manually
- ~~Support attachments~~ done—place files in the project root under `attachments`

## Tool Development
**Python execution and SSH access to a prepared Linux box are available out of the box.** If you want to add your own tooling, start here.

Inside the `ctf_tool` directory you will find `base_tool.py`:
```python
class BaseTool(ABC):
    @abstractmethod
    def execute(self, *args, **kwargs) -> Tuple[str, str]:
        """Run the tool and return stdout/stderr."""
        pass
    
    @property
    @abstractmethod
    def function_config(self) -> Dict:
        """Describe the function-call schema exposed to the agent."""
        pass
```
Every custom tool must implement `execute` and `function_config`.

* `execute` performs the actual action and returns a tuple of `(stdout, stderr)`; the order is flexible, but both values should be provided.

* `function_config` exposes the tool through function calling so the agent can discover when to use it. The method must be decorated with `@property`, and the returned structure follows a consistent schema. Example for a remote shell:
```python
@property
def function_config(self) -> Dict:
    return {
        "type": "function",
        "function": {
            "name": "execute_shell_command",
            "description": "Run a shell command on the remote server. curl, sqlmap, nmap, openssl, and other common tools are available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "Why this step is being executed."
                    },
                    "content": {
                        "type": "string",
                        "description": "The shell command to run."
                    },
                },
                "required": ["purpose", "content"]
            }
        }
    }
}
```

## Attention
Because the agent can execute shell commands, **do not let it run on a machine that stores important data**. There is no guarantee that an LLM will not suggest something destructive like `rm -rf /*`. Use a disposable environment or the provided Dockerfile to stay safe.

QQ group:

![image](https://github.com/MuWinds/BUUCTF_Agent/blob/main/qq_group.jpg)
