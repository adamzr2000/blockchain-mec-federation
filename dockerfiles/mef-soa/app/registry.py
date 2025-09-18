from threading import RLock
_peers = {}   # peer_id -> {url, token}
_lock = RLock()

def add_peer(peer_id: str, base_url: str, token: str) -> None:
    with _lock:
        _peers[peer_id] = {"url": base_url, "token": token}

def list_peers() -> dict:
    with _lock:
        return dict(_peers)

def clear_peers() -> int:
    with _lock:
        n = len(_peers)
        _peers.clear()
        return n
