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


class TestRepo:
    _NAME_RE = re.compile(r"[A-Z][A-Z0-9_]*")

    def __init__(self, path: str):
        self.path = Path(path)
        self.deps: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, 1):
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if ":" in line:
                    name, rhs = line.split(":", 1)
                    name = name.strip()
                    deps = [d for d in re.split(r"[\s,]+", rhs.strip()) if d]
                else:
                    parts = re.split(r"[\s,]+", line)
                    name, deps = parts[0], parts[1:]

                if not self._NAME_RE.fullmatch(name):
                    raise ConfigError(
                        f"Invalid package name in {self.path}:{lineno}: {name!r}"
                    )
                for d in deps:
                    if not self._NAME_RE.fullmatch(d):
                        raise ConfigError(
                            f"Invalid dep name in {self.path}:{lineno}: {d!r}"
                        )
                self.deps.setdefault(name, [])
                self.deps[name].extend(d for d in deps if d not in self.deps[name])

    def get_dependencies(self, name: str) -> List[str]:
        return list(self.deps.get(name, []))


class ApkRepo:
    """Скачивает APKINDEX.tar.gz из репозитория и парсит поле D: (Dependencies)."""

    def __init__(self, repo_url: str):
        self.repo_url = repo_url.rstrip("/")
        self.index: Dict[str, List[str]] = {}
        self._load_index()

    def _fetch_index_bytes(self) -> bytes:
        url = f"{self.repo_url}/APKINDEX.tar.gz"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            raise ConfigError(f"Failed to download {url}: {e}")

    def _load_index(self) -> None:
        raw = self._fetch_index_bytes()
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                member = next(
                    (m for m in tf.getmembers() if m.name == "APKINDEX" or m.name.endswith("/APKINDEX")),
                    None
                )
                if member is None:
                    raise ConfigError("APKINDEX not found in archive")
                data = tf.extractfile(member).read().decode("utf-8", "replace")
        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Cannot extract APKINDEX: {e}")
        self._parse_index(data)

    @staticmethod
    def _parse_dep_token(tok: str) -> Optional[str]:
        if not tok or tok.startswith("!"):        # конфликт
            return None
        base = re.split(r"[<>=~]", tok, 1)[0]     # отбрасываем версию
        if base.startswith(("so:", "cmd:", "pc:")):  # виртуальные provides
            return None
        if ":" in base:                            # прочие виртуальные
            base = base.split(":", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", base):
            return None
        return base

    def _parse_index(self, text: str) -> None:
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
        if name not in self.index:
            raise ConfigError(
                f"Package {name!r} not found in repository {self.repo_url}"
            )
        return list(self.index[name])


@dataclass
class GraphNode:
    name: str
    children: List["GraphNode"] = field(default_factory=list)
    cycle: bool = False
    truncated: bool = False
    missing: bool = False


def build_graph(pkg: str,
                get_deps: Callable[[str], List[str]],
                max_depth: int) -> GraphNode:
    """Дерево зависимостей через рекурсивный DFS.

    - max_depth ограничивает раскрытие (0 — только корень);
    - цикл помечается флагом cycle и не раскрывается дальше;
    - отсутствующий пакет помечается missing.
    """
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


def collect_edges(node: GraphNode,
                  seen: Optional[Set[Tuple[str, str]]] = None
                  ) -> List[Tuple[str, str]]:
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


def load_order(pkg: str,
               get_deps: Callable[[str], List[str]],
               max_depth: int) -> List[str]:
    """Порядок загрузки: зависимости раньше зависящих от них."""
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
                    continue                     # цикл
                dfs(d, depth + 1)
        on_stack.discard(name)
        if name not in done:
            done.add(name)
            order.append(name)

    dfs(pkg, 0)
    return order


def apk_load_order_via_cli(pkg: str) -> Optional[List[str]]:
    try:
        res = subprocess.run(
            ["apk", "info", "-R", "-q", pkg],
            capture_output=True, text=True, timeout=60,
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
    label = node.name
    if node.truncated:
        label += " ..."
    if node.cycle:
        label += " (cycle)"
    if node.missing:
        label += " (missing)"
    return label


def _print_ascii_node(node: GraphNode, prefix: str, is_last: bool) -> None:
    print(prefix + ("`-- " if is_last else "|-- ") + _tree_label(node))
    if node.cycle:
        return
    new_prefix = prefix + ("    " if is_last else "|   ")
    for i, c in enumerate(node.children):
        _print_ascii_node(c, new_prefix, i == len(node.children) - 1)


def print_ascii_tree(root: GraphNode) -> None:
    print(_tree_label(root))
    for i, c in enumerate(root.children):
        _print_ascii_node(c, "", i == len(root.children) - 1)


def _mermaid_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def print_mermaid(root: GraphNode) -> None:
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


def main() -> int:
    ap = argparse.ArgumentParser(description="apk dependency graph visualizer")
    ap.add_argument("-c", "--config", default="config.ini",
                    help="path to INI file (default: config.ini)")
    ap.add_argument("--show-config-only", action="store_true",
                    help="Stage 1: только вывести параметры и выйти")
    ap.add_argument("--direct-only", action="store_true",
                    help="Stage 2: вывести только прямые зависимости")
    ap.add_argument("--load-order", action="store_true",
                    help="Stage 4: вывести порядок загрузки и сравнить с apk")
    args = ap.parse_args()

    # --- этап 1: конфиг ---
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as e:
        print(f"[config error] {e}", file=sys.stderr)
        return 2

    print_config(cfg)
    if args.show_config_only:
        return 0

    # --- этап 2-3: источник данных ---
    if cfg.test_mode:
        try:
            provider = TestRepo(cfg.test_file)
        except ConfigError as e:
            print(f"[test repo error] {e}", file=sys.stderr)
            return 2
    else:
        try:
            provider = ApkRepo(cfg.repo_url)
        except ConfigError as e:
            print(f"[apk repo error] {e}", file=sys.stderr)
            return 2

    get_deps = provider.get_dependencies

    # проверяем существование заданного пакета
    try:
        direct = get_deps(cfg.package)
    except ConfigError as e:
        print(f"[package error] {e}", file=sys.stderr)
        return 2

    # --- этап 2: прямые зависимости ---
    if args.direct_only:
        print(f"Direct dependencies of {cfg.package} ({len(direct)}):")
        for d in direct:
            print(f"  {d}")
        return 0

    # --- этап 4: порядок загрузки ---
    if args.load_order:
        try:
            order = load_order(cfg.package, get_deps, cfg.max_depth)
        except ConfigError as e:
            print(f"[load order error] {e}", file=sys.stderr)
            return 2
        print(f"Load order for {cfg.package} (max_depth={cfg.max_depth}):")
        for i, n in enumerate(order, 1):
            print(f"  {i}. {n}")

        if not cfg.test_mode:
            real = apk_load_order_via_cli(cfg.package)
            print()
            if real is None:
                print("[comparison] apk CLI недоступен или команда не удалась")
            else:
                print("[comparison] apk info -R -q:")
                for n in real:
                    print(f"  {n}")
                if real != order:
                    print(
                        "\n[diff] Порядок отличается. Возможные причины:\n"
                        "  - apk раскрывает виртуальные provides (so:/cmd:),\n"
                        "  - учитывает приоритеты репозиториев и пиннинг версий,\n"
                        "  - у apk свой порядок обхода, а мы идём в порядке,\n"
                        "    в котором зависимости перечислены в APKINDEX."
                    )
        return 0

    # --- этап 5: визуализация ---
    graph = build_graph(cfg.package, get_deps, cfg.max_depth)

    if cfg.ascii_tree:
        print(f"=== ASCII tree (max_depth={cfg.max_depth}) ===")
        print_ascii_tree(graph)
        print()

    print("=== Mermaid diagram ===")
    print_mermaid(graph)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
