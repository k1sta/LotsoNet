import ipaddress
import socket

import psutil


def get_interface_ip(interface_name):
    addresses = psutil.net_if_addrs()
    if interface_name in addresses:
        for addr in addresses[interface_name]:
            if addr.family == socket.AF_INET:
                return addr.address
    return None


def _interface_netmask(interface_name):
    addresses = psutil.net_if_addrs()
    if interface_name in addresses:
        for addr in addresses[interface_name]:
            if addr.family == socket.AF_INET:
                return addr.netmask
    return None


def pick_primary_interface(preferred=None):
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    if preferred and preferred in addrs:
        return preferred

    candidates = []
    for name, entries in addrs.items():
        if name.startswith("lo"):
            continue
        if name not in stats or not stats[name].isup:
            continue
        if any(entry.family == socket.AF_INET for entry in entries):
            candidates.append(name)

    if len(candidates) > 1:
        print(f"[netutil] Multiple candidate interfaces found: {candidates}. Using {candidates[0]!r}.")

    return candidates[0] if candidates else None


def get_local_ip(preferred_interface=None):
    iface = pick_primary_interface(preferred_interface)
    return get_interface_ip(iface) if iface else None


def get_broadcast_address(ip, interface_name):
    netmask = _interface_netmask(interface_name)
    if not netmask:
        return "255.255.255.255"
    try:
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network.broadcast_address)
    except ValueError:
        return "255.255.255.255"
