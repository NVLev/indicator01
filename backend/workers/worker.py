import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .tasks import celery_app

if __name__ == "__main__":
    celery_app.start()
