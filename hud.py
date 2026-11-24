"""Launch an iOS app with the Metal HUD, no root (userspace tunnel).
Usage: hud.py <udid> <bundle_id | --apps> [iphone_ip [port]]
Without an IP the iPhone is found on the local Wi-Fi via Bonjour. With an IP (e.g. its
Tailscale 100.x address) it connects directly; set HUD_SOCKS=host:port to dial through a
SOCKS5 proxy (userspace tailscaled)."""
import asyncio
import os
import socket
import struct
import sys

from pymobiledevice3.pair_records import generate_host_id as _host_id
from pymobiledevice3.remote import tunnel_service
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.userspace_tunnel import UserspaceDialPlane
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl
from pymobiledevice3.services.installation_proxy import InstallationProxyService


def socks_connect(proxy: str, host: str, port: int) -> socket.socket:
    phost, pport = proxy.rsplit(":", 1)
    s = socket.create_connection((phost, int(pport)), timeout=15)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00":
        raise ConnectionError("SOCKS5 proxy refused auth method")
    s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(host) + struct.pack(">H", port))
    rep = s.recv(10)
    if len(rep) < 2 or rep[1] != 0:
        raise ConnectionError(f"SOCKS5 connect to {host}:{port} failed")
    s.settimeout(None)
    return s


def route_via_socks(proxy: str, target: str) -> None:
    """Send only connections to `target` through the proxy; everything else stays direct."""
    orig_open, orig_create = asyncio.open_connection, socket.create_connection

    async def open_connection(host=None, port=None, **kw):
        if host == target:
            return await orig_open(sock=await asyncio.to_thread(socks_connect, proxy, host, port), **kw)
        return await orig_open(host, port, **kw)

    def create_connection(addr, *a, **kw):
        return socks_connect(proxy, *addr) if addr[0] == target else orig_create(addr, *a, **kw)

    asyncio.open_connection = open_connection
    tunnel_service.create_connection = create_connection


async def find_service(udid: str, ip: str | None, port: int):
    if ip:
        return await tunnel_service.create_core_device_tunnel_service_using_remotepairing(udid, ip, port)
    services = await tunnel_service.get_remote_pairing_tunnel_services(udid=udid)
    if not services:
        sys.exit("iPhone not found on Wi-Fi (unlocked? same network? paired?)")
    return services[0]


async def main(udid: str, bundle: str, ip: str | None, port: int) -> None:
    tunnel_service.USE_USERSPACE_TUNNEL = True  # pure-Python TUN, so no root needed
    if os.environ.get("HUD_PAIR_HOST"):
        # The phone pins the host ID, derived from the pairing machine's hostname; reuse it elsewhere.
        pair_host = os.environ["HUD_PAIR_HOST"]
        tunnel_service.generate_host_id = lambda hostname=None: _host_id(pair_host)
    if ip and os.environ.get("HUD_SOCKS"):
        route_via_socks(os.environ["HUD_SOCKS"], ip)
    provider = await find_service(udid, ip, port)
    try:
        async with provider.start_tcp_tunnel() as t:
            t.client.tun.set_peer(t.address)
            async with UserspaceDialPlane(t.client.tun, t.address) as plane:
                rsd = RemoteServiceDiscoveryService((t.address, t.port), open_connection=plane.dial)
                await rsd.connect()
                if bundle == "--apps":  # list user apps as "category<TAB>name<TAB>bundle"
                    apps = await InstallationProxyService(lockdown=rsd).get_apps(application_type="User")
                    for bid, info in apps.items():
                        name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or bid
                        print(f"{info.get('LSApplicationCategoryType', '')}\t{name}\t{bid}")
                    sys.stdout.flush()
                    os._exit(0)
                async with DvtProvider(rsd) as dvt, ProcessControl(dvt) as pc:
                    pid = await pc.launch(bundle_id=bundle, kill_existing=True,
                                          environment={"MTL_HUD_ENABLED": "1"})
                    print(f"launched {bundle} pid {pid}", flush=True)
                    os._exit(0)  # userspace tunnel teardown hangs; nothing left to clean up
    finally:
        await provider.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(a[0], a[1], a[2] if len(a) > 2 else None, int(a[3]) if len(a) > 3 else 49152))
