"""Entry point for a small workspace utility.

Reads non-secret configuration from config.yaml, loads local secrets from .env,
processes files from input/, and writes run artifacts to output/.
"""

from pathlib import Path

import yaml
from dotenv import load_dotenv

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    load_dotenv()
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    config = load_config()
    input_dir = Path(config.get("input_dir", "input"))
    output_dir = Path(config.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # TODO: implement the utility logic.
    print(f"input={input_dir} output={output_dir}")


if __name__ == "__main__":
    main()
