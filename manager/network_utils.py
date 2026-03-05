# -*- coding: utf-8 -*-
"""
網路連線偵測工具
"""
import socket
import urllib.request


def check_internet(timeout: int = 3) -> bool:
    """
    檢查是否有網路連線。
    嘗試連線多個可靠的伺服器來判斷。
    """
    test_urls = [
        ("pypi.org", 443),
        ("github.com", 443),
        ("download.pytorch.org", 443),
    ]
    for host, port in test_urls:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except (socket.timeout, OSError):
            continue
    return False


def check_url_reachable(url: str, timeout: int = 5) -> bool:
    """檢查特定 URL 是否可達"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False
