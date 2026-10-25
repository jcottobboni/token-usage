"""Linha de comando: `token-usage [serve|tray|autostart]`."""
import argparse
import sys

from . import __version__

TRAY_DEPS = ("o ícone precisa de dependências extras: pip install 'token-usage[tray]'. "
             "No Linux também: python3-gi e gir1.2-ayatanaappindicator3-0.1 (ou o equivalente da distro)")


def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(prog="token-usage", description="Painel local de uso de tokens de agentes de IA.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--open", action="store_true", help="abre o painel no navegador")
    sub = p.add_subparsers(dest="cmd", metavar="{serve,tray,autostart}")
    s = sub.add_parser("serve", help="sobe o painel em http://127.0.0.1:8777/ (padrão)")
    # SUPPRESS: o padrão do subcomando não apaga um --open passado antes dele
    s.add_argument("--open", action="store_true", default=argparse.SUPPRESS, help="abre o painel no navegador")
    sub.add_parser("tray", help="ícone na bandeja/barra superior; sobe o painel se ele não estiver rodando")
    a = sub.add_parser("autostart", help="inicia com a sessão do usuário")
    a.add_argument("--tray", action="store_true", help="inicia o ícone em vez de só o painel")
    a.add_argument("--remove", action="store_true", help="desfaz o início automático")
    args = p.parse_args(argv)

    if args.cmd == "tray":
        try:
            from . import tray
        except ImportError as e:
            # o executável de Linux sai sem o ícone: o PyGObject vem da distro, não dá para embutir
            sys.exit(f"{e}\n" + ("este executável não inclui o ícone; instale com install.sh --tray"
                                  if getattr(sys, "frozen", False) else TRAY_DEPS))
        tray.main()
    elif args.cmd == "autostart":
        from . import autostart
        if args.remove:
            autostart.remove()
        else:
            autostart.install(args.tray)
    else:
        from . import server
        server.main(open_browser=args.open)


def tray_main():
    """Executável sem console (Windows): sem argumentos abre o ícone; com argumentos, igual ao token-usage."""
    main(sys.argv[1:] or ["tray"])
