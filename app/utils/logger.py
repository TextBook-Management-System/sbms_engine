import logging
import sys
import os

def setup_logger(name: str = "sbms_engine", level: int = logging.INFO):
    """Set up logger for Vercel (Console only)"""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Console handler - This is what Vercel captures
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add ONLY the console handler
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()