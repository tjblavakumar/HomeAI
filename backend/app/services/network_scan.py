"""Local-network device discovery.

Discovers devices on the LAN without requiring root or extra system binaries:
  1. Reads the OS ARP / neighbor table (``ip neigh`` → fallback ``arp -a``).
  2. Optionally runs a lightweight TCP-connect sweep across the subnet to find
     hosts that aren't in the ARP cache and to infer a rough device type.
  3. Resolves hostnames via reverse-DNS and vendors via a built-in MAC OUI
     prefix table.

Degrades gracefully (like ``ocr.py``): if no discovery method yields results
the caller can surface a helpful message instead of crashing.
"""

from __future__ import annotations

import concurrent.futures
import ipaddress
import logging
import re
import socket
import subprocess
from dataclasses import dataclass, field

from app.config import settings
from app.services import llm, oui

logger = logging.getLogger(__name__)


class NetworkScanUnavailableError(RuntimeError):
    """Raised when the host provides no usable way to scan the network."""


# Common ports we probe to detect live hosts and guess a device type.
# port -> (label, device_type hint)
_PROBE_PORTS: dict[int, tuple[str, str]] = {
    22: ("ssh", "computer"),
    80: ("http", "generic"),
    443: ("https", "generic"),
    445: ("smb", "nas"),
    515: ("printer-lpd", "printer"),
    631: ("ipp", "printer"),
    9100: ("jetdirect", "printer"),
    8080: ("http-alt", "generic"),
    5000: ("upnp/nas", "nas"),
    53: ("dns", "router"),
}

@dataclass
class DiscoveredDevice:
    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    device_type: str | None = None
    label: str | None = None
    open_ports: list[int] = field(default_factory=list)


# ── ARP / neighbor table ────────────────────────────────────────────

_IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
_MAC_RE = re.compile(r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})")


def _run(cmd: list[str], timeout: int = 5) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        if result.returncode != 0 and not result.stdout:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _read_arp_table() -> dict[str, str | None]:
    """Return a mapping of ip -> mac (mac may be None) from the OS table."""
    table: dict[str, str | None] = {}

    # Preferred: `ip neigh` (Linux iproute2)
    out = _run(["ip", "neigh"])
    if out:
        for line in out.splitlines():
            ip_match = _IP_RE.search(line)
            if not ip_match:
                continue
            if "FAILED" in line or "INCOMPLETE" in line:
                continue
            mac_match = _MAC_RE.search(line)
            table[ip_match.group(1)] = mac_match.group(1).lower() if mac_match else None
        if table:
            return table

    # Fallback: `arp -a` (portable-ish; BSD/macOS/older Linux)
    out = _run(["arp", "-a"])
    if out:
        for line in out.splitlines():
            ip_match = _IP_RE.search(line)
            if not ip_match:
                continue
            mac_match = _MAC_RE.search(line)
            table[ip_match.group(1)] = mac_match.group(1).lower() if mac_match else None

    return table


# ── Subnet detection ────────────────────────────────────────────────


def _local_ip() -> str | None:
    """Best-effort local IP by opening a UDP socket to a public address.

    No packets are actually sent; this just makes the OS pick the outbound
    interface so we can read its address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _detect_subnet() -> ipaddress.IPv4Network | None:
    if settings.scan_subnet:
        try:
            return ipaddress.ip_network(settings.scan_subnet, strict=False)
        except ValueError:
            logger.warning("Invalid scan_subnet %r; auto-detecting", settings.scan_subnet)

    ip = _local_ip()
    if not ip:
        return None
    try:
        # Assume a /24 home network around the host's own address.
        return ipaddress.ip_network(f"{ip}/24", strict=False)
    except ValueError:
        return None


# ── TCP probe ───────────────────────────────────────────────────────


def _probe_host(ip: str, ports: list[int], timeout: float = 0.4) -> list[int]:
    open_ports: list[int] = []
    for port in ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
        except OSError:
            continue
    return open_ports


def _tcp_sweep(subnet: ipaddress.IPv4Network, ports: list[int]) -> dict[str, list[int]]:
    """Concurrently TCP-connect probe every host address in *subnet*."""
    hosts = [str(h) for h in subnet.hosts()]
    # Cap the sweep so a mistakenly large subnet can't hang the request.
    if len(hosts) > 512:
        hosts = hosts[:512]

    results: dict[str, list[int]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        future_map = {pool.submit(_probe_host, ip, ports): ip for ip in hosts}
        for future in concurrent.futures.as_completed(future_map):
            ip = future_map[future]
            try:
                open_ports = future.result()
            except Exception:
                open_ports = []
            if open_ports:
                results[ip] = open_ports
    return results


# ── Enrichment ──────────────────────────────────────────────────────


def _reverse_dns(ip: str) -> str | None:
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host or None
    except (OSError, socket.herror):
        return None


def _mdns_hostname(ip: str) -> str | None:
    """Best-effort mDNS/.local name lookup for consumer devices.

    Many IoT/home devices only answer multicast DNS, not unicast reverse-DNS.
    Uses the optional ``zeroconf`` package if available; otherwise returns None.
    """
    try:
        from zeroconf import Zeroconf  # optional dependency
    except Exception:
        return None

    try:
        zc = Zeroconf()
        try:
            # resolve_address is available in modern zeroconf; guard defensively.
            resolver = getattr(zc, "resolve_address", None)
            if resolver is None:
                return None
            name = resolver(ip, timeout=1.0)
            if name:
                return str(name).rstrip(".") or None
        finally:
            zc.close()
    except Exception:
        return None
    return None


def _resolve_hostname(ip: str) -> str | None:
    return _reverse_dns(ip) or _mdns_hostname(ip)


def _clean_hostname(hostname: str | None) -> str | None:
    """Strip trailing DNS suffixes for display/keyword matching."""
    if not hostname:
        return None
    h = hostname.rstrip(".")
    for suffix in (".local", ".lan", ".home", ".localdomain"):
        if h.lower().endswith(suffix):
            h = h[: -len(suffix)]
            break
    return h or None


def _guess_device_type(open_ports: list[int], hostname: str | None, vendor: str | None) -> str | None:
    text = f"{hostname or ''} {vendor or ''}".lower()

    # Hostname/vendor keywords are the strongest signal.
    if any(k in text for k in ("printer", "canon", "epson", "brother", "officejet", "laserjet", "pixma")):
        return "printer"
    if any(k in text for k in ("router", "gateway", "netgear", "tp-link", "asus", "linksys", "ubiquiti", "unifi")):
        return "router"
    if any(k in text for k in ("nas", "synology", "qnap", "diskstation", "truenas")):
        return "nas"
    if any(k in text for k in ("echo", "alexa", "sonos", "homepod", "speaker", "chromecast audio")):
        return "speaker"
    if any(k in text for k in ("tv", "roku", "firetv", "appletv", "chromecast", "shield", "bravia", "webos")):
        return "tv"
    if any(k in text for k in ("iphone", "ipad", "android", "pixel", "galaxy", "phone")):
        return "phone"
    if any(k in text for k in ("camera", "cam", "nest", "ring", "wyze", "reolink")):
        return "camera"
    if any(k in text for k in ("macbook", "imac", "desktop", "laptop", "-pc", "thinkpad", "surface")):
        return "computer"

    # Fall back to open-port hints (printer ports are very telling).
    if any(p in open_ports for p in (515, 631, 9100)):
        return "printer"
    if 445 in open_ports or 5000 in open_ports:
        return "nas"
    if 22 in open_ports:
        return "computer"
    if 53 in open_ports:
        return "router"
    if open_ports:
        return "generic"
    return None


_TYPE_WORDS = {
    "printer": "Printer",
    "router": "Router",
    "nas": "NAS",
    "computer": "Computer",
    "phone": "Phone",
    "tv": "TV",
    "speaker": "Speaker",
    "camera": "Camera",
    "iot": "Smart Device",
    "generic": "Device",
}


def _build_label(vendor: str | None, hostname: str | None, device_type: str | None) -> str | None:
    """Compose a human-friendly label from the signals we have (no LLM).

    Examples: "Canon Printer", "Amazon Technologies Speaker", "CANON-MG3600",
    or None when we know nothing beyond the IP.
    """
    clean_host = _clean_hostname(hostname)
    type_word = _TYPE_WORDS.get(device_type or "", "") if device_type and device_type != "generic" else ""

    if vendor:
        # Trim overly long registry names to the first meaningful token(s).
        short_vendor = vendor.split(",")[0].strip()
        if type_word:
            return f"{short_vendor} {type_word}"
        if clean_host:
            return f"{short_vendor} ({clean_host})"
        return f"{short_vendor} device"

    if clean_host:
        return clean_host
    return None


# ── Public entry point ──────────────────────────────────────────────


def scan_network(tcp_probe: bool | None = None) -> list[DiscoveredDevice]:
    """Discover devices on the local network.

    Combines the ARP table with an optional TCP-connect sweep, then enriches
    each host with hostname / vendor / device-type guesses.

    Raises:
        NetworkScanUnavailableError: if no discovery method produced any host.
    """
    if tcp_probe is None:
        tcp_probe = settings.scan_tcp_probe

    arp = _read_arp_table()
    subnet = _detect_subnet()

    sweep: dict[str, list[int]] = {}
    if tcp_probe and subnet is not None:
        try:
            sweep = _tcp_sweep(subnet, list(_PROBE_PORTS.keys()))
        except Exception:
            logger.exception("TCP sweep failed; continuing with ARP results only")

    # Union of IPs from both sources, optionally constrained to the subnet.
    all_ips: set[str] = set(arp.keys()) | set(sweep.keys())
    if subnet is not None:
        constrained = {ip for ip in all_ips if _ip_in(ip, subnet)}
        # If constraining removed everything (e.g. odd ARP entries), keep the union.
        all_ips = constrained or all_ips

    if not all_ips:
        raise NetworkScanUnavailableError(
            "Could not discover any devices. The ARP table was empty and the TCP "
            "probe found no hosts. This can happen in containers or on networks "
            "that block probing. Try setting SCAN_SUBNET in .env, or ensure the "
            "server runs on the same LAN as your devices."
        )

    devices: list[DiscoveredDevice] = []
    for ip in sorted(all_ips, key=_ip_sort_key):
        mac = arp.get(ip)
        open_ports = sweep.get(ip, [])
        hostname = _resolve_hostname(ip)
        vendor = oui.lookup_vendor(mac)
        device_type = _guess_device_type(open_ports, hostname, vendor)
        label = _build_label(vendor, hostname, device_type)
        devices.append(
            DiscoveredDevice(
                ip=ip,
                mac=mac,
                hostname=hostname,
                vendor=vendor,
                device_type=device_type,
                label=label,
                open_ports=open_ports,
            )
        )

    # Optional LLM refinement: turn vendor + hostname + ports into a friendlier
    # product label and a better device type. Skipped silently when the LLM is
    # not configured; the heuristic label above remains as the fallback.
    if settings.scan_llm_label:
        _refine_labels_with_llm(devices)

    return devices


def _refine_labels_with_llm(devices: list[DiscoveredDevice]) -> None:
    """Enrich device labels/types via the LLM, in place. Best-effort."""
    # Only bother for devices where we have at least a vendor or hostname.
    candidates = [d for d in devices if d.vendor or _clean_hostname(d.hostname)]
    if not candidates:
        return
    for device in candidates:
        try:
            guess = llm.guess_product(device.vendor, device.hostname, device.open_ports)
        except llm.LLMNotConfiguredError:
            return  # no key configured — stop trying, keep heuristic labels
        except Exception:
            logger.exception("LLM product guess failed for %s", device.ip)
            continue
        label = (guess.get("label") or "").strip()
        dtype = (guess.get("device_type") or "").strip().lower()
        # Reject empty or placeholder labels (e.g. a literal "<Vendor>") — keep
        # the heuristic label already on the device in that case.
        if label and "<" not in label and ">" not in label:
            device.label = label[:80]
        # Only tighten the device type; don't let a vague "generic" guess wipe a
        # more specific heuristic classification.
        if dtype in _TYPE_WORDS and dtype != "generic":
            device.device_type = dtype


def _ip_in(ip: str, subnet: ipaddress.IPv4Network) -> bool:
    try:
        return ipaddress.ip_address(ip) in subnet
    except ValueError:
        return False


def _ip_sort_key(ip: str) -> int:
    try:
        return int(ipaddress.ip_address(ip))
    except ValueError:
        return 0
