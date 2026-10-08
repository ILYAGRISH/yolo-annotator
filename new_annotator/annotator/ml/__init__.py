"""
ML extension of the annotator — the client side of the ML backend.

Deliberately self-contained, so the main app stays simple and never depends
on it:
  * the heavy work runs in a separate process (../ml_backend) and in its own
    Python environment (.venv-ml) — torch / ultralytics are never imported here;
  * the app touches this package in exactly three places (main_window.py):
    install() on start, retranslate() on language change, shutdown() on close;
    install() is wrapped in try/except — a missing or broken ML package only
    disables the ML menu;
  * own UI strings (strings.py) and own settings keys ("ml/...");
  * nothing starts until the user asks (or enables autostart).

    extension.py        install(window) -> MLExtension: menu, status bar button
    client.py           MLBackend: QProcess + JSON-lines protocol, callbacks
    config.py           interpreter path / autostart settings
    settings_dialog.py  "ML Settings…" dialog: interpreter, check, test model
"""
