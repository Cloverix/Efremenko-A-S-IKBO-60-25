import tkinter as tk
from tkinter import font
import getpass
import platform
from pathlib import Path


class TerminalEmulator:
    def __init__(self, root, cwd = Path.home()):
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
        self.cwd = Path(cwd).expanduser()
        
        self.prompt = f"{self.username}@{self.hostname}:{self.cwd}> "

        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Key>", self.on_key)

        self.print_welcome()
        self.insert_prompt()

    def print_welcome(self):
        self.text.insert("end", "Добро пожаловать в эмулятор терминала!\n", "info")
        self.text.insert("end", "Введите 'help' для списка команд.\n\n")

    def insert_prompt(self):
        self.text.insert("end", self.prompt, "prompt")
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
        if not cmd_line:
            return

        parts = cmd_line.split()
        cmd, args = parts[0], parts[1:]

        if cmd == "help":
            self.write("Доступные команды:\n")
            self.write("  help     - показать это сообщение\n")
            self.write("  echo     - вывести текст\n")
            self.write("  clear    - очистить экран\n")
            self.write("  exit     - закрыть терминал\n")
            self.write("  ls       - вывести список содержимого директории\n")
        elif cmd == "echo":
            self.write(" ".join(args) + "\n")
        elif cmd == "clear":
            self.text.delete("1.0", "end")
        elif cmd == "exit":
            self.root.destroy()
        elif cmd == "ls":
            if not self.cwd.exists():
                return

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
        else:
            self.write(f"Команда не найдена: {cmd}\n", "error")

    def write(self, text, tag=None):
        self.text.insert("end", text, tag)


if __name__ == "__main__":
    root = tk.Tk()
    app = TerminalEmulator(root, "foo")
    root.mainloop()