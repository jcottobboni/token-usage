#!/usr/bin/env python3
"""Ícone na bandeja/barra superior: clique mostra o resumo de cotas e consumo; "Abrir painel" mostra o detalhado.

Dependências opcionais (só para o ícone): pystray e Pillow. No Linux também precisa do PyGObject
com AppIndicator (pacotes python3-gi e gir1.2-ayatanaappindicator3-0.1).
Se o painel (server.py) não estiver rodando, sobe ele neste mesmo processo.
"""
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

import server

URL = f"http://{server.HOST}:{server.PORT}/"
REFRESH = 60  # segundos entre atualizações do menu
LABEL = {"claude": "Claude Code", "copilot": "Copilot CLI", "codex": "Codex CLI",
         "gemini": "Gemini CLI", "antigravity": "Antigravity"}
TOKEN_KEYS = ("input", "output", "cache_read", "cache_write")
# mesmas cores do painel (Catppuccin suavizado)
GREEN, YELLOW, RED, GRAY = (166, 218, 149), (238, 212, 159), (238, 153, 160), (143, 150, 173)

SHORT = {"claude": "Claude", "copilot": "Copilot", "codex": "Codex", "gemini": "Gemini", "antigravity": "AGY"}
CONFIG = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "token-usage" / "tray.json"
LOWEST = "lowest"  # valor especial de "show": a menor cota restante entre todas

state = {"limits": {}, "usage": None, "error": None, "updated": None}


def load_config() -> dict:
    # show: None (só o anel), LOWEST ou "fonte|rótulo da cota"; mode: "used" ou "remaining"
    cfg = {"show": None, "mode": "used"}
    try:
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config():
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"não salvou {CONFIG}: {e}", file=sys.stderr, flush=True)


config = load_config()


def get(path: str) -> dict:
    with urllib.request.urlopen(URL + path, timeout=30) as res:
        return json.load(res)


def ensure_server():
    try:
        get("api/usage")
    except OSError:
        # ninguém escutando na porta: sobe o painel aqui mesmo
        srv = server.ThreadingHTTPServer((server.HOST, server.PORT), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()


def fmt(n: float) -> str:
    for div, suf in ((1e9, " B"), (1e6, " M"), (1e3, " k")):
        if abs(n) >= div:
            return f"{n / div:.1f}{suf}"
    return f"{n:.0f}"


def until(iso: str | None) -> str:
    if not iso:
        return ""
    s = (datetime.fromisoformat(iso.replace("Z", "+00:00")) - datetime.now().astimezone()).total_seconds()
    if s <= 0:
        return "renovou"
    d, h, m = int(s // 86400), int(s % 86400 // 3600), int(s % 3600 // 60)
    return f"renova em {d} d {h} h" if d else f"renova em {h} h {m:02d} min"


def remaining(lim: dict) -> float | None:
    if lim.get("stale"):
        return None  # cache de uma janela que já renovou: o uso atual é desconhecido
    reset = lim.get("resets_at")
    # janela que já renovou desde a leitura do cache: o uso real é 0
    if reset and datetime.fromisoformat(reset.replace("Z", "+00:00")) < datetime.now().astimezone():
        return 100.0
    return 100 - min(max(float(lim.get("used_pct") or 0), 0), 100)


def lowest() -> float | None:
    vals = [v for L in state["limits"].values() for lim in L.get("limits") or [] if (v := remaining(lim)) is not None]
    return min(vals) if vals else None


def quotas() -> list[tuple[str, str, dict]]:
    """(chave, nome, cota) de cada janela de cota conhecida, na ordem do painel."""
    return [(f"{src}|{lim['label']}", f"{LABEL.get(src, src)} · {lim['label']}", lim)
            for src, L in state["limits"].items() for lim in L.get("limits") or []]


def bar_text() -> str | None:
    """Texto ao lado do ícone, conforme a cota escolhida em "Mostrar na barra"."""
    show = config.get("show")
    if not show:
        return None
    if show == LOWEST:
        left, prefix = lowest(), ""
    else:
        lim = next((lim for key, _, lim in quotas() if key == show), None)
        left, prefix = (remaining(lim) if lim else None), SHORT.get(show.split("|")[0], "") + " "
    if left is None:
        return f"{prefix}—"
    pct = 100 - left if config.get("mode") == "used" else left
    return f"{prefix}{pct:.0f}%"


def set_bar_text(icon: pystray.Icon, text: str | None) -> bool:
    """Põe o texto ao lado do ícone quando o backend permite; False se não der."""
    ind = getattr(icon, "_appindicator", None)  # Linux com AppIndicator (GNOME, KDE)
    if ind is not None:
        from gi.repository import GLib
        # o guia reserva a largura máxima e evita a barra pular a cada atualização
        GLib.idle_add(ind.set_label, text or "", "Copilot 100%" if text else "")
        return True
    item = getattr(icon, "_status_item", None)  # macOS
    if item is not None:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(item.button().setTitle_, f" {text}" if text else "")
        return True
    return False


def color(left: float | None):
    return GRAY if left is None else GREEN if left > 50 else YELLOW if left > 20 else RED


def draw_icon(left: float | None, text: str | None = None) -> Image.Image:
    """Anel com a menor cota restante entre todas as ferramentas; text vai no centro no lugar do ponto."""
    size, w = 64, 9
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (w // 2 + 2, w // 2 + 2, size - w // 2 - 3, size - w // 2 - 3)
    d.ellipse(box, outline=(90, 96, 120, 255), width=w)
    if left is not None:
        d.arc(box, -90, -90 + 360 * left / 100, fill=color(left) + (255,), width=w)
    if text:
        # bandejas sem texto ao lado do ícone (Windows): só o número cabe no anel
        font = ImageFont.load_default(size=26)
        d.text((size / 2, size / 2), text, fill=(200, 205, 224, 255), font=font, anchor="mm")
    else:
        d.ellipse((size / 2 - 7, size / 2 - 7, size / 2 + 7, size / 2 + 7), fill=color(left) + (255,))
    return img


def usage_lines() -> list[str]:
    u = state["usage"]
    if not u:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    month = today[:7]
    by = {}
    for r in u["rows"]:
        t = sum(r[k] for k in TOKEN_KEYS)
        a = by.setdefault(r["source"], [0, 0])
        a[0] += t if r["day"] == today else 0
        a[1] += t if r["day"].startswith(month) else 0
    return [f"{LABEL.get(s, s)}: hoje {fmt(a[0])} · mês {fmt(a[1])}"
            for s, a in sorted(by.items(), key=lambda kv: -kv[1][1])]


def show_action(key: str | None):
    def act(icon, _item):
        config["show"] = key
        save_config()
        redraw(icon)
    return act


def mode_action(mode: str):
    def act(icon, _item):
        config["mode"] = mode
        save_config()
        redraw(icon)
    return act


def bar_menu() -> pystray.Menu:
    def radio(text, checked, action):
        return pystray.MenuItem(text, action, checked=lambda _: checked(), radio=True)
    items = [radio("Nada (só o ícone)", lambda: not config.get("show"), show_action(None)),
             radio("Menor cota restante", lambda: config.get("show") == LOWEST, show_action(LOWEST))]
    items += [radio(name, lambda k=key: config.get("show") == k, show_action(key)) for key, name, _ in quotas()]
    items += [pystray.Menu.SEPARATOR,
              radio("Mostrar % usado", lambda: config.get("mode") == "used", mode_action("used")),
              radio("Mostrar % restante", lambda: config.get("mode") != "used", mode_action("remaining"))]
    return pystray.Menu(*items)


def menu_items():
    info = lambda text: pystray.MenuItem(text, None, enabled=False)
    items = []
    if state["error"]:
        items.append(info(f"Erro: {state['error'][:80]}"))
    for src, L in state["limits"].items():
        for lim in L.get("limits") or []:
            left = remaining(lim)
            if left is None:
                items.append(info(f"{LABEL.get(src, src)} · {lim['label']}: sem dado atual"))
                continue
            extra = until(lim.get("resets_at"))
            items.append(info(f"{LABEL.get(src, src)} · {lim['label']}: {left:.0f}% restante"
                              + (f" · {extra}" if extra else "")))
        if not L.get("live") and L.get("error"):
            items.append(info(f"{LABEL.get(src, src)}: {L['error'][:90]}"))
    lines = usage_lines()
    if lines:
        items += [pystray.Menu.SEPARATOR, info("Tokens processados"), *map(info, lines)]
    if state["updated"]:
        items += [pystray.Menu.SEPARATOR, info(f"Atualizado às {state['updated']:%H:%M}")]
    items += [pystray.Menu.SEPARATOR,
              pystray.MenuItem("Abrir painel detalhado", lambda: webbrowser.open(URL), default=True),
              pystray.MenuItem("Mostrar na barra", bar_menu()),
              pystray.MenuItem("Atualizar agora", lambda icon: refresh(icon, force=True)),
              pystray.MenuItem("Sair", lambda icon: icon.stop())]
    return items


def refresh(icon: pystray.Icon, force: bool = False):
    try:
        state["limits"] = get("api/limits" + ("?force=1" if force else ""))
        state["usage"] = get("api/usage")
        state["error"], state["updated"] = None, datetime.now()
    except Exception as e:  # noqa: BLE001
        state["error"] = str(e)
    redraw(icon)


def redraw(icon: pystray.Icon):
    left, text = lowest(), bar_text()
    in_bar = set_bar_text(icon, text)
    icon.icon = draw_icon(left, None if in_bar else (text or "").split(" ")[-1].rstrip("%"))
    icon.title = "Uso de IA" + (f" · menor cota: {left:.0f}% restante" if left is not None else "")
    icon.update_menu()


def loop(icon: pystray.Icon):
    icon.visible = True
    while icon.visible:
        refresh(icon)
        time.sleep(REFRESH)


def single_instance() -> socket.socket:
    # porta ao lado da do painel funciona como trava em qualquer sistema operacional
    lock = socket.socket()
    try:
        lock.bind((server.HOST, server.PORT + 1))
    except OSError:
        sys.exit("token-usage tray já está rodando")
    return lock


def main():
    _lock = single_instance()  # noqa: F841  (precisa viver até o fim do processo)
    ensure_server()
    icon = pystray.Icon("token-usage", draw_icon(None), "Uso de IA", menu=pystray.Menu(menu_items))
    icon.run(setup=lambda i: threading.Thread(target=loop, args=(i,), daemon=True).start())


if __name__ == "__main__":
    main()
