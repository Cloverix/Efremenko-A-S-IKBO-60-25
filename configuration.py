from argparse import ArgumentTypeError, ArgumentParser
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree


# конфиг из аргументов командной строки для TerminalEmulator
class Configuration(NamedTuple):
    vfs: Path | None = None
    script: Path | None = None
    config: Path | None = None


def dir_exists(arg: str) -> Path:
    path = Path(arg).expanduser().resolve()
    if not path.is_dir():
        raise ArgumentTypeError(f"{arg}: не директория")
    return path


def file_exists(arg: str) -> Path:
    path = Path(arg).expanduser().resolve()
    if not path.is_file():
        raise ArgumentTypeError(f"{arg}: не файл")
    return path


def parseCLIArgs() -> Configuration:
    parser = ArgumentParser(
        prog="terminal"
    )
    parser.add_argument(
        "--vfs",
        type=dir_exists,
        default=None
    )
    parser.add_argument(
        "--script",
        type=file_exists,
        default=None
    )
    parser.add_argument(
        "--config",
        type=file_exists,
        default=None
    )
    parsed = parser.parse_args()

    return Configuration(
        vfs=parsed.vfs,
        script=parsed.script,
        config=parsed.config
    )


def parseConfigFile(path: str) -> Configuration:
    xml = Path(path).expanduser().resolve()
    if not xml.is_file():
        return Configuration()
    tree = ElementTree.parse(xml)
    vfsElement = tree.find("vfs")
    scriptElement = tree.find("script")
    
    vfsText = vfsElement.text.strip() if vfsElement is not None else None
    scriptText = scriptElement.text.strip() if scriptElement is not None else None
    return Configuration(
        vfs=Path(vfsText).expanduser().resolve() if vfsText else None,
        script=Path(scriptText).expanduser().resolve() if scriptText else None,
        config=xml 
    )


def mergeConfiguration(cliConf: Configuration, xmlConf: Configuration) -> Configuration:
    return Configuration(
        vfs=cliConf.vfs if cliConf.vfs is not None else xmlConf.vfs,
        script=cliConf.script if cliConf.script is not None else xmlConf.script,
        config=cliConf.config if cliConf.config is not None else xmlConf.config
    )