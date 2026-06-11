import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionStatus(str, Enum):
    INICIANDO = "iniciando"
    ESPERANDO_LOGIN = "esperando_login"
    EJECUTANDO = "ejecutando"
    COMPLETADO = "completado"
    ERROR = "error"
    CANCELADO = "cancelado"
    LIBRE = "libre"  # flujo falló pero navegador sigue abierto para inspección manual


@dataclass
class Session:
    id: str
    banco: str
    status: SessionStatus = SessionStatus.INICIANDO
    logs: list = field(default_factory=list)
    login_event: threading.Event = field(default_factory=threading.Event)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    driver: Optional[object] = None
    resultado: Optional[int] = None
    error: Optional[str] = None
    current_frame: Optional[bytes] = None

    def log(self, msg: str) -> None:
        self.logs.append(msg)


_TERMINAL = {SessionStatus.COMPLETADO, SessionStatus.ERROR, SessionStatus.CANCELADO}


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def crear(self, banco: str) -> Session:
        session = Session(id=str(uuid.uuid4()), banco=banco)
        with self._lock:
            # Purge old terminal sessions for this banco
            stale = [
                sid for sid, s in self._sessions.items()
                if s.banco == banco and s.status in _TERMINAL
            ]
            for sid in stale:
                del self._sessions[sid]
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def get_activa(self, banco: str) -> Optional[Session]:
        """Returns the non-terminal session for a banco, if any."""
        for s in self._sessions.values():
            if s.banco == banco and s.status not in _TERMINAL:
                return s
        return None

    def get_any_activa(self) -> Optional[Session]:
        """Returns any non-terminal session across all banks."""
        for s in self._sessions.values():
            if s.status not in _TERMINAL:
                return s
        return None


session_manager = SessionManager()
