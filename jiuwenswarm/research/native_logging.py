"""Configure the pinned native logger before imports create default files."""
from pathlib import Path


def configure_native_logging(directory):
    root = Path(directory)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    from openjiuwen.core.common.logging.log_config import configure_log_config
    configure_log_config({"backend": "default", "level": "INFO", "log_path": str(root),
        "log_file": "run/jiuwen.log", "output": ["console", "file"],
        "structured_output_format": "json", "interface_log_file": "interface/jiuwen_interface.log",
        "prompt_builder_interface_log_file": "interface/jiuwen_prompt_builder_interface.log",
        "performance_log_file": "performance/jiuwen_performance.log"})
