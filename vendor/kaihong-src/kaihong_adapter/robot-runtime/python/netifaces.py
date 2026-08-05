"""Small pure-Python netifaces replacement for the OHOS Python runtime.

The bundled binary netifaces extension was built against a different Python
ABI. ROS only needs interfaces() and ifaddresses(), so keep the workaround
small and avoid loading the incompatible extension.
"""

import fcntl
import socket
import struct

AF_INET = socket.AF_INET
AF_INET6 = socket.AF_INET6
AF_LINK = 17


def interfaces():
    return [name for _index, name in socket.if_nameindex()]


def _ipv4_address(name):
    request = struct.pack("256s", name[:15].encode("ascii", "ignore"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        response = fcntl.ioctl(sock.fileno(), 0x8915, request)  # SIOCGIFADDR
        return socket.inet_ntoa(response[20:24])
    except OSError:
        return None
    finally:
        sock.close()


def _ipv6_addresses(name):
    result = []
    try:
        with open("/proc/net/if_inet6", "r", encoding="ascii") as stream:
            for line in stream:
                raw, _idx, _plen, _scope, _flags, iface = line.split()
                if iface != name:
                    continue
                groups = [raw[pos : pos + 4] for pos in range(0, 32, 4)]
                result.append({"addr": ":".join(groups)})
    except (OSError, ValueError):
        pass
    return result


def ifaddresses(name):
    if name not in interfaces():
        raise ValueError("You must specify a valid interface name.")

    result = {AF_LINK: [{"addr": "00:00:00:00:00:00"}]}
    ipv4 = _ipv4_address(name)
    if ipv4:
        result[AF_INET] = [{"addr": ipv4}]
    ipv6 = _ipv6_addresses(name)
    if ipv6:
        result[AF_INET6] = ipv6
    return result

