"""Início automático com a sessão: systemd/autostart no Linux, LaunchAgent no macOS, chave Run no Windows."""
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
HOME = Path.home()
LABEL = "io.github.leoalmeidasa.token-usage"


def command(tray: bool) -> list[str]:
    args = ["tray"] if tray else ["serve"]
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        # no Windows, o token-usage-tray.exe roda sem janela de console e aceita os mesmos argumentos
        windowless = exe.with_name("token-usage-tray.exe")
        if sys.platform == "win32" and windowless.exists():
            exe = windowless
        return [str(exe), *args]
    py = Path(sys.executable)
    if sys.platform == "win32" and py.with_name("pythonw.exe").exists():
        py = py.with_name("pythonw.exe")
    # roda o diretório do pacote: funciona instalado (pip/pipx) e direto do clone
    return [str(py), str(PKG), *args]


def _quote(arg: str) -> str:
    # aspas duplas valem tanto em Exec= (.desktop) quanto em ExecStart= (systemd)
    if re.fullmatch(r"[\w@%+=:,./-]+", arg):
        return arg
    return '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'


def _linux_paths() -> dict[str, Path]:
    return {"desktop": HOME / ".config" / "autostart" / "token-usage.desktop",
            "unit": HOME / ".config" / "systemd" / "user" / "token-usage.service"}


def _systemctl(*args: str):
    subprocess.run(["systemctl", "--user", *args], check=True)


def _install_linux(cmd: list[str], tray: bool) -> Path:
    paths = _linux_paths()
    exec_line = " ".join(map(_quote, cmd))
    if tray or not shutil.which("systemctl"):
        # o ícone precisa da sessão gráfica; o autostart do XDG roda depois que ela sobe
        paths["desktop"].parent.mkdir(parents=True, exist_ok=True)
        paths["desktop"].write_text(
            "[Desktop Entry]\nType=Application\nName=Token Usage\n"
            "Comment=AI agent token usage and quotas\n"
            f"Exec={exec_line}\nIcon=utilities-system-monitor\nTerminal=false\n"
            "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")
        return paths["desktop"]
    paths["unit"].parent.mkdir(parents=True, exist_ok=True)
    paths["unit"].write_text(
        "[Unit]\nDescription=Painel local de uso de tokens de agentes de IA\n\n"
        f"[Service]\nExecStart={exec_line}\nRestart=on-failure\n\n"
        "[Install]\nWantedBy=default.target\n", encoding="utf-8")
    _systemctl("daemon-reload")
    _systemctl("enable", "token-usage.service")
    return paths["unit"]


def _remove_linux():
    paths = _linux_paths()
    if paths["unit"].exists():
        subprocess.run(["systemctl", "--user", "disable", "token-usage.service"], check=False)
        paths["unit"].unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    paths["desktop"].unlink(missing_ok=True)


def _plist() -> Path:
    return HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _install_macos(cmd: list[str]) -> Path:
    path = _plist()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump({"Label": LABEL, "ProgramArguments": cmd, "RunAtLoad": True,
                       "ProcessType": "Interactive"}, fh)
    return path


def _run_key():
    import winreg
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                          0, winreg.KEY_SET_VALUE)


def _install_windows(cmd: list[str]) -> str:
    import winreg
    with _run_key() as key:
        winreg.SetValueEx(key, "token-usage", 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
    return r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run\token-usage"


def _remove_windows():
    import winreg
    with _run_key() as key:
        try:
            winreg.DeleteValue(key, "token-usage")
        except FileNotFoundError:
            pass


def install(tray: bool):
    # um registro só: trocar entre painel e ícone substitui o anterior
    remove(quiet=True)
    cmd = command(tray)
    if sys.platform == "win32":
        where = _install_windows(cmd)
    elif sys.platform == "darwin":
        where = _install_macos(cmd)
    else:
        where = _install_linux(cmd, tray)
    what = "o ícone" if tray else "o painel"
    print(f"{what} vai iniciar com a sessão ({where}). Para iniciar agora: token-usage {'tray' if tray else 'serve'}")


def remove(quiet: bool = False):
    if sys.platform == "win32":
        _remove_windows()
    elif sys.platform == "darwin":
        _plist().unlink(missing_ok=True)
    else:
        _remove_linux()
    if not quiet:
        print("início automático removido")
