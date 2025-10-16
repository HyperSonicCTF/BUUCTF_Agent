from config import Config
from agent.workflow import Workflow
from datetime import datetime
import sys
import os
import logging


def setup_logging():
    """Configure the logging system."""
    # Create the log directory
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate a timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"log_{timestamp}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set file logging level to DEBUG and console level to INFO
    file_handler = logging.FileHandler(log_file,encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Remove default handlers and attach the custom ones
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Tweak third-party logger levels
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    config: dict = Config.load_config()
    print("If the challenge includes attachments, place them in the project root under the attachments directory.")
    print("Please enter the challenge title and description. Multi-line input is supported.")
    print("Press Enter, then finish with Ctrl+D (or Ctrl+Z followed by Enter on Windows).")
    question = sys.stdin.read().strip()
    logger.debug(f"Challenge content: {question}")
    result = Workflow(config=config).solve(question)
    logger.info(f"Final result: {result}")
