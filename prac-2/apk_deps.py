import argparse
import configparser
import io
import re
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass
class Config:
    package: str
    repo_url: Optional[str]
    test_file: Optional[str]
    test_mode: bool
    ascii_tree: bool
    max_depth: int


class ConfigError(Exception):
    pass


_BOOL_TRUE = {"true", "1", "yes"}
_BOOL_FALSE = {"false", "0", "no"}


def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    cp = configparser.ConfigParser()
    try:
        with path.open("r", encoding="utf-8") as f:
            cp.read_file(f)
    except Exception as e:
        raise ConfigError(f"Cannot parse INI: {e}")

    if not cp.has_section("main"):
        raise ConfigError("Section [main] is required")
    sec = cp["main"]

    # package
    package = sec.get("package", "").strip()
    if not package:
        raise ConfigError("Parameter 'package' is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", package):
        raise ConfigError(f"Invalid package name: {package!r}")

    # test_mode
    raw = sec.get("test_mode", "false").strip().lower()
    if raw not in _BOOL_TRUE | _BOOL_FALSE:
        raise ConfigError(f"Invalid test_mode value: {raw!r}")
    test_mode = raw in _BOOL_TRUE

    # test_file / repo_url
    test_file = sec.get("test_file", "").strip() or None
    repo_url = sec.get("repo_url", "").strip() or None

    if test_mode:
        if not test_file:
            raise ConfigError("'test_file' is required when test_mode=true")
        if not Path(test_file).exists():
            raise ConfigError(f"test_file not found: {test_file}")
    else:
        if not repo_url:
            raise ConfigError("'repo_url' is required when test_mode=false")
        if not re.match(r"^https?://", repo_url):
            raise ConfigError(f"repo_url must be http(s) URL: {repo_url!r}")

    # ascii_tree
    raw = sec.get("ascii_tree", "true").strip().lower()
    if raw not in _BOOL_TRUE | _BOOL_FALSE:
        raise ConfigError(f"Invalid ascii_tree value: {raw!r}")
    ascii_tree = raw in _BOOL_TRUE

    # max_depth
    raw = sec.get("max_depth", "5").strip()
    try:
        max_depth = int(raw)
    except ValueError:
        raise ConfigError(f"max_depth must be integer, got {raw!r}")
    if max_depth < 0:
        raise ConfigError(f"max_depth must be >= 0, got {max_depth}")

    return Config(package, repo_url, test_file, test_mode, ascii_tree, max_depth)


def print_config(cfg: Config) -> None:
    print("=== Configuration ===")
    print(f"package    = {cfg.package}")
    print(f"repo_url   = {cfg.repo_url or '(none)'}")
    print(f"test_file  = {cfg.test_file or '(none)'}")
    print(f"test_mode  = {str(cfg.test_mode).lower()}")
    print(f"ascii_tree = {str(cfg.ascii_tree).lower()}")
    print(f"max_depth  = {cfg.max_depth}")
    print()
