import tkinter as tk
from tkinter import font
from pathlib import Path
import getpass
import platform
from configuration import Configuration, parseCLIArgs, parseConfigFile, mergeConfiguration
import sys


class TerminalEmulator:
    def __init__(self, root, configuration: Configuration):
        self.root = root
        self.root.title("Терминал")
        self.root.geometry("900x600")
        self.root.configure(bg="#0c0c0c")

        self.term_font = font.Font(family="DejaVu Sans Mono", size=10)
        
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
            padx=8,
            pady=8,
        )
        self.text.pack(fill="both", expand=True)

        self.text.tag_config("prompt", foreground="#4ec9b0")
        self.text.tag_config("error",  foreground="#f44747")
        self.text.tag_config("success", foreground="#6a9955")
        self.text.tag_config("info",   foreground="#569cd6")

        self.username = getpass.getuser()
        self.hostname = platform.node()
        self.cwd = configuration.vfs if configuration.vfs is not None else Path.home()
        self.scriptFile = configuration.script

        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Key>", self.on_key)

        self.print_welcome()
        scriptResult = self.exec_script()
        if scriptResult == 0:
            self.insert_prompt()

    def print_welcome(self):
        self.text.insert("end", "Добро пожаловать в эмулятор терминала!\n", "info")
        self.text.insert("end", "Введите 'help' для списка команд.\n\n")

    def get_prompt(self):
        return f"{self.username}@{self.hostname}:{self.cwd}> "

    def insert_prompt(self):
        self.text.insert("end", self.get_prompt(), "prompt")
        self.text.mark_set("insert", "end-1c")
        self.text.see("end")

    def _prompt_end(self):
        ranges = self.text.tag_ranges("prompt")
        if not ranges:
            return None
        return self.text.index(ranges[-1])

    def get_current_input(self):
        end = self._prompt_end()
        if end is None:
            return ""
        return self.text.get(end, "end-1c")

    def on_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "BackSpace",
                            "Left", "Right", "Home", "End", "Prior", "Next"):
            return
        end = self._prompt_end()
        if end and self.text.compare("insert", "<=", end):
            self.text.mark_set("insert", "end-1c")

    def on_backspace(self, event):
        end = self._prompt_end()
        if end and self.text.compare("insert", "<=", end):
            return "break"

    def replace_current_input(self, new_text):
        end = self._prompt_end()
        if end is None:
            return
        self.text.delete(end, "end-1c")
        self.text.insert("end", new_text)
        self.text.see("end")

    def on_enter(self, event):
        raw = self.get_current_input()
        self.text.insert("end", "\n")

        cmd = raw.strip()

        self.execute(cmd)
        self.insert_prompt()
        return "break"

    def execute(self, cmd_line):
        # проверка на пустую команду
        if not cmd_line:
            return -1

        parts = cmd_line.split()
        cmd, args = parts[0], parts[1:]

        if cmd == "help":
            self.write("Доступные команды:\n")
            self.write("  help     - показать это сообщение\n")
            self.write("  echo     - вывести текст\n")
            self.write("  clear    - очистить экран\n")
            self.write("  exit     - закрыть терминал\n")
            self.write("  ls       - вывести список содержимого директории\n")
            return 0
        elif cmd == "echo":
            self.write(" ".join(args) + "\n")
            return 0
        elif cmd == "clear":
            self.text.delete("1.0", "end")
            return 0
        elif cmd == "exit":
            self.root.destroy()
            # возвращаем специальный код, говорящий о том, что окно закрыто
            return 1
        elif cmd == "ls":
            if not self.cwd.is_dir():
                return -1

            files = []
            dirs = []
            for item in self.cwd.iterdir():
                if item.name[0] == '.':
                    continue
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    dirs.append(item.name)
            for dirName in dirs:
                self.write(dirName + "  ", "info")
            for fileName in files:
                self.write(fileName + "  ")
            self.write('\n')
            return 0
        elif cmd == "cd":
            if not args:
                self.cwd = Path.home()
                return 0
            if args[0] == ".":
                return 0
            if args[0] == "..":
                self.cwd = self.cwd.parent
                return 0
            target_dir = self.cwd / Path(args[0]).expanduser()
            if not target_dir.is_dir():
                self.write(f"{target_dir} не является директорией\n", "error")
                return 0
            self.cwd = target_dir
            return 0
        else:
            self.write(f"Команда не найдена: {cmd}\n", "error")
            return -1

    def write(self, text, tag=None):
        self.text.insert("end", text, tag)

    def exec_script(self):
        if self.scriptFile is None:
            return 0
        commandsRaw = self.scriptFile.read_text(encoding="utf-8").strip().splitlines()
        commands = []
        for cmd in commandsRaw:
            stripped = cmd.strip()
            if stripped:
                commands.append(stripped)

        for cmd in commands:
            self.insert_prompt()
            self.write(f"{cmd}\n")
            result = self.execute(cmd)
            # код 1 = окно закрыто (команда exit)
            if result == 1:
                print("Предупреждение: в стартовом скрипте запрещена команда exit", file=sys.stderr)
                return 1
            if result == -1:
                self.write(f"Ошибка в скрипте: команда '{cmd}'\n", "error")
                self.insert_prompt()
                return -1
        self.write('\n')
        return 0


if __name__ == "__main__":
    conf = parseCLIArgs()
    if conf.config is not None:
        xmlConf = parseConfigFile(str(conf.config))
        conf = mergeConfiguration(conf, xmlConf)

    root = tk.Tk()
    app = TerminalEmulator(root, conf)
    root.mainloop()