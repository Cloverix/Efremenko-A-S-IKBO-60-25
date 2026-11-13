"""Модуль конфигурации приложения."""
from argparse import ArgumentTypeError, ArgumentParser
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree


class Configuration(NamedTuple):
    """Набор параметров конфигурации."""

    vfs: Path | None = None
    script: Path | None = None
    config: Path | None = None


def dir_exists(arg: str) -> Path:
    """Проверяет, что переданный путь существует и является папкой."""
    path = Path(arg).expanduser().resolve()
    if not path.is_dir():
        raise ArgumentTypeError(f"{arg}: не директория")
    return path


def file_exists(arg: str) -> Path:
    """Проверяет, что переданный путь существует и является файлом."""
    path = Path(arg).expanduser().resolve()
    if not path.is_file():
        raise ArgumentTypeError(f"{arg}: не файл")
    return path


def parse_cli_args() -> Configuration:
    """Парсит аргументы командной строки."""
    parser = ArgumentParser(prog="terminal")
    parser.add_argument("--vfs", type=dir_exists, default=None)
    parser.add_argument("--script", type=file_exists, default=None)
    parser.add_argument("--config", type=file_exists, default=None)
    parsed = parser.parse_args()

    return Configuration(
        vfs=parsed.vfs,
        script=parsed.script,
        config=parsed.config
    )


def parse_config_file(path: str) -> Configuration:
    """Парсит XML файл конфигурации."""
    xml_path = Path(path).expanduser().resolve()
    if not xml_path.is_file():
        return Configuration()

    tree = ElementTree.parse(xml_path)
    vfs_element = tree.find("vfs")
    script_element = tree.find("script")

    vfs_text = vfs_element.text.strip() if vfs_element is not None else None
    script_text = (
        script_element.text.strip()
        if script_element is not None
        else None
    )

    vfs_path = (
        Path(vfs_text).expanduser().resolve()
        if vfs_text
        else None
    )
    script_path = (
        Path(script_text).expanduser().resolve()
        if script_text
        else None
    )

    return Configuration(vfs=vfs_path, script=script_path, config=xml_path)


def merge_configuration(
    cli_conf: Configuration,
    xml_conf: Configuration
) -> Configuration:
    """Объединяет параметры из CLI и XML (CLI имеет приоритет)."""
    vfs = cli_conf.vfs if cli_conf.vfs is not None else xml_conf.vfs
    script = (
        cli_conf.script
        if cli_conf.script is not None
        else xml_conf.script
    )
    config = (
        cli_conf.config
        if cli_conf.config is not None
        else xml_conf.config
    )
    return Configuration(vfs=vfs, script=script, config=config)