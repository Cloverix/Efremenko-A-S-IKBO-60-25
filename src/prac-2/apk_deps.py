"""Модуль визуализации графа зависимостей Alpine Linux (apk)."""
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

DEFAULT_TIMEOUT = 30
CLI_TIMEOUT = 60
MIN_DEPTH = 0
RET_SUCCESS = 0
RET_CONFIG_ERROR = 2
RET_CMD_EXIT = 1
RET_CMD_NOT_FOUND = -1

# Регулярное выражение вынесено на уровень модуля
NAME_REGEX = re.compile(r"[A-Z][A-Z0-9_]*")


@dataclass
class Config:
    """Конфигурация приложения."""
    package: str
    repo_url: Optional[str]
    test_file: Optional[str]
    test_mode: bool
    ascii_tree: bool
    max_depth: int


class ConfigError(Exception):
    """Исключение при ошибках конфигурации."""


_BOOL_TRUE = {"true", "1", "yes"}
_BOOL_FALSE = {"false", "0", "no"}


def _parse_bool(val: str, param_name: str) -> bool:
    """Парсит булево значение."""
    raw = val.strip().lower()
    if raw not in _BOOL_TRUE | _BOOL_FALSE:
        raise ConfigError(f"Invalid {param_name} value: {raw!r}")
    return raw in _BOOL_TRUE


def _parse_int(val: str, param_name: str, min_val: int) -> int:
    """Парсит целочисленное значение."""
    raw = val.strip()
    try:
        res = int(raw)
    except ValueError:
        raise ConfigError(f"{param_name} must be integer, got {raw!r}")
    if res < min_val:
        raise ConfigError(f"{param_name} must be >= {min_val}")
    return res


def _validate_paths(
    cfg: Config, test_file: Optional[str], repo_url: Optional[str]
) -> None:
    """Валидирует пути и URL в зависимости от режима."""
    if cfg.test_mode:
        if not test_file:
            raise ConfigError("'test_file' is required when test_mode=true")
        if not Path(test_file).exists():
            raise ConfigError(f"test_file not found: {test_file}")
    else:
        if not repo_url:
            raise ConfigError("'repo_url' is required when test_mode=false")
        if not re.match(r"^https?://", repo_url):
            raise ConfigError(f"repo_url must be http(s) URL: {repo_url!r}")


def load_config(path: Path) -> Config:
    """Загружает и валидирует конфигурацию из INI."""
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

    package = sec.get("package", "").strip()
    if not package:
        raise ConfigError("Parameter 'package' is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", package):
        raise ConfigError(f"Invalid package name: {package!r}")

    test_mode = _parse_bool(sec.get("test_mode", "false"), "test_mode")
    test_file = sec.get("test_file", "").strip() or None
    repo_url = sec.get("repo_url", "").strip() or None
    ascii_tree = _parse_bool(sec.get("ascii_tree", "true"), "ascii_tree")
    max_depth = _parse_int(sec.get("max_depth", "5"), "max_depth", MIN_DEPTH)

    cfg = Config(
        package, repo_url, test_file, test_mode, ascii_tree, max_depth
    )
    _validate_paths(cfg, test_file, repo_url)
    return cfg


def print_config(cfg: Config) -> None:
    """Выводит текущую конфигурацию."""
    print("=== Configuration ===")
    print(f"package    = {cfg.package}")
    print(f"repo_url   = {cfg.repo_url or '(none)'}")
    print(f"test_file  = {cfg.test_file or '(none)'}")
    print(f"test_mode  = {str(cfg.test_mode).lower()}")
    print(f"ascii_tree = {str(cfg.ascii_tree).lower()}")
    print(f"max_depth  = {cfg.max_depth}")
    print()


class TestRepo:
    """Провайдер зависимостей из тестового файла."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.deps: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        """Загружает данные из файла."""
        with self.path.open("r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, 1):
                self._parse_line(raw, lineno)

    def _parse_line(self, raw: str, lineno: int) -> None:
        """Парсит одну строку."""
        line = raw.split("#", 1)[0].strip()
        if not line:
            return
        if ":" in line:
            name, rhs = line.split(":", 1)
            name = name.strip()
            deps = [d for d in re.split(r"[\s,]+", rhs.strip()) if d]
        else:
            parts = re.split(r"[\s,]+", line)
            name, deps = parts[0], parts[1:]

        if not NAME_REGEX.fullmatch(name):
            raise ConfigError(
                f"Invalid package name in {self.path}:{lineno}: {name!r}"
            )
        for d in deps:
            if not NAME_REGEX.fullmatch(d):
                raise ConfigError(
                    f"Invalid dep name in {self.path}:{lineno}: {d!r}"
                )
        self.deps.setdefault(name, [])
        self.deps[name].extend(
            d for d in deps if d not in self.deps[name]
        )

    def get_dependencies(self, name: str) -> List[str]:
        """Возвращает прямые зависимости."""
        return list(self.deps.get(name, []))


class ApkRepo:
    """Провайдер зависимостей из репозитория Alpine Linux."""

    def __init__(self, repo_url: str):
        self.repo_url = repo_url.rstrip("/")
        self.index: Dict[str, List[str]] = {}
        self._load_index()

    def _fetch_index_bytes(self) -> bytes:
        """Скачивает APKINDEX.tar.gz."""
        url = f"{self.repo_url}/APKINDEX.tar.gz"
        try:
            with urllib.request.urlopen(url, timeout=DEFAULT_TIMEOUT) as r:
                return r.read()
        except Exception as e:
            raise ConfigError(f"Failed to download {url}: {e}")

    def _load_index(self) -> None:
        """Загружает и распаковывает индекс."""
        raw = self._fetch_index_bytes()
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                member = next(
                    (
                        m for m in tf.getmembers()
                        if m.name.endswith("APKINDEX")
                    ),
                    None
                )
                if member is None:
                    raise ConfigError("APKINDEX not found in archive")
                data = tf.extractfile(member).read().decode(
                    "utf-8", "replace"
                )
        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Cannot extract APKINDEX: {e}")
        self._parse_index(data)

    @staticmethod
    def _parse_dep_token(tok: str) -> Optional[str]:
        """Парсит токен зависимости."""
        if not tok or tok.startswith("!"):
            return None
        base = re.split(r"[<>=~]", tok, 1)[0]
        if base.startswith(("so:", "cmd:", "pc:")):
            return None
        if ":" in base:
            base = base.split(":", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", base):
            return None
        return base

    def _parse_index(self, text: str) -> None:
        """Парсит содержимое APKINDEX."""
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            pkg = None
            deps_raw = ""
            for line in block.splitlines():
                if line.startswith("P:"):
                    pkg = line[2:].strip()
                elif line.startswith("D:"):
                    deps_raw = line[2:].strip()
            if not pkg:
                continue
            deps: List[str] = []
            for tok in deps_raw.split():
                name = self._parse_dep_token(tok)
                if name and name not in deps:
                    deps.append(name)
            self.index[pkg] = deps

    def get_dependencies(self, name: str) -> List[str]:
        """Возвращает прямые зависимости."""
        if name not in self.index:
            raise ConfigError(
                f"Package {name!r} not found in repository {self.repo_url}"
            )
        return list(self.index[name])


@dataclass
class GraphNode:
    """Узел графа зависимостей."""
    name: str
    children: List["GraphNode"] = field(default_factory=list)
    cycle: bool = False
    truncated: bool = False
    missing: bool = False


def build_graph(
    pkg: str,
    get_deps: Callable[[str], List[str]],
    max_depth: int
) -> GraphNode:
    """Строит дерево зависимостей через рекурсивный DFS."""
    root = GraphNode(pkg)

    def dfs(node: GraphNode, depth: int, path: Set[str]) -> None:
        if depth >= max_depth:
            try:
                deps = get_deps(node.name)
            except ConfigError:
                deps = []
            if deps:
                node.truncated = True
            return

        try:
            deps = get_deps(node.name)
        except ConfigError:
            node.missing = True
            return

        for d in deps:
            child = GraphNode(d)
            node.children.append(child)
            if d in path:
                child.cycle = True
                continue
            dfs(child, depth + 1, path | {d})

    dfs(root, 0, {pkg})
    return root


def collect_edges(
    node: GraphNode,
    seen: Optional[Set[Tuple[str, str]]] = None
) -> List[Tuple[str, str]]:
    """Собирает все уникальные ребра графа."""
    if seen is None:
        seen = set()
    edges: List[Tuple[str, str]] = []
    for c in node.children:
        key = (node.name, c.name)
        if key not in seen:
            seen.add(key)
            edges.append(key)
        if not c.cycle:
            edges.extend(collect_edges(c, seen))
    return edges


def load_order(
    pkg: str,
    get_deps: Callable[[str], List[str]],
    max_depth: int
) -> List[str]:
    """Возвращает порядок загрузки зависимостей."""
    order: List[str] = []
    on_stack: Set[str] = set()
    done: Set[str] = set()

    def dfs(name: str, depth: int) -> None:
        if name in done:
            return
        on_stack.add(name)
        if depth < max_depth:
            try:
                deps = get_deps(name)
            except ConfigError:
                deps = []
            for d in deps:
                if d in on_stack:
                    continue
                dfs(d, depth + 1)
        on_stack.discard(name)
        if name not in done:
            done.add(name)
            order.append(name)

    dfs(pkg, 0)
    return order


def apk_load_order_via_cli(pkg: str) -> Optional[List[str]]:
    """Получает порядок через штатный apk."""
    try:
        res = subprocess.run(
            ["apk", "info", "-R", "-q", pkg],
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None

    seen = set()
    out = []
    for line in res.stdout.splitlines():
        n = line.strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _tree_label(node: GraphNode) -> str:
    """Формирует метку узла."""
    label = node.name
    if node.truncated:
        label += " ..."
    if node.cycle:
        label += " (cycle)"
    if node.missing:
        label += " (missing)"
    return label


def _print_ascii_node(
    node: GraphNode,
    prefix: str,
    is_last: bool
) -> None:
    """Рекурсивно выводит узел ASCII-дерева."""
    print(prefix + ("`-- " if is_last else "|-- ") + _tree_label(node))
    if node.cycle:
        return
    new_prefix = prefix + ("    " if is_last else "|   ")
    for i, c in enumerate(node.children):
        _print_ascii_node(
            c, new_prefix, i == len(node.children) - 1
        )


def print_ascii_tree(root: GraphNode) -> None:
    """Выводит граф в виде ASCII-дерева."""
    print(_tree_label(root))
    for i, c in enumerate(root.children):
        _print_ascii_node(c, "", i == len(root.children) - 1)


def _mermaid_id(name: str) -> str:
    """Создает безопасный ID для Mermaid."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def print_mermaid(root: GraphNode) -> None:
    """Выводит граф в виде Mermaid диаграммы."""
    edges = collect_edges(root)
    nodes = {root.name}
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)

    print("graph TD")
    for n in sorted(nodes):
        print(f'    {_mermaid_id(n)}["{n}"]')
    for a, b in edges:
        print(f"    {_mermaid_id(a)} --> {_mermaid_id(b)}")


def _init_provider(cfg: Config):
    """Инициализирует источник данных."""
    if cfg.test_mode:
        return TestRepo(cfg.test_file)
    return ApkRepo(cfg.repo_url)


def _handle_direct_only(direct: List[str], package: str) -> int:
    """Выводит только прямые зависимости."""
    print(f"Direct dependencies of {package} ({len(direct)}):")
    for d in direct:
        print(f"  {d}")
    return RET_SUCCESS


def _handle_load_order(cfg: Config, get_deps: Callable) -> int:
    """Выводит порядок загрузки и сравнивает."""
    try:
        order = load_order(cfg.package, get_deps, cfg.max_depth)
    except ConfigError as e:
        print(f"[load order error] {e}", file=sys.stderr)
        return RET_CONFIG_ERROR

    print(f"Load order for {cfg.package} (max_depth={cfg.max_depth}):")
    for i, n in enumerate(order, 1):
        print(f"  {i}. {n}")

    if not cfg.test_mode:
        real = apk_load_order_via_cli(cfg.package)
        print()
        if real is None:
            print("[comparison] apk CLI недоступен")
        else:
            print("[comparison] apk info -R -q:")
            for n in real:
                print(f"  {n}")
            if real != order:
                print(
                    "\n[diff] Порядок отличается. Возможные причины:\n"
                    "  - apk раскрывает виртуальные provides,\n"
                    "  - учитывает приоритеты репозиториев,\n"
                    "  - у apk свой порядок обхода."
                )
    return RET_SUCCESS


def _handle_visualization(cfg: Config, get_deps: Callable) -> None:
    """Выводит ASCII-дерево и Mermaid."""
    graph = build_graph(cfg.package, get_deps, cfg.max_depth)
    if cfg.ascii_tree:
        print(f"=== ASCII tree (max_depth={cfg.max_depth}) ===")
        print_ascii_tree(graph)
        print()

    print("=== Mermaid diagram ===")
    print_mermaid(graph)
    print()


def _parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    ap = argparse.ArgumentParser(description="apk visualizer")
    ap.add_argument("-c", "--config", default="config/config.ini")
    ap.add_argument("--show-config-only", action="store_true")
    ap.add_argument("--direct-only", action="store_true")
    ap.add_argument("--load-order", action="store_true")
    return ap.parse_args()


def main() -> int:
    """Точка входа."""
    args = _parse_args()
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as e:
        print(f"[config error] {e}", file=sys.stderr)
        return RET_CONFIG_ERROR

    print_config(cfg)
    if args.show_config_only:
        return RET_SUCCESS

    try:
        provider = _init_provider(cfg)
    except ConfigError as e:
        print(f"[provider error] {e}", file=sys.stderr)
        return RET_CONFIG_ERROR

    get_deps = provider.get_dependencies

    try:
        direct = get_deps(cfg.package)
    except ConfigError as e:
        print(f"[package error] {e}", file=sys.stderr)
        return RET_CONFIG_ERROR

    if args.direct_only:
        return _handle_direct_only(direct, cfg.package)

    if args.load_order:
        return _handle_load_order(cfg, get_deps)

    _handle_visualization(cfg, get_deps)
    return RET_SUCCESS


if __name__ == "__main__":
    sys.exit(main())