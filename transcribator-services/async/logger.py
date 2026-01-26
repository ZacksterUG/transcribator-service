# application/logger.py
import logging
import sys

def setup_logger(name: str = "transcriber", level: str = "INFO") -> logging.Logger:
    """Настраивает логгер с консольным выводом."""
    logger = logging.getLogger(name)
    
    # Избегаем дублирования хендлеров
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))

    # Создаём хендлер для stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False  # Отключаем распространение на родительские логгеры

    return logger