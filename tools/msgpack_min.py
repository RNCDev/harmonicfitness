"""A minimal MessagePack codec: just the types Fish Audio's API takes (None, bool, int, float, str,
bytes, list, dict), so sweatcast needs no extra dependency. Follows the MessagePack spec
(https://github.com/msgpack/msgpack/blob/master/spec.md). The decoder lets the tests' fake Fish
server read what the engine sends."""
import struct


def pack(obj):
    out = bytearray()
    _pack(obj, out)
    return bytes(out)


def _pack(obj, out):
    if obj is None:
        out.append(0xC0)
    elif obj is True:
        out.append(0xC3)
    elif obj is False:
        out.append(0xC2)
    elif isinstance(obj, int):
        if 0 <= obj < 0x80:
            out.append(obj)
        elif -32 <= obj < 0:
            out.append(obj & 0xFF)
        elif 0 <= obj < 1 << 8:
            out += b"\xCC" + struct.pack(">B", obj)
        elif 0 <= obj < 1 << 16:
            out += b"\xCD" + struct.pack(">H", obj)
        elif 0 <= obj < 1 << 32:
            out += b"\xCE" + struct.pack(">I", obj)
        elif 0 <= obj < 1 << 64:
            out += b"\xCF" + struct.pack(">Q", obj)
        elif -(1 << 7) <= obj:
            out += b"\xD0" + struct.pack(">b", obj)
        elif -(1 << 15) <= obj:
            out += b"\xD1" + struct.pack(">h", obj)
        elif -(1 << 31) <= obj:
            out += b"\xD2" + struct.pack(">i", obj)
        else:
            out += b"\xD3" + struct.pack(">q", obj)
    elif isinstance(obj, float):
        out += b"\xCB" + struct.pack(">d", obj)
    elif isinstance(obj, str):
        data = obj.encode("utf-8")
        n = len(data)
        if n < 32:
            out.append(0xA0 | n)
        elif n < 1 << 8:
            out += b"\xD9" + struct.pack(">B", n)
        elif n < 1 << 16:
            out += b"\xDA" + struct.pack(">H", n)
        else:
            out += b"\xDB" + struct.pack(">I", n)
        out += data
    elif isinstance(obj, (bytes, bytearray)):
        n = len(obj)
        if n < 1 << 8:
            out += b"\xC4" + struct.pack(">B", n)
        elif n < 1 << 16:
            out += b"\xC5" + struct.pack(">H", n)
        else:
            out += b"\xC6" + struct.pack(">I", n)
        out += obj
    elif isinstance(obj, (list, tuple)):
        n = len(obj)
        if n < 16:
            out.append(0x90 | n)
        elif n < 1 << 16:
            out += b"\xDC" + struct.pack(">H", n)
        else:
            out += b"\xDD" + struct.pack(">I", n)
        for x in obj:
            _pack(x, out)
    elif isinstance(obj, dict):
        n = len(obj)
        if n < 16:
            out.append(0x80 | n)
        elif n < 1 << 16:
            out += b"\xDE" + struct.pack(">H", n)
        else:
            out += b"\xDF" + struct.pack(">I", n)
        for k, v in obj.items():
            _pack(k, out)
            _pack(v, out)
    else:
        raise TypeError(f"can't pack {type(obj).__name__} as MessagePack")


def unpack(data):
    obj, end = _unpack(memoryview(data), 0)
    if end != len(data):
        raise ValueError(f"{len(data) - end} bytes left over after the MessagePack value")
    return obj


def _unpack(b, i):
    t = b[i]
    i += 1
    if t < 0x80:
        return t, i
    if t >= 0xE0:
        return t - 0x100, i
    if 0x80 <= t <= 0x8F:
        return _map(b, i, t & 0x0F)
    if 0x90 <= t <= 0x9F:
        return _array(b, i, t & 0x0F)
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return bytes(b[i:i + n]).decode("utf-8"), i + n
    simple = {0xC0: None, 0xC2: False, 0xC3: True}
    if t in simple:
        return simple[t], i
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q",
             0xCA: ">f", 0xCB: ">d"}
    if t in fixed:
        size = struct.calcsize(fixed[t])
        return struct.unpack(fixed[t], b[i:i + size])[0], i + size
    sized = {0xC4: (">B", "bin"), 0xC5: (">H", "bin"), 0xC6: (">I", "bin"), 0xD9: (">B", "str"),
             0xDA: (">H", "str"), 0xDB: (">I", "str"), 0xDC: (">H", "array"), 0xDD: (">I", "array"),
             0xDE: (">H", "map"), 0xDF: (">I", "map")}
    if t in sized:
        fmt, kind = sized[t]
        size = struct.calcsize(fmt)
        n = struct.unpack(fmt, b[i:i + size])[0]
        i += size
        if kind == "bin":
            return bytes(b[i:i + n]), i + n
        if kind == "str":
            return bytes(b[i:i + n]).decode("utf-8"), i + n
        return (_array if kind == "array" else _map)(b, i, n)
    raise ValueError(f"MessagePack type 0x{t:02x} isn't supported here")


def _array(b, i, n):
    out = []
    for _ in range(n):
        x, i = _unpack(b, i)
        out.append(x)
    return out, i


def _map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = _unpack(b, i)
        v, i = _unpack(b, i)
        out[k] = v
    return out, i
