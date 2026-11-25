"""Orquesta el pipeline: transcribir, unificar, resumir, indexar y extraer temas."""

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) > 2:
        raise ValueError("Uso: python app/main.py [email_de_la_cuenta]")
    if len(sys.argv) == 2:
        os.environ["REUNION_OWNER_EMAIL"] = sys.argv[1].strip().lower()

    scripts = (
        ROOT_DIR / "app" / "transcriptor.py",
        ROOT_DIR / "app" / "unificador.py",
        ROOT_DIR / "app" / "resume.py",
        ROOT_DIR / "app" / "indexador.py",
        ROOT_DIR / "app" / "extractor_temas.py",
    )

    meeting_id = None

    for index, script in enumerate(scripts):
        command = [sys.executable, str(script)]
        if meeting_id is not None:
            command.append(meeting_id)

        if index == 0:
            result = subprocess.run(
                command,
                cwd=ROOT_DIR,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            meeting_id = result.stdout.strip()
            if not meeting_id.isdigit():
                raise ValueError("No se recibió un ID válido de Supabase")
        else:
            subprocess.run(command, cwd=ROOT_DIR, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
