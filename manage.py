#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import subprocess
import sys


def lint():
    """Run linting (py_compile) over key app folders."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "rag_app", "rag_project"],
            check=True,
        )
        if result.returncode == 0:
            print("✓ Lint passed: py_compile clean")
    except subprocess.CalledProcessError:
        print("✗ Lint failed: syntax errors present")
        sys.exit(1)


def main():
    """Run administrative tasks."""
    if "lint" in sys.argv:
        lint()
        sys.exit(0)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rag_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
