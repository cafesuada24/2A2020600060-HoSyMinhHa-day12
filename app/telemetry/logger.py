import json
import logging
import os
from datetime import UTC, datetime


class IndustryLogger:
    """Structured logger that simulates industry practices.
    Logs to both console and a file in JSON format.
    """

    def __init__(self, name: str = 'AI-Lab-Agent', log_dir: str = 'logs') -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        os.makedirs(log_dir, exist_ok=True)

        # File Handler (JSON)
        log_file = os.path.join(log_dir, f'{datetime.now().strftime("%Y-%m-%d")}.log')
        file_handler = logging.FileHandler(log_file)

        # Console Handler
        console_handler = logging.StreamHandler()

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_event(self, event_type: str, data: dict[str, object]) -> None:
        """Logs an event with a timestamp and type."""
        payload = {
            'timestamp': datetime.now(UTC).isoformat(),
            'event': event_type,
            'data': data,
        }
        self.logger.info(json.dumps(payload))

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str, exc_info=True):
        self.logger.error(msg, exc_info=exc_info)


# Global logger instance
logger = IndustryLogger()
