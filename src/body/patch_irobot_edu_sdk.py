#!/usr/bin/env python3
"""
Applica alla libreria irobot_edu_sdk (installata via pip) i fix per due bug noti:

1. robot.py:_finished() -> manca una `await` su `_backend.is_connected()`.
2. backend/bluetooth_desktop.py:connect() -> con bleak moderno `connect()` non
   ritorna piu' True/False, quindi le notifiche BLE non venivano mai attivate.

Va eseguito nel Dockerfile subito dopo `pip install -r requirements.txt`, cosi'
i fix sono sempre presenti anche quando l'immagine viene ricostruita da zero.
E' idempotente: se il pattern "nuovo" e' gia' presente lo salta, se non trova
ne' il pattern vecchio ne' quello nuovo si ferma con errore (probabile
cambio di versione della libreria da rivedere).
"""
import importlib.util
from pathlib import Path


def patch_file(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    changed = False
    for old, new in replacements:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(
                f"Pattern atteso non trovato in {path} "
                f"(la libreria e' cambiata? serve rivedere la patch):\n{old!r}"
            )
        text = text.replace(old, new)
        changed = True
    if changed:
        path.write_text(text)
        print(f"[patch_irobot_edu_sdk] patchato {path}")
    else:
        print(f"[patch_irobot_edu_sdk] gia' patchato, salto {path}")


def package_dir() -> Path:
    spec = importlib.util.find_spec("irobot_edu_sdk")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("irobot_edu_sdk non risulta installato")
    return Path(next(iter(spec.submodule_search_locations)))


def main() -> None:
    pkg = package_dir()

    patch_file(
        pkg / "robot.py",
        [(
            "if r._backend.is_connected():",
            "if await r._backend.is_connected():",
        )],
    )

    patch_file(
        pkg / "backend" / "bluetooth_desktop.py",
        [(
            "if await self._client.connect():\n"
            "            await self._client.start_notify(self.RX_CHARACTERISTIC, self.rx_handler)",

            "await self._client.connect()\n"
            "        if await self.is_connected():\n"
            "            await self._client.start_notify(self.RX_CHARACTERISTIC, self.rx_handler)",
        )],
    )


if __name__ == "__main__":
    main()
