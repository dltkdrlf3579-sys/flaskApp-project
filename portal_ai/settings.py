import configparser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / "config.ini", encoding="utf-8-sig")
    return config


def configured_path(config, section, key, default=""):
    value = config.get(section, key, fallback=default).strip()
    if not value:
        raise ValueError("설정이 필요합니다: [{}] {}".format(section, key))
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def bounded_int(config, section, key, default, minimum, maximum):
    value = config.getint(section, key, fallback=default)
    if not minimum <= value <= maximum:
        raise ValueError("[{}] {}는 {}~{} 범위여야 합니다.".format(section, key, minimum, maximum))
    return value
