"""Session ID generation utilities"""
import hashlib


def generate_session_id(stream_name: str, client_ip: str, token: str) -> str:
    """
    Generate session ID using Flussonic's method: hash(name + ip + token)

    Args:
        stream_name: Stream name
        client_ip: Client IP address
        token: Authorization token

    Returns:
        SHA256 hash of combined parameters
    """
    combined = f"{stream_name}{client_ip}{token}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
