"""JARVIS NEON — локальный голосовой помощник для Windows.
Команды, приложения и сценарии работают без API-ключа.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

APP_NAME = "JARVIS NEON"
IS_WINDOWS = platform.system() == "Windows"
BG = "#050b18"
PANEL = "#0a1729"
PANEL2 = "#0d2038"
BORDER = "#163e61"
CYAN = "#42dcff"
BLUE = "#258cff"
PURPLE = "#8b72ff"
GREEN = "#53f3bb"
TEXT = "#d9f4ff"
MUTED = "#7895b2"
RED = "#ff647c"

DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "JarvisNeon"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SCENARIO_FILE = DATA_DIR / "scenarios.json"
LOG_FILE = DATA_DIR / "jarvis.log"

WAKE_RE = re.compile(r"\b(джарвис|джарвиз|джервис|jarvis)\b[\s,.!?]*", re.I)

# Aliases and paths for common apps. Existing Start Menu shortcuts are also searched,
# so this works for apps installed in non-default folders.
APPS = {
    "блокнот": {"aliases": ["блокнот", "notepad"], "exe": "notepad.exe", "proc": ["notepad.exe"], "shortcuts": ["блокнот", "notepad"]},
    "калькулятор": {"aliases": ["калькулятор", "calculator", "calc"], "exe": "calc.exe", "proc": ["CalculatorApp.exe", "calc.exe"], "shortcuts": ["калькулятор", "calculator"]},
    "проводник": {"aliases": ["проводник", "explorer", "файлы"], "exe": "explorer.exe", "proc": ["explorer.exe"], "shortcuts": ["проводник", "file explorer"]},
    "paint": {"aliases": ["paint", "паинт", "пейнт"], "exe": "mspaint.exe", "proc": ["mspaint.exe"], "shortcuts": ["paint"]},
    "диспетчер задач": {"aliases": ["диспетчер задач", "task manager"], "exe": "taskmgr.exe", "proc": ["Taskmgr.exe"], "shortcuts": ["диспетчер задач", "task manager"]},
    "терминал": {"aliases": ["терминал", "командная строка", "cmd"], "exe": "cmd.exe", "proc": ["cmd.exe", "WindowsTerminal.exe"], "shortcuts": ["terminal", "командная строка"]},
    "chrome": {"aliases": ["google chrome", "гугл хром", "chrome", "хром"], "exe": "chrome.exe", "proc": ["chrome.exe"], "shortcuts": ["google chrome", "chrome"], "paths": [r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe", r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"]},
    "firefox": {"aliases": ["firefox", "фаерфокс", "файрфокс"], "exe": "firefox.exe", "proc": ["firefox.exe"], "shortcuts": ["mozilla firefox", "firefox"], "paths": [r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe", r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"]},
    "edge": {"aliases": ["microsoft edge", "edge", "эдж", "майкрософт эдж"], "exe": "msedge.exe", "proc": ["msedge.exe"], "shortcuts": ["microsoft edge", "edge"], "paths": [r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe", r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"]},
    "discord": {"aliases": ["discord", "дискорд"], "exe": "Discord.exe", "proc": ["Discord.exe"], "shortcuts": ["discord"], "paths": [r"%LOCALAPPDATA%\Discord\app-*/Discord.exe"]},
    "steam": {"aliases": ["steam", "стим"], "exe": "steam.exe", "proc": ["steam.exe", "steamwebhelper.exe"], "shortcuts": ["steam"], "paths": [r"%PROGRAMFILES(X86)%\Steam\steam.exe", r"%PROGRAMFILES%\Steam\steam.exe"]},
    "spotify": {"aliases": ["spotify", "спотифай"], "exe": "Spotify.exe", "proc": ["Spotify.exe"], "shortcuts": ["spotify"], "paths": [r"%APPDATA%\Spotify\Spotify.exe", r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"]},
    "visual studio code": {"aliases": ["visual studio code", "vs code", "vscode", "вс код", "код"], "exe": "Code.exe", "proc": ["Code.exe"], "shortcuts": ["visual studio code", "vs code"], "paths": [r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe", r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"]},
    "word": {"aliases": ["word", "ворд", "microsoft word"], "exe": "WINWORD.EXE", "proc": ["WINWORD.EXE"], "shortcuts": ["word", "microsoft word"], "paths": [r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE", r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE"]},
    "excel": {"aliases": ["excel", "эксель", "microsoft excel"], "exe": "EXCEL.EXE", "proc": ["EXCEL.EXE"], "shortcuts": ["excel", "microsoft excel"], "paths": [r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE", r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE"]},
    "powerpoint": {"aliases": ["powerpoint", "пауэрпоинт", "поверпоинт"], "exe": "POWERPNT.EXE", "proc": ["POWERPNT.EXE"], "shortcuts": ["powerpoint"], "paths": [r"%PROGRAMFILES%\Microsoft Office\root\Office16\POWERPNT.EXE", r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\POWERPNT.EXE"]},
}

SITES = {
    "ютуб": ("ютуб", "https://www.youtube.com"),
    "youtube": ("ютуб", "https://www.youtube.com"),
    "гугл": ("гугл", "https://www.google.com"),
    "google": ("гугл", "https://www.google.com"),
    "почта": ("почту", "https://mail.google.com"),
    "почту": ("почту", "https://mail.google.com"),
    "gmail": ("почту", "https://mail.google.com"),
    "телеграм": ("телеграм", "https://web.telegram.org"),
    "telegram": ("телеграм", "https://web.telegram.org"),
    "github": ("GitHub", "https://github.com"),
    "гитхаб": ("GitHub", "https://github.com"),
    "браузер": ("браузер", "https://www.google.com"),
    "browser": ("браузер", "https://www.google.com"),
}


def log_line(who: str, text: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} [{who}] {text}\n")
    except OSError:
        pass


def expand_path(raw: str) -> str:
    return os.path.expandvars(os.path.expanduser(raw.replace("%PROGRAMFILES(X86)%", os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))))


def app_paths_registry(exe: str) -> list[str]:
    if not IS_WINDOWS:
        return []
    try:
        import winreg
        locations = [
            (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe}"),
        ]
        out = []
        for root, sub in locations:
            try:
                with winreg.OpenKey(root, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val:
                        out.append(os.path.expandvars(val.strip('"')))
            except OSError:
                continue
        return out
    except Exception:
        return []


def start_menu_links(hints: list[str]) -> list[Path]:
    if not IS_WINDOWS:
        return []
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    matches: list[tuple[int, Path]] = []
    keys = [re.sub(r"[^a-z0-9а-я]", "", h.lower()) for h in hints]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*.lnk"):
                normalized = re.sub(r"[^a-z0-9а-я]", "", path.stem.lower())
                for key in keys:
                    if key and (normalized == key or key in normalized or normalized in key):
                        score = 0 if normalized == key else 1
                        matches.append((score, path))
                        break
        except OSError:
            continue
    matches.sort(key=lambda pair: (pair[0], len(str(pair[1]))))
    return [p for _, p in matches[:8]]


def locate_app(config: dict) -> tuple[str | None, str]:
    """Return (launch target, kind): kind is exe or shortcut."""
    exe = config.get("exe", "")
    if exe:
        # App Paths registry is important for non-standard installations.
        for target in app_paths_registry(exe):
            if Path(target).is_file():
                return target, "exe"
        for raw in config.get("paths", []):
            # Allow wildcard folder versions (e.g. Discord\app-*/Discord.exe).
            expanded = expand_path(raw)
            if "*" in expanded:
                import glob
                for target in sorted(glob.glob(expanded), reverse=True):
                    if Path(target).is_file():
                        return target, "exe"
            elif Path(expanded).is_file():
                return expanded, "exe"
        found = shutil.which(exe)
        if found:
            return found, "exe"
    links = start_menu_links(config.get("shortcuts", []) + config.get("aliases", []))
    if links:
        return str(links[0]), "shortcut"
    return None, ""


def resolve_app_name(name: str) -> str | None:
    target = name.strip().lower()
    # Prefer the longest alias so "Google Chrome" wins over a shorter match.
    candidates = []
    for canonical, config in APPS.items():
        for alias in config["aliases"]:
            a = alias.lower()
            if target == a or (len(a) >= 4 and a in target):
                candidates.append((len(a), canonical))
    return max(candidates)[1] if candidates else None


def process_exists(names: list[str]) -> bool:
    if not IS_WINDOWS:
        return False
    # tasklist does not need psutil and works from a frozen exe too.
    for name in names:
        try:
            result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                                    capture_output=True, text=True, timeout=3,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0 and name.lower() in result.stdout.lower():
                return True
        except Exception:
            pass
    return False


def open_target(name: str) -> str:
    name = name.strip().strip('"')
    if not name:
        return "Скажите или введите название приложения."
    lowered = name.lower()

    # Web sites open in the user's default browser.
    for key, (label, url) in SITES.items():
        # If a name matches a local app alias, prefer the installed app over a website.
        if key in lowered and not resolve_app_name(lowered):
            try:
                ok = webbrowser.open(url, new=2)
                return f"Открываю {label}." if ok else f"Не удалось открыть сайт {url}. Проверьте браузер по умолчанию."
            except Exception as e:
                return f"Не удалось открыть сайт: {e}"

    canonical = resolve_app_name(lowered)
    if canonical:
        config = APPS[canonical]
        target, kind = locate_app(config)
        try:
            if target:
                if kind == "shortcut":
                    os.startfile(target)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen([target], close_fds=True)
                time.sleep(0.9)
                if process_exists(config.get("proc", [])):
                    return f"{canonical}: приложение запущено."
                # A process may launch slowly or be a packaged Windows app.
                time.sleep(1.0)
                if process_exists(config.get("proc", [])):
                    return f"{canonical}: приложение запущено."
                return (f"Windows приняла команду запуска «{canonical}», но процесс не обнаружен. "
                        "Возможно, приложение запускается дольше обычного или его ярлык настроен нестандартно.")
            # System applications can sometimes be located through PATH even when not found above.
            if config.get("exe") and shutil.which(config["exe"]):
                subprocess.Popen([shutil.which(config["exe"])], close_fds=True)
                return f"Запрос на запуск «{canonical}» отправлен Windows."
        except Exception as e:
            log_line("ERROR", f"open {canonical}: {e}")
            return f"Не получилось открыть «{canonical}»: {e}"
        return f"Не нашёл установленное приложение «{canonical}». Проверьте установку либо добавьте его ярлык в меню Пуск."

    # Explicit path / shortcut typed by the user.
    if name.lower().endswith((".exe", ".lnk")):
        candidate = Path(os.path.expandvars(name)).expanduser()
        if candidate.is_file():
            try:
                if IS_WINDOWS:
                    os.startfile(str(candidate))  # type: ignore[attr-defined]
                else:
                    subprocess.Popen([str(candidate)])
                return f"Запрос на запуск «{candidate.name}» отправлен системе."
            except Exception as e:
                return f"Не получилось открыть файл: {e}"
    return f"Не знаю приложение «{name}». Добавьте его в каталог приложений или укажите путь к .exe/.lnk."


def close_target(name: str) -> str:
    """Try a normal close first, then force-terminate only the requested app processes."""
    if not IS_WINDOWS:
        return "Закрытие приложений по имени доступно в Windows."
    lowered = name.lower().strip().strip('"')
    canonical = resolve_app_name(lowered)
    if canonical == "проводник":
        return "Не закрываю Проводник через диспетчер процессов, чтобы не завершить оболочку Windows. Закройте окно Проводника вручную."
    procs = APPS.get(canonical, {}).get("proc", []) if canonical else []
    if not procs and re.fullmatch(r"[A-Za-z0-9_. -]+\.exe", lowered):
        procs = [lowered]
    if not procs:
        return f"Не знаю, какой процесс закрыть: «{name}»."

    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    found = False
    failures: list[str] = []
    for proc in dict.fromkeys(procs):
        if not process_exists([proc]):
            continue
        found = True
        # First ask Windows to close the app normally, allowing it to save/clean up.
        try:
            graceful = subprocess.run(
                ["taskkill", "/IM", proc, "/T"], capture_output=True, text=True,
                errors="replace", timeout=10, creationflags=no_window
            )
            log_line("CLOSE", f"normal {proc}: code={graceful.returncode}; out={graceful.stdout.strip()}; err={graceful.stderr.strip()}")
        except subprocess.TimeoutExpired:
            log_line("CLOSE", f"normal close timeout for {proc}")
        except Exception as e:
            log_line("CLOSE", f"normal close error for {proc}: {e}")

        # Allow GUI apps time to exit naturally before forcing them.
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline and process_exists([proc]):
            time.sleep(0.25)
        if not process_exists([proc]):
            continue

        # Force termination is needed for apps that ignore WM_CLOSE or have background helpers.
        try:
            forced = subprocess.run(
                ["taskkill", "/F", "/IM", proc, "/T"], capture_output=True, text=True,
                errors="replace", timeout=12, creationflags=no_window
            )
            out = (forced.stdout or "").strip()
            err = (forced.stderr or "").strip()
            log_line("CLOSE", f"force {proc}: code={forced.returncode}; out={out}; err={err}")
        except subprocess.TimeoutExpired:
            failures.append(f"{proc}: команда завершения превысила лимит времени")
            continue
        except Exception as e:
            failures.append(f"{proc}: {e}")
            continue

        # Check for a few seconds, since taskkill may take time to stop a process tree.
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and process_exists([proc]):
            time.sleep(0.25)
        if process_exists([proc]):
            detail = err or out or f"taskkill завершился с кодом {forced.returncode}"
            failures.append(f"{proc}: {detail}")

    if not found:
        return f"«{canonical or name}» сейчас не запущено."
    if failures:
        detail = " | ".join(failures)[:500]
        return (f"Не удалось завершить «{canonical or name}»: процесс всё ещё запущен. {detail} "
                "Запустите именно этот Jarvis.exe от имени администратора и проверьте снова. "
                "Подробности записаны в журнал.")
    return f"«{canonical or name}» закрыто. Учтите, что несохранённая работа могла быть потеряна."


def load_scenarios() -> dict[str, list[str]]:
    try:
        with SCENARIO_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): list(v) for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_scenarios(data: dict[str, list[str]]) -> None:
    SCENARIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = SCENARIO_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SCENARIO_FILE)


class Voice:
    """Queued TTS so command processing remains responsive. Uses Russian pyttsx3 voice,
    with Windows SAPI as a fallback."""
    def __init__(self, event_callback):
        self.q: queue.Queue[str | None] = queue.Queue()
        self.event_callback = event_callback
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def say(self, text: str) -> None:
        if text:
            self.q.put(text)

    def _powershell_speak(self, text: str) -> bool:
        if not IS_WINDOWS:
            return False
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'ru-*' } | Select-Object -First 1; "
                  "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
                  "$t = [Console]::In.ReadToEnd(); $s.Speak($t)")
        try:
            subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                           input=text, text=True, capture_output=True, timeout=45,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
            return True
        except Exception as e:
            log_line("TTS", f"PowerShell fallback failed: {e}")
            return False

    def _loop(self):
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            chosen = None
            for v in voices:
                info = (str(getattr(v, "name", "")) + " " + str(getattr(v, "id", "")) + " " + str(getattr(v, "languages", ""))).lower()
                if any(x in info for x in ("russian", "ru-ru", "ru_ru", "ирина", "pavel", "павел", "elena", "елена")):
                    chosen = v.id
                    break
            if chosen:
                engine.setProperty("voice", chosen)
            engine.setProperty("rate", 178)
            engine.setProperty("volume", 1.0)
        except Exception as e:
            log_line("TTS", f"pyttsx3 unavailable: {e}")
            engine = None
        while True:
            text = self.q.get()
            if text is None:
                break
            self.event_callback(("state", "speaking"))
            try:
                if engine is not None:
                    engine.say(text)
                    engine.runAndWait()
                elif not self._powershell_speak(text):
                    log_line("TTS", "No TTS engine available; check Russian voice in Windows.")
            except Exception as e:
                log_line("TTS", str(e))
                if not self._powershell_speak(text):
                    pass
            self.event_callback(("state", "ready"))


class JarvisApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1280x820")
        self.root.minsize(1020, 690)
        self.root.configure(bg=BG)
        self.events: queue.Queue[tuple] = queue.Queue()
        self.commands: queue.Queue[tuple[str, str]] = queue.Queue()
        self.stop_event = threading.Event()
        self.voice = Voice(self.events.put)
        self.phase = 0.0
        self.ui_state = "ready"
        self.current_scenarios = load_scenarios()
        self._build_ui()
        self._seed_scenarios()
        threading.Thread(target=self._command_loop, daemon=True).start()
        self._start_speech_recognition()
        self.root.after(80, self._poll_events)
        self.root.after(40, self._animate)
        self.root.after(1000, self._clock)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log("SYSTEM", "JARVIS NEON запущен. Команды работают без ключа ИИ.")

    def _seed_scenarios(self):
        if not self.current_scenarios:
            self.current_scenarios = {
                "Игровой режим": ["открой discord", "открой steam"],
                "Рабочий режим": ["открой visual studio code", "открой chrome"],
            }
            save_scenarios(self.current_scenarios)
        self._refresh_scenario_list()

    def panel(self, parent, *, bg=PANEL, border=BORDER, padx=1, pady=1):
        outer = tk.Frame(parent, bg=border, bd=0, highlightthickness=0)
        inner = tk.Frame(outer, bg=bg, bd=0, highlightthickness=0)
        inner.pack(fill="both", expand=True, padx=padx, pady=pady)
        return outer, inner

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", PANEL), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def button(self, parent, text, command, *, accent=False, compact=False):
        bg = "#0b3f62" if accent else "#102943"
        fg = CYAN if accent else TEXT
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground="#14527a", activeforeground="#ffffff",
                      bd=0, relief="flat", cursor="hand2",
                      font=("Segoe UI", 9 if compact else 10, "bold"),
                      padx=10 if compact else 14, pady=6 if compact else 9,
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=CYAN)
        return b

    def _build_ui(self):
        root = self.root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
        # Header bar
        header = tk.Frame(root, bg="#071324", height=70, highlightbackground=BORDER, highlightthickness=1)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)
        mark = tk.Canvas(header, width=44, height=44, bg="#071324", highlightthickness=0)
        mark.grid(row=0, column=0, padx=(14, 10), pady=9)
        mark.create_oval(3, 3, 41, 41, outline=CYAN, width=2)
        mark.create_oval(10, 10, 34, 34, outline=BLUE, width=2)
        mark.create_oval(18, 18, 26, 26, fill=CYAN, outline="")
        title = tk.Frame(header, bg="#071324")
        title.grid(row=0, column=1, sticky="w")
        self.label(title, "J A R V I S  /  N E O N", 15, CYAN, True, bg="#071324").pack(anchor="w")
        self.label(title, "LOCAL PC ASSISTANT  •  CONTROL SYSTEM", 8, MUTED, True, bg="#071324").pack(anchor="w", pady=(1, 0))
        self.clock_label = self.label(header, "--:--:--", 13, TEXT, True, bg="#071324")
        self.clock_label.grid(row=0, column=2, padx=16)
        self.state_badge = self.label(header, "● SYSTEM READY", 9, GREEN, True, bg="#071324")
        self.state_badge.grid(row=0, column=3, padx=(0, 16))

        content = tk.Frame(root, bg=BG)
        content.grid(row=1, column=0, sticky="nsew", padx=14)
        content.grid_columnconfigure(0, minsize=238, weight=0)
        content.grid_columnconfigure(1, weight=1, minsize=390)
        content.grid_columnconfigure(2, minsize=292, weight=0)
        content.grid_rowconfigure(0, weight=1)

        # left: command shortcuts
        outer, left = self.panel(content)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.label(left, "COMMAND DECK", 10, CYAN, True).pack(anchor="w", padx=14, pady=(14, 2))
        self.label(left, "БЫСТРЫЕ ДЕЙСТВИЯ", 8, MUTED, True).pack(anchor="w", padx=14, pady=(0, 12))
        deck = [
            ("◈  Список команд", self.show_help),
            ("▣  Создать сценарий", self.new_scenario),
            ("▶  Запустить сценарий", self.run_selected_scenario),
            ("◎  Проверить систему", lambda: self.submit_command("состояние системы")),
            ("▤  Скриншот экрана", lambda: self.submit_command("сделай скриншот")),
            ("⌑  Открыть сценарии", self.edit_scenarios),
        ]
        for text, cmd in deck:
            self.button(left, text, cmd, compact=True).pack(fill="x", padx=12, pady=3)
        sep = tk.Frame(left, bg=BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=12)
        self.label(left, "VOICE LINK", 9, MUTED, True).pack(anchor="w", padx=14)
        self.mic_status = self.label(left, "● Голосовая служба запускается", 9, GREEN, False, wraplength=205, justify="left")
        self.mic_status.pack(anchor="w", padx=14, pady=(7, 6))
        self.label(left, "Фраза активации", 8, MUTED).pack(anchor="w", padx=14, pady=(8, 2))
        self.label(left, "«Джарвис» + команда", 10, TEXT, True).pack(anchor="w", padx=14)
        self.label(left, "Можно также вводить команды снизу.", 8, MUTED, wraplength=200, justify="left").pack(anchor="w", padx=14, pady=(4, 14))

        # center: reactor
        outer, center = self.panel(content, bg="#071426", border="#1b5a82")
        outer.grid(row=0, column=1, sticky="nsew", padx=4)
        center.grid_rowconfigure(1, weight=1)
        self.label(center, "NEURAL CORE  /  LIVE VISUALIZER", 10, CYAN, True, bg="#071426").pack(anchor="w", padx=16, pady=(14, 0))
        self.orb = tk.Canvas(center, bg="#071426", highlightthickness=0, height=360)
        self.orb.pack(fill="both", expand=True, padx=4, pady=(0, 2))
        stats = tk.Frame(center, bg="#071426")
        stats.pack(fill="x", padx=12, pady=(0, 12))
        for col in range(3):
            stats.grid_columnconfigure(col, weight=1)
        for col, (caption, value, color) in enumerate((("CORE", "ONLINE", GREEN), ("COMMANDS", "LOCAL", CYAN), ("VOICE", "READY", PURPLE))):
            _, cell = self.panel(stats, bg="#0a1b2f", padx=1, pady=1)
            cell.master.grid(row=0, column=col, sticky="ew", padx=3)
            self.label(cell, caption, 8, MUTED, True, bg="#0a1b2f").pack(pady=(7, 1))
            self.label(cell, value, 11, color, True, bg="#0a1b2f").pack(pady=(0, 7))

        # right: scenarios and event log
        outer, right = self.panel(content)
        outer.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        right.grid_rowconfigure(4, weight=1)
        self.label(right, "SCENARIO MATRIX", 10, CYAN, True).pack(anchor="w", padx=13, pady=(14, 2))
        self.label(right, "ТВОИ ПЕРСОНАЛЬНЫЕ СЦЕНАРИИ", 8, MUTED, True).pack(anchor="w", padx=13, pady=(0, 8))
        list_holder = tk.Frame(right, bg=PANEL)
        list_holder.pack(fill="x", padx=10)
        self.scenario_list = tk.Listbox(list_holder, height=7, bg="#071426", fg=TEXT, selectbackground="#10567b",
                                        selectforeground="#ffffff", highlightthickness=1, highlightbackground=BORDER,
                                        relief="flat", bd=0, font=("Segoe UI", 10), activestyle="none")
        self.scenario_list.pack(fill="x")
        self.scenario_list.bind("<Double-Button-1>", lambda e: self.run_selected_scenario())
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x", padx=10, pady=7)
        self.button(row, "+ Новый", self.new_scenario, compact=True, accent=True).pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.button(row, "Изменить", self.edit_scenarios, compact=True).pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.button(right, "▶  ВЫПОЛНИТЬ ВЫБРАННЫЙ", self.run_selected_scenario, accent=True, compact=True).pack(fill="x", padx=10, pady=(0, 12))
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(0, 9))
        self.label(right, "ACTIVITY LOG", 9, CYAN, True).pack(anchor="w", padx=13)
        self.log_view = tk.Text(right, height=10, bg="#06111f", fg=MUTED, insertbackground=CYAN,
                                font=("Consolas", 8), wrap="word", bd=0, highlightthickness=1,
                                highlightbackground=BORDER, state="disabled", padx=8, pady=7)
        self.log_view.pack(fill="both", expand=True, padx=10, pady=(6, 12))
        self.log_view.tag_config("SYSTEM", foreground=CYAN)
        self.log_view.tag_config("YOU", foreground=TEXT)
        self.log_view.tag_config("JARVIS", foreground=GREEN)
        self.log_view.tag_config("ERROR", foreground=RED)

        # quick launch rail
        quick = tk.Frame(root, bg=BG)
        quick.grid(row=2, column=0, sticky="ew", padx=14, pady=(10, 7))
        quick.grid_columnconfigure(1, weight=1)
        self.label(quick, "QUICK LAUNCH", 9, MUTED, True, bg=BG).grid(row=0, column=0, sticky="w", padx=(2, 12))
        appsframe = tk.Frame(quick, bg=BG)
        appsframe.grid(row=0, column=1, sticky="ew")
        for i, (title, cmd) in enumerate((("CHROME", "открой chrome"), ("DISCORD", "открой discord"), ("STEAM", "открой steam"), ("VS CODE", "открой visual studio code"), ("NOTEPAD", "открой блокнот"))):
            appsframe.grid_columnconfigure(i, weight=1)
            self.button(appsframe, title, lambda c=cmd: self.submit_command(c), compact=True).grid(row=0, column=i, sticky="ew", padx=3)

        # command composer
        composer_outer, composer = self.panel(root, bg="#08182b", border="#2185b8")
        composer_outer.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        composer.grid_columnconfigure(1, weight=1)
        self.label(composer, "⌘", 17, CYAN, True, bg="#08182b").grid(row=0, column=0, padx=(14, 10), pady=11)
        self.command_entry = tk.Entry(composer, bg="#0b2138", fg=TEXT, insertbackground=CYAN,
                                      selectbackground="#13577c", relief="flat", bd=0,
                                      font=("Segoe UI", 12), highlightthickness=1,
                                      highlightbackground=BORDER, highlightcolor=CYAN)
        self.command_entry.grid(row=0, column=1, sticky="ew", ipady=10, pady=9)
        self.command_entry.insert(0, "Введите команду, например: открой калькулятор")
        self.command_entry.bind("<FocusIn>", self._clear_placeholder)
        self.command_entry.bind("<Return>", lambda e: self.send_command())
        self.button(composer, "ВЫПОЛНИТЬ  ↗", self.send_command, accent=True).grid(row=0, column=2, padx=10, pady=8)

    def _clear_placeholder(self, _event=None):
        if self.command_entry.get().strip() == "Введите команду, например: открой калькулятор":
            self.command_entry.delete(0, "end")

    def _clock(self):
        try:
            self.clock_label.config(text=dt.datetime.now().strftime("%H:%M:%S"))
            self.root.after(1000, self._clock)
        except tk.TclError:
            pass

    def _animate(self):
        try:
            c = self.orb
            w, h = max(c.winfo_width(), 360), max(c.winfo_height(), 300)
            c.delete("all")
            cx, cy = w * .5, h * .48
            self.phase += .055 if self.ui_state != "speaking" else .12
            base = min(w, h) * .33
            # circuit traces on the panel
            for side in (-1, 1):
                for i in range(5):
                    y = cy - 55 + i * 28
                    x0 = cx + side * (base + 22)
                    x1 = cx + side * (w * .48)
                    c.create_line(x0, y, x1, y, fill="#103856", width=1)
                    c.create_oval(x0 - 2, y - 2, x0 + 2, y + 2, fill=BLUE, outline="")
            for i, (mult, color, width) in enumerate(((1.0, "#164d7a", 2), (.82, "#1e88c8", 2), (.66, CYAN, 2), (.48, "#176aa5", 2), (.29, "#0f3c65", 3))):
                r = base * mult + 2 * (i + 1) * __import__("math").sin(self.phase - i * .8)
                c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=width)
                if i in (0, 2):
                    c.create_arc(cx-r, cy-r, cx+r, cy+r, start=(self.phase*45 + i*65) % 360,
                                 extent=72, style="arc", outline=CYAN, width=3)
            # small orbit nodes
            import math
            for i in range(12):
                a = self.phase * .7 + i * math.tau / 12
                r = base * (.76 if i % 2 else .95)
                x, y = cx + math.cos(a)*r, cy + math.sin(a)*r
                c.create_oval(x-3, y-3, x+3, y+3, fill=CYAN if i % 3 == 0 else BLUE, outline="")
            c.create_oval(cx-42, cy-42, cx+42, cy+42, fill="#0a2841", outline=CYAN, width=2)
            c.create_oval(cx-29, cy-29, cx+29, cy+29, fill="#0d4970", outline="#67e7ff", width=1)
            c.create_text(cx, cy-2, text="J", fill="#effcff", font=("Segoe UI", 31, "bold"))
            c.create_text(cx, cy + base + 33, text="NEURAL CORE  •  LOCAL EXECUTION", fill=MUTED, font=("Consolas", 9, "bold"))
            c.create_text(cx, 18, text="SYSTEM TELEMETRY / LIVE", fill="#397caa", font=("Consolas", 8))
            self.root.after(42, self._animate)
        except tk.TclError:
            pass

    def _set_state(self, state: str):
        self.ui_state = state
        if state == "speaking":
            self.state_badge.config(text="● SPEAKING", fg=PURPLE)
        elif state == "working":
            self.state_badge.config(text="● PROCESSING", fg=CYAN)
        else:
            self.state_badge.config(text="● SYSTEM READY", fg=GREEN)

    def log(self, who: str, text: str):
        log_line(who, text)
        t = self.log_view
        t.configure(state="normal")
        now = dt.datetime.now().strftime("%H:%M:%S")
        t.insert("end", f"{now}  ", "SYSTEM")
        t.insert("end", f"{who:<6} ", who if who in ("YOU", "JARVIS", "ERROR", "SYSTEM") else "SYSTEM")
        t.insert("end", text + "\n", who if who in ("YOU", "JARVIS", "ERROR", "SYSTEM") else "SYSTEM")
        lines = int(t.index("end-1c").split(".")[0])
        if lines > 160:
            t.delete("1.0", f"{lines-160}.0")
        t.see("end")
        t.configure(state="disabled")

    def submit_command(self, text: str):
        text = text.strip()
        if not text:
            return
        self.commands.put(("text", text))
        self.command_entry.focus_set()

    def send_command(self):
        text = self.command_entry.get().strip()
        if text == "Введите команду, например: открой калькулятор":
            return
        if text:
            self.command_entry.delete(0, "end")
            self.submit_command(text)

    def _command_loop(self):
        while not self.stop_event.is_set():
            try:
                kind, text = self.commands.get(timeout=.3)
            except queue.Empty:
                continue
            self.events.put(("state", "working"))
            self.events.put(("log", "YOU", text))
            try:
                response = self.execute(text)
            except Exception as e:
                log_line("ERROR", f"command {text}: {e}")
                response = f"Ошибка выполнения команды: {e}"
            self.events.put(("log", "JARVIS" if not response.lower().startswith(("не удалось", "не получилось", "не знаю", "ошибка", "не нашёл")) else "ERROR", response))
            self.voice.say(response)
            self.events.put(("state", "ready"))

    def execute(self, command: str, in_scenario: bool = False) -> str:
        cmd = command.lower().strip().strip(".,! ?")
        if not cmd:
            return "Команда пустая."
        if cmd in ("помощь", "команды", "список команд", "что ты умеешь"):
            return "Команды: открой приложение, закрой приложение, найди запрос, который час, какая дата, громче, тише, скриншот, состояние системы, сценарии, выполни сценарий название. Все эти команды работают без ключа ИИ."
        if "который час" in cmd or "сколько времени" in cmd or cmd == "время":
            return "Сейчас " + dt.datetime.now().strftime("%H:%M")
        if "какая дата" in cmd or "какое сегодня число" in cmd or "какой сегодня день" in cmd:
            d = dt.date.today()
            months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
            return f"Сегодня {d.day} {months[d.month-1]} {d.year} года."
        m = re.match(r"^(?:выполни сценарий|запусти сценарий|сценарий)\s+(.+)$", cmd)
        if m:
            return self.run_scenario(m.group(1))
        m = re.match(r"^(?:открой сценарии|настрой сценарии)$", cmd)
        if m:
            self.events.put(("ui", "scenarios"))
            return "Открываю редактор сценариев."
        m = re.match(r"^(?:закрой|заверши|выключи приложение)\s+(.+)$", cmd)
        if m:
            return close_target(m.group(1))
        m = re.match(r"^(?:открой|запусти|включи)\s+(.+)$", cmd)
        if m:
            return open_target(m.group(1))
        if re.match(r"^(?:найди|поищи|загугли|поиск)\s+", cmd):
            query = re.sub(r"^(?:найди|поищи|загугли|поиск)\s*(?:в интернете\s*)?", "", command, flags=re.I).strip()
            if query:
                url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
                try:
                    ok = webbrowser.open(url, new=2)
                    return f"Ищу в интернете: {query}." if ok else "Не удалось открыть браузер для поиска."
                except Exception as e:
                    return f"Ошибка открытия поиска: {e}"
            return "Что именно искать?"
        if any(x in cmd for x in ("громче", "прибавь громкость", "тише", "убавь громкость", "выключи звук", "включи звук", "без звука")):
            return self.change_volume(cmd)
        if "скриншот" in cmd or "снимок экрана" in cmd:
            return self.screenshot()
        if "состояние системы" in cmd or "загрузка процессора" in cmd or "заряд" in cmd:
            return self.system_status()
        if "заблокируй компьютер" in cmd or cmd == "заблокируй":
            if IS_WINDOWS:
                try:
                    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                    return "Отправлена команда блокировки компьютера."
                except Exception as e:
                    return f"Не получилось заблокировать компьютер: {e}"
            return "Блокировка компьютера доступна в Windows."
        if "отмени выключение" in cmd:
            if IS_WINDOWS:
                subprocess.Popen(["shutdown", "/a"])
                return "Запрос отмены выключения отправлен."
            return "Эта команда доступна в Windows."
        if "выключи компьютер" in cmd:
            self.events.put(("ui", "shutdown-confirm"))
            return "Показываю подтверждение выключения компьютера."
        return f"Я не знаю команду «{command}». Скажите «список команд», чтобы увидеть доступные действия."

    def run_scenario(self, name: str) -> str:
        scenarios = load_scenarios()
        steps = next((v for k, v in scenarios.items() if k.lower() == name.strip().lower()), None)
        if not steps:
            return f"Сценарий «{name}» не найден. Создайте его кнопкой «Новый» справа."
        if len(steps) > 40:
            return "В сценарии слишком много шагов (лимит 40)."
        self.events.put(("log", "SYSTEM", f"Запуск сценария: {name}"))
        outcomes = []
        for idx, step in enumerate(steps, 1):
            step = str(step).strip()
            if not step:
                continue
            wait_match = re.fullmatch(r"(?:подожди|пауза)\s+(\d+(?:\.\d+)?)", step.lower())
            if wait_match:
                wait = max(0, min(float(wait_match.group(1)), 30))
                time.sleep(wait)
                outcomes.append(f"шаг {idx}: пауза {wait:g} с")
                continue
            result = self.execute(step, in_scenario=True)
            outcomes.append(f"шаг {idx}: {step} — {result}")
            self.events.put(("log", "SYSTEM", outcomes[-1]))
        failures = [line for line in outcomes if "ошибка закрытия" in line.lower() or "не получилось" in line.lower() or "ошибка" in line.lower()]
        if failures:
            return f"Сценарий «{name}» завершён с ошибками: {len(failures)} из {len(outcomes)} шагов. Подробности в журнале."
        return f"Сценарий «{name}» завершён. Выполнено шагов: {len(outcomes)}."

    def change_volume(self, cmd: str) -> str:
        if not IS_WINDOWS:
            return "Управление громкостью настроено для Windows."
        try:
            import ctypes
            # Media volume keys via keybd_event: up, down or mute.
            user32 = ctypes.windll.user32
            VK_UP, VK_DOWN, VK_MUTE = 0xAF, 0xAE, 0xAD
            if "выключи звук" in cmd or "включи звук" in cmd or "без звука" in cmd:
                user32.keybd_event(VK_MUTE, 0, 0, 0); user32.keybd_event(VK_MUTE, 0, 2, 0)
            else:
                key = VK_UP if "громче" in cmd or "прибавь" in cmd else VK_DOWN
                for _ in range(5):
                    user32.keybd_event(key, 0, 0, 0); user32.keybd_event(key, 0, 2, 0)
            return "Громкость изменена."
        except Exception as e:
            return f"Не удалось изменить громкость: {e}"

    def screenshot(self) -> str:
        try:
            import time as _time
            from PIL import ImageGrab
            folder = Path.home() / "Pictures" / "Jarvis"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"screenshot_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
            ImageGrab.grab().save(path)
            return f"Скриншот сохранён: {path}"
        except ImportError:
            return "Для скриншота установите Pillow: pip install pillow."
        except Exception as e:
            return f"Не удалось сделать скриншот: {e}"

    def system_status(self) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=.4)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            text = f"Загрузка процессора {cpu:.0f} процентов. Оперативная память занята на {ram:.0f} процентов."
            if battery:
                text += f" Заряд батареи {battery.percent:.0f} процентов."
            return text
        except ImportError:
            return "Состояние системы доступно после установки psutil."
        except Exception:
            return "Не удалось получить все системные показатели."

    def _start_speech_recognition(self):
        try:
            import speech_recognition as sr
            import pyaudio  # noqa: F401
        except Exception:
            self.mic_status.config(text="● Микрофон не настроен — используйте поле команд", fg=RED)
            self.log("SYSTEM", "Голосовое распознавание недоступно. Текстовые команды продолжают работать.")
            return
        threading.Thread(target=self._mic_loop, args=(sr,), daemon=True).start()

    def _mic_loop(self, sr):
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = .7
        recognizer.non_speaking_duration = .4
        follow_until = 0.0
        backoff = 2
        while not self.stop_event.is_set():
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=.5)
                    self.events.put(("ui", "mic-ok"))
                    backoff = 2
                    while not self.stop_event.is_set():
                        try:
                            audio = recognizer.listen(source, timeout=1, phrase_time_limit=7)
                        except sr.WaitTimeoutError:
                            continue
                        try:
                            spoken = recognizer.recognize_google(audio, language="ru-RU").lower().strip()
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError:
                            self.events.put(("ui", "mic-net"))
                            time.sleep(2)
                            continue
                        match = WAKE_RE.search(spoken)
                        if match:
                            command = spoken[match.end():].strip(" ,.!?")
                            if command:
                                follow_until = time.monotonic() + 8
                                self.commands.put(("voice", command))
                            else:
                                follow_until = time.monotonic() + 8
                                self.voice.say("Слушаю.")
                                self.events.put(("ui", "mic-follow"))
                        elif time.monotonic() < follow_until:
                            follow_until = 0
                            self.commands.put(("voice", spoken))
            except Exception as e:
                self.events.put(("ui", "mic-error"))
                log_line("MIC", str(e))
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 30)

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self.log(event[1], event[2])
                elif kind == "state":
                    self._set_state(event[1])
                elif kind == "ui":
                    if event[1] == "scenarios":
                        self.edit_scenarios()
                    elif event[1] == "shutdown-confirm":
                        if messagebox.askyesno("JARVIS NEON", "Выключить компьютер через 10 секунд?", parent=self.root):
                            if IS_WINDOWS:
                                subprocess.Popen(["shutdown", "/s", "/t", "10"])
                                self.voice.say("Компьютер будет выключен через десять секунд. Для отмены скажите: отмени выключение.")
                        else:
                            self.voice.say("Выключение отменено.")
                    elif event[1] == "mic-ok":
                        self.mic_status.config(text="● Микрофон активен. Скажите «Джарвис»", fg=GREEN)
                    elif event[1] == "mic-follow":
                        self.mic_status.config(text="● Слушаю следующую фразу…", fg=CYAN)
                    elif event[1] == "mic-net":
                        self.mic_status.config(text="● Нет соединения для распознавания речи", fg=RED)
                    elif event[1] == "mic-error":
                        self.mic_status.config(text="● Микрофон недоступен — вводите текст", fg=RED)
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.root.after(100, self._poll_events)
        except tk.TclError:
            pass

    def _refresh_scenario_list(self):
        if not hasattr(self, "scenario_list"):
            return
        self.scenario_list.delete(0, "end")
        for title in sorted(self.current_scenarios, key=str.lower):
            self.scenario_list.insert("end", title)
        if self.scenario_list.size():
            self.scenario_list.selection_set(0)

    def _selected_scenario(self) -> str | None:
        sel = self.scenario_list.curselection()
        return self.scenario_list.get(sel[0]) if sel else None

    def run_selected_scenario(self):
        name = self._selected_scenario()
        if not name:
            self.voice.say("Сначала выберите сценарий.")
            return
        self.submit_command(f"выполни сценарий {name}")

    def new_scenario(self):
        self._scenario_editor(None)

    def edit_scenarios(self):
        name = self._selected_scenario()
        if not name:
            messagebox.showinfo(APP_NAME, "Выберите сценарий справа или нажмите «Новый».", parent=self.root)
            return
        self._scenario_editor(name)

    def _scenario_editor(self, name: str | None):
        win = tk.Toplevel(self.root)
        win.title("Scenario Designer / JARVIS NEON")
        win.geometry("650x560")
        win.minsize(520, 450)
        win.configure(bg=BG)
        self.label(win, "SCENARIO DESIGNER", 13, CYAN, True, bg=BG).pack(anchor="w", padx=18, pady=(18, 4))
        self.label(win, "Создай последовательность действий. Каждый шаг — с новой строки.", 9, MUTED, bg=BG).pack(anchor="w", padx=18, pady=(0, 12))
        self.label(win, "НАЗВАНИЕ", 8, MUTED, True, bg=BG).pack(anchor="w", padx=18)
        name_var = tk.StringVar(value=name or "Новый сценарий")
        entry = tk.Entry(win, textvariable=name_var, bg=PANEL2, fg=TEXT, insertbackground=CYAN, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", padx=18, ipady=8, pady=(4, 12))
        self.label(win, "ШАГИ", 8, MUTED, True, bg=BG).pack(anchor="w", padx=18)
        steps = tk.Text(win, bg="#071426", fg=TEXT, insertbackground=CYAN, font=("Consolas", 10), bd=0,
                        highlightthickness=1, highlightbackground=BORDER, padx=10, pady=10, wrap="word")
        steps.pack(fill="both", expand=True, padx=18, pady=(4, 8))
        old = self.current_scenarios.get(name, []) if name else []
        steps.insert("1.0", "\n".join(old))
        self.label(win, "Примеры: открой chrome  •  закрой discord  •  подожди 2  •  найди погоду в Риге", 8, MUTED, bg=BG, wraplength=600, justify="left").pack(anchor="w", padx=18, pady=(0, 8))
        controls = tk.Frame(win, bg=BG)
        controls.pack(fill="x", padx=18, pady=(0, 16))
        def save():
            title = name_var.get().strip()
            lines = [line.strip() for line in steps.get("1.0", "end").splitlines() if line.strip()]
            if not title or not lines:
                messagebox.showwarning(APP_NAME, "Добавьте название и хотя бы один шаг.", parent=win)
                return
            if len(lines) > 40:
                messagebox.showwarning(APP_NAME, "Лимит — 40 шагов на сценарий.", parent=win)
                return
            if name and name != title:
                self.current_scenarios.pop(name, None)
            self.current_scenarios[title] = lines
            try:
                save_scenarios(self.current_scenarios)
                self._refresh_scenario_list()
                for i in range(self.scenario_list.size()):
                    if self.scenario_list.get(i) == title:
                        self.scenario_list.selection_clear(0, "end")
                        self.scenario_list.selection_set(i)
                        break
                self.log("SYSTEM", f"Сценарий «{title}» сохранён.")
                win.destroy()
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Не удалось сохранить сценарий: {e}", parent=win)
        self.button(controls, "СОХРАНИТЬ СЦЕНАРИЙ", save, accent=True).pack(side="left")
        self.button(controls, "УДАЛИТЬ", lambda: self._delete_scenario(name, win), compact=True).pack(side="right") if name else None

    def _delete_scenario(self, name: str | None, win):
        if name and messagebox.askyesno(APP_NAME, f"Удалить сценарий «{name}»?", parent=win):
            self.current_scenarios.pop(name, None)
            save_scenarios(self.current_scenarios)
            self._refresh_scenario_list()
            win.destroy()
            self.log("SYSTEM", f"Сценарий «{name}» удалён.")

    def show_help(self):
        help_text = (
            "ПРИЛОЖЕНИЯ\n"
            "  открой chrome / Edge / discord / steam / калькулятор / блокнот / Word / Excel / VS Code\n"
            "  закрой chrome / discord / steam / блокнот\n\n"
            "САЙТЫ И ПОИСК\n"
            "  открой ютуб / гугл / почту / телеграм\n"
            "  найди погоду в Риге\n\n"
            "СИСТЕМА\n"
            "  который час / какая дата / громче / тише / выключи звук\n"
            "  сделай скриншот / состояние системы / заблокируй компьютер\n\n"
            "СЦЕНАРИИ\n"
            "  открой сценарии\n"
            "  выполни сценарий Игровой режим\n"
            "  шаги: открой discord; открой steam; подожди 2; закрой chrome\n\n"
            "ИИ-ключ не нужен для этих команд. Голосовое распознавание использует интернет; озвучка — установленный голос Windows."
        )
        win = tk.Toplevel(self.root)
        win.title("Команды / JARVIS NEON")
        win.geometry("660x560")
        win.configure(bg=BG)
        self.label(win, "COMMAND DATABASE", 13, CYAN, True, bg=BG).pack(anchor="w", padx=18, pady=16)
        text = tk.Text(win, bg=PANEL, fg=TEXT, font=("Consolas", 10), wrap="word", bd=0, padx=14, pady=14)
        text.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        text.insert("1.0", help_text)
        text.configure(state="disabled")

    def _on_close(self):
        self.stop_event.set()
        try:
            self.voice.q.put_nowait(None)
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if "--self-test" in sys.argv:
        assert resolve_app_name("google chrome") == "chrome"
        assert resolve_app_name("включи discord") == "discord"
        assert resolve_app_name("калькулятор") == "калькулятор"
        assert set(load_scenarios().keys()) == set(load_scenarios().keys())
        print("Self-test passed: aliases, scenario storage, command parser ready.")
        return
    JarvisApp().run()

if __name__ == "__main__":
    main()
