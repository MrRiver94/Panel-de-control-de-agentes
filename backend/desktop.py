"""Local application entry point, also used by the portable Windows executable."""
from __future__ import annotations

import argparse
from http.client import HTTPConnection
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import sys
import threading
import time
import webbrowser
from urllib.parse import urlparse


def existing_application(port: int, data_directory: Path) -> bool:
    """Only reuse our desktop instance, with the same data directory and mode."""
    connection = HTTPConnection('127.0.0.1', port, timeout=1)
    try:
        connection.request('GET', '/health')
        response = connection.getresponse()
        if response.status != 200:
            return False
        identity = json.loads(response.read(8192))
        return (identity.get('app') == 'slimeops' and identity.get('desktop') is True
                and identity.get('monitor_only') == (os.environ.get('SLIMEOPS_MONITOR_ONLY') == '1')
                and os.path.normcase(identity.get('data_directory', '')) == os.path.normcase(str(data_directory)))
    except (OSError, ValueError):
        return False
    finally:
        connection.close()


def create_local_app():
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from app.config import PROJECT_ROOT
    from app.main import app

    assets = PROJECT_ROOT / 'dist'
    if not (assets / 'index.html').is_file():
        raise RuntimeError('Falta el panel compilado. Genera dist antes de iniciar la aplicación.')

    @app.middleware('http')
    async def local_requests_only(request: Request, call_next):
        origin = request.headers.get('origin')
        local_hosts = {'localhost', '127.0.0.1', '::1'}
        if (not request.client or request.client.host not in local_hosts
                or request.url.hostname not in local_hosts
                or (origin and urlparse(origin).hostname not in local_hosts)):
            return JSONResponse({'detail': 'SlimeOps solo permite acceso desde tu equipo.'}, status_code=403)
        return await call_next(request)

    app.mount('/', StaticFiles(directory=assets, html=True), name='desktop-panel')
    return app


def show_error(message: str, headless: bool) -> None:
    logging.error('%s', message)
    if headless:
        return
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror('SlimeOps', message, parent=root)
    root.destroy()


def run_window(server, thread: threading.Thread, url: str, monitor: bool) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title('SlimeOps · Monitor local')
    root.geometry('460x210')
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='SlimeOps', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Monitor local de Codex' if monitor else 'Monitor local · misiones habilitadas').pack(anchor='w', pady=(4, 12))
    ttk.Label(frame, text='El panel se abre en tu navegador.\nCierra esta ventana para detener SlimeOps.').pack(anchor='w')
    controls = ttk.Frame(frame)
    controls.pack(anchor='w', pady=14)
    ttk.Button(controls, text='Abrir panel', command=lambda: webbrowser.open(url)).pack(side='left', padx=(0, 10))
    stop = ttk.Button(controls, text='Cerrar SlimeOps')
    stop.pack(side='left')

    def close() -> None:
        stop.configure(state='disabled')
        server.should_exit = True
        wait_for_shutdown()

    def wait_for_shutdown() -> None:
        if thread.is_alive():
            root.after(100, wait_for_shutdown)
        else:
            root.destroy()

    def watch() -> None:
        if not thread.is_alive():
            root.destroy()
        else:
            root.after(500, watch)

    stop.configure(command=close)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(500, watch)
    root.mainloop()


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='SlimeOps: monitor local de Codex.')
    parser.add_argument('--port', type=int, default=47831)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--enable-missions', action='store_true')
    parser.add_argument('--headless', action='store_true', help='Sin ventana de control.')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help='Arranque, comprobación HTTP y cierre sin usar Codex.')
    args = parser.parse_args(arguments)
    if not 1 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 1 y 65535.')
    if args.data_dir:
        os.environ['SLIMEOPS_DATA_DIR'] = str(args.data_dir.expanduser().resolve())
    os.environ['SLIMEOPS_MONITOR_ONLY'] = '0' if args.enable_missions else '1'
    os.environ['SLIMEOPS_DESKTOP'] = '1'

    # Import after configuring paths, so no database is created inside the bundle.
    from app.config import DATA_DIRECTORY
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_log = RotatingFileHandler(DATA_DIRECTORY / 'slimeops.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[file_log], format='%(asctime)s %(levelname)s %(message)s', force=True)
    logging.getLogger('uvicorn.access').disabled = True
    url = f'http://127.0.0.1:{args.port}'
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # On Windows SO_REUSEADDR can share a listener with another process.
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', args.port))
        listener.listen(128)
    except OSError:
        listener.close()
        if not args.smoke_test and existing_application(args.port, DATA_DIRECTORY):
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        show_error(f'El puerto {args.port} está ocupado. Cierra la otra instancia o elige otro puerto con --port.', args.headless or args.smoke_test)
        return 1

    import uvicorn
    server = None
    thread = None
    stream_connection = None
    try:
        server = uvicorn.Server(uvicorn.Config(create_local_app(), log_config=None, access_log=False, loop='asyncio', http='h11', ws='none', timeout_graceful_shutdown=3))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, name='slimeops-server', daemon=True)
        thread.start()
        deadline = time.monotonic() + 20
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError('No se pudo iniciar el monitor. Consulta slimeops.log en su carpeta de datos.')
            time.sleep(0.05)
        if args.smoke_test:
            if os.name == 'nt':
                import tkinter as tk
                window = tk.Tk()
                window.withdraw()
                window.update_idletasks()
                window.destroy()
            connection = HTTPConnection('127.0.0.1', args.port, timeout=5)
            try:
                for path in ('/health', '/', '/js/config.js'):
                    connection.request('GET', path)
                    response = connection.getresponse()
                    body = response.read()
                    if response.status != 200 or not body:
                        raise RuntimeError(f'Comprobación de arranque fallida: {path}.')
                connection.request('GET', '/health', headers={'Origin': 'https://example.org'})
                response = connection.getresponse()
                response.read()
                if response.status != 403:
                    raise RuntimeError('La aplicación no rechazó un origen remoto.')
            finally:
                connection.close()
            # Keep a browser-like live stream open while shutting down. Otherwise
            # a persistent SSE request can keep the local application alive forever.
            stream_connection = HTTPConnection('127.0.0.1', args.port, timeout=10)
            stream_connection.request('GET', '/api/stream', headers={'X-Operator-Id': 'super-admin'})
            stream_response = stream_connection.getresponse()
            if stream_response.status != 200 or not stream_response.read(1):
                raise RuntimeError('No se pudo abrir el stream del monitor.')
        else:
            if not args.no_browser:
                webbrowser.open(url)
            if args.headless:
                while thread.is_alive():
                    thread.join(0.5)
            else:
                run_window(server, thread, url, not args.enable_missions)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        logging.exception('No se pudo iniciar SlimeOps')
        show_error(str(error), args.headless or args.smoke_test)
        return 1
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=20)
        if stream_connection:
            stream_connection.close()
        listener.close()
        file_log.close()


if __name__ == '__main__':
    raise SystemExit(main())
