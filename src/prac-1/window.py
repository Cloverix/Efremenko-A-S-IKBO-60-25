"""Графический интерфейс эмулятора терминала."""
import tkinter as tk
from tkinter import font
from pathlib import Path
import getpass
import platform
import sys
from configuration import (
    Configuration,
    parse_cli_args,
    parse_config_file,
    merge_configuration,
)

WINDOW_GEOMETRY = "900x600"
FONT_SIZE = 10
PADDING = 8
RET_SUCCESS = 0
RET_EXIT = 1
RET_CMD_NOT_FOUND = -1


class TerminalEmulator:
    """Класс графического эмулятора терминала."""

    def __init__(self, root: tk.Tk, configuration: Configuration):
        """Инициализирует окно и виджеты."""
        self.root = root
        self.root.title("Терминал")
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.configure(bg="#0c0c0c")

        self.term_font = font.Font(
            family="DejaVu Sans Mono",
            size=FONT_SIZE
        )

        self.text = tk.Text(
            root,
            bg="#0c0c0c",
            fg="#cccccc",
            insertbackground="#cccccc",
            selectbackground="#264f78",
            font=self.term_font,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=PADDING,
            pady=PADDING,
        )
        self.text.pack(fill="both", expand=True)

        self.text.tag_config("prompt", foreground="#4ec9b0")
        self.text.tag_config("error", foreground="#f44747")
        self.text.tag_config("success", foreground="#6a9955")
        self.text.tag_config("info", foreground="#569cd6")

        self.username = getpass.getuser()
        self.hostname = platform.node()
        self.cwd = configuration.vfs or Path.home()
        self.script_file = configuration.script

        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Key>", self.on_key)

        self.print_welcome()
        script_result = self.execute_script()
        if script_result == RET_SUCCESS:
            self.insert_prompt()

    def print_welcome(self) -> None:
        """Выводит приветствие."""
        self.text.insert(
            "end", "Добро пожаловать в эмулятор терминала!\n", "info"
        )
        self.text.insert("end", "Введите 'help' для списка команд.\n\n")

    def get_prompt(self) -> str:
        """Возвращает строку приглашения."""
        return f"{self.username}@{self.hostname}:{self.cwd}> "

    def insert_prompt(self) -> None:
        """Вставляет приглашение ввода."""
        self.text.insert("end", self.get_prompt(), "prompt")
        self.text.mark_set("insert", "end-1c")
        self.text.see("end")

    def _prompt_end(self) -> str | None:
        """Возвращает индекс конца приглашения."""
        ranges = self.text.tag_ranges("prompt")
        if not ranges:
            return None
        return self.text.index(ranges[-1])

    def get_current_input(self) -> str:
        """Получает введенный текст."""
        end = self._prompt_end()
        if end is None:
            return ""
        return self.text.get(end, "end-1c")

    def on_key(self, event: tk.Event) -> None:
        """Блокирует редактирование до приглашения."""
        if event.keysym in (
            "Up", "Down", "Return", "BackSpace",
            "Left", "Right", "Home", "End",
            "Prior", "Next"
        ):
            return
        end = self._prompt_end()
        if end and self.text.compare("insert", "<=", end):
            self.text.mark_set("insert", "end-1c")

    def on_backspace(self, event: tk.Event) -> str | None:
        """Блокирует удаление приглашения."""
        end = self._prompt_end()
        if end and self.text.compare("insert", "<=", end):
            return "break"
        return None

    def on_enter(self, event: tk.Event) -> str:
        """Обрабатывает Enter."""
        raw = self.get_current_input()
        self.text.insert("end", "\n")
        self.execute(raw.strip())
        self.insert_prompt()
        return "break"

    def _cmd_help(self, args: list[str]) -> int:
        """Команда help."""
        self.write("Доступные команды:\n")
        self.write("  help     - показать это сообщение\n")
        self.write("  echo     - вывести текст\n")
        self.write("  clear    - очистить экран\n")
        self.write("  exit     - закрыть терминал\n")
        self.write("  ls       - список содержимого директории\n")
        self.write("  cd       - сменить директорию\n")
        return RET_SUCCESS

    def _cmd_echo(self, args: list[str]) -> int:
        """Команда echo."""
        self.write(" ".join(args) + "\n")
        return RET_SUCCESS

    def _cmd_clear(self, args: list[str]) -> int:
        """Команда clear."""
        self.text.delete("1.0", "end")
        return RET_SUCCESS

    def _cmd_exit(self, args: list[str]) -> int:
        """Команда exit."""
        self.root.destroy()
        return RET_EXIT

    def _cmd_ls(self, args: list[str]) -> int:
        """Команда ls."""
        if not self.cwd.is_dir():
            return RET_CMD_NOT_FOUND

        files = []
        dirs = []
        for item in self.cwd.iterdir():
            if item.name[0] == '.':
                continue
            if item.is_file():
                files.append(item.name)
            elif item.is_dir():
                dirs.append(item.name)
        for dir_name in dirs:
            self.write(dir_name + "  ", "info")
        for file_name in files:
            self.write(file_name + "  ")
        self.write('\n')
        return RET_SUCCESS

    def _cmd_cd(self, args: list[str]) -> int:
        """Команда cd."""
        if not args:
            self.cwd = Path.home()
            return RET_SUCCESS
        if args[0] == ".":
            return RET_SUCCESS
        if args[0] == "..":
            self.cwd = self.cwd.parent
            return RET_SUCCESS

        target_dir = self.cwd / Path(args[0]).expanduser()
        if not target_dir.is_dir():
            self.write(
                f"'{args[0]}' не является директорией\n", "error"
            )
            return RET_SUCCESS
        self.cwd = target_dir
        return RET_SUCCESS

    def execute(self, cmd_line: str) -> int:
        """Выполняет введенную команду."""
        if not cmd_line:
            return RET_CMD_NOT_FOUND

        parts = cmd_line.split()
        cmd, args = parts[0], parts[1:]

        # Словарь снижает цикломатическую сложность (Ц1)
        commands = {
            "help": self._cmd_help,
            "echo": self._cmd_echo,
            "clear": self._cmd_clear,
            "exit": self._cmd_exit,
            "ls": self._cmd_ls,
            "cd": self._cmd_cd,
        }

        handler = commands.get(cmd)
        if handler:
            return handler(args)

        self.write(f"Команда не найдена: {cmd}\n", "error")
        return RET_CMD_NOT_FOUND

    def write(self, text: str, tag: str | None = None) -> None:
        """Вставляет текст в виджет."""
        self.text.insert("end", text, tag)

    def execute_script(self) -> int:
        """Выполняет стартовый скрипт."""
        if self.script_file is None:
            return RET_SUCCESS

        commands_raw = self.script_file.read_text(
            encoding="utf-8"
        ).strip().splitlines()

        commands = [cmd.strip() for cmd in commands_raw if cmd.strip()]

        for cmd in commands:
            self.insert_prompt()
            self.write(f"{cmd}\n")
            result = self.execute(cmd)
            if result == RET_EXIT:
                msg = "Предупреждение: в стартовом скрипте запрещена exit"
                print(msg, file=sys.stderr)
                return RET_EXIT
            if result == RET_CMD_NOT_FOUND:
                self.write(
                    f"Ошибка в скрипте: команда '{cmd}'\n", "error"
                )
                self.insert_prompt()
                return RET_CMD_NOT_FOUND
        self.write('\n')
        return RET_SUCCESS


if __name__ == "__main__":
    conf = parse_cli_args()
    if conf.config is not None:
        xml_conf = parse_config_file(str(conf.config))
        conf = merge_configuration(conf, xml_conf)

    root = tk.Tk()
    app = TerminalEmulator(root, conf)
    root.mainloop()