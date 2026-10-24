"""An OS lease prevents two API workers from launching overlapping missions."""
import os

from . import state


class RuntimeLease:
    def __init__(self) -> None:
        self.stream = None

    def acquire(self) -> None:
        path = state.AUDIT_DATABASE.with_suffix(".runtime.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("a+b")
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            stream.close()
            raise RuntimeError("El runtime ya está abierto. Usa una sola instancia de la API y un worker.") from error
        self.stream = stream

    def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
