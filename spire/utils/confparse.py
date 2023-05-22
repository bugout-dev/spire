from pathlib import Path
import toml # type: ignore


MODULE_PATH = Path(__file__).parent.parent.parent.resolve()

scope_conf = toml.load(f"{MODULE_PATH}/config.toml")
