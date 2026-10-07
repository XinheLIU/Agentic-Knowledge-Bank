"""Export this product's skills with the separately installed agent-tools package."""
import sys
from pathlib import Path
from agent_tools.skills.export import main

if __name__ == "__main__":
    main(["--repo", str(Path(__file__).resolve().parents[1]), *sys.argv[1:]])
