import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    scripts = (
        ROOT_DIR / "app" / "transcriptor.py",
        ROOT_DIR / "app" / "unificador.py",
        ROOT_DIR / "app" / "resume.py",
    )

    for script in scripts:
        subprocess.run([sys.executable, str(script)], cwd=ROOT_DIR, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
