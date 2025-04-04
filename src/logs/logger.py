import os
import sys
from loguru import logger
from typing import Dict, Any

def setup_logging(config: Dict[str, Any]):
    """Configure logging based on configuration"""
    log_config = config['logging']
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'logs/monitor.log')
    log_format = log_config.get('format', "{time} | {level} | {message}")
    retention = log_config.get('retention', "7 days")
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure logger
    logger.remove()  # Remove default handler
    
    # Add console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True
    )
    
    # Add file handler
    logger.add(
        log_file,
        format=log_format,
        level=log_level,
        rotation="10 MB",
        retention=retention,
        compression="zip"
    )
    
    return logger
