import sys

from bot.services.heartbeat import is_healthy


if __name__ == "__main__":
    sys.exit(0 if is_healthy() else 1)
