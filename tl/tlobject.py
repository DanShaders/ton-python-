import base64
import json
import typing
import struct
from typing import override, Self, cast, Any, Callable, TextIO
from collections.abc import Mapping
from abc import ABC, abstractmethod


def _json_default(value: bytes) -> str:
    if isinstance(value, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
        return base64.b64encode(value).decode('ascii')
    else:
        return repr(value)  # pyright: ignore[reportUnreachable]


class TLObject(ABC):
    CONSTRUCTOR_ID: int
    SUBCLASS_OF_ID: int
    # Cache mapping class names to classes for quick lookup during from_dict
    _name_registry: dict[str, list['TLObject']] = {}

    @staticmethod
    def serialize_bytes(data: bytes | str) -> bytes:
        """Write bytes by using Telegram guidelines"""
        if not isinstance(data, bytes):
            data = data.encode('utf-8')

        r: list[bytes] = []
        if len(data) < 254:
            padding = (len(data) + 1) % 4
            if padding != 0:
                padding = 4 - padding

            r.append(bytes([len(data)]))
            r.append(data)

        else:
            padding = len(data) % 4
            if padding != 0:
                padding = 4 - padding

            r.append(bytes([
                254,
                len(data) % 256,
                (len(data) >> 8) % 256,
                (len(data) >> 16) % 256
            ]))
            r.append(data)

        r.append(bytes(padding))
        return b''.join(r)

    @override
    def __eq__(self, o: object):
        return isinstance(o, type(self)) and self.to_dict() == o.to_dict()

    @override
    def __ne__(self, o: object):
        return not isinstance(o, type(self)) or self.to_dict() != o.to_dict()

    @override
    def __str__(self):
        return self.__class__.__name__ + f'<{str(self.to_dict())}>'

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        raise NotImplementedError

    def to_json(self, fp: TextIO | None = None, default: Callable[[bytes], str] = _json_default):
        """
        Represent the current `TLObject` as JSON.

        If ``fp`` is given, the JSON will be dumped to said
        file pointer, otherwise a JSON string will be returned.

        Note that bytes cannot be represented
        in JSON, so if those are found, they will be base64
        encoded and ISO-formatted, respectively, by default.
        """
        d = self.to_dict()
        if fp:
            return json.dump(d, fp, default=default)
        else:
            return json.dumps(d, default=default)

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:  # pyright: ignore[reportExplicitAny]
        raise NotImplementedError

    @classmethod
    def from_json(cls, source: str) -> Self:
        return cls.from_dict(cast(dict[str, Any], json.loads(source)))  # pyright: ignore[reportExplicitAny]

    @abstractmethod
    def to_bytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_reader(cls, reader: 'BinaryReader') -> Self:
        raise NotImplementedError


class TLRequest(TLObject, ABC):

    @abstractmethod
    @override
    def to_dict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        raise NotImplementedError

    @classmethod
    @abstractmethod
    @override
    def from_dict(cls, d: dict[str, Any]) -> Self:  # pyright: ignore[reportExplicitAny]
        raise NotImplementedError

    @abstractmethod
    @override
    def to_bytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    @override
    def from_reader(cls, reader: 'BinaryReader') -> Self:
        raise NotImplementedError


class BinaryReader:

    def __init__(self, data: bytes, tl_objects: Mapping[int, type[TLObject]]):
        self.stream: bytes = data or b''
        self.position: int = 0
        self._last: bytes | None = None  # Should come in handy to spot -404 errors
        self.tl_objects: Mapping[int, type[TLObject]] = tl_objects

    # "All numbers are written as little endian."
    # https://core.telegram.org/mtproto
    def read_byte(self) -> int:
        """Reads a single byte value."""
        value = typing.cast(int, struct.unpack_from("<B", self.stream, self.position)[0])
        self.position += 1
        return value

    def read_int(self, signed: bool = True) -> int:
        """Reads an integer (4 bytes) value."""
        fmt = '<i' if signed else '<I'
        value = typing.cast(int, struct.unpack_from(fmt, self.stream, self.position)[0])
        self.position += 4
        return value

    def read_long(self, signed: bool = True) -> int:
        """Reads a long integer (8 bytes) value."""
        fmt = '<q' if signed else '<Q'
        value = typing.cast(int, struct.unpack_from(fmt, self.stream, self.position)[0])
        self.position += 8
        return value

    def read_double(self) -> float:
        """Reads a real floating point (8 bytes) value."""
        value = typing.cast(float, (struct.unpack_from("<d", self.stream, self.position))[0])
        self.position += 8
        return value

    def read_large_int(self, bits: int, signed: bool = True) -> int:
        """Reads a n-bits long integer value."""
        return int.from_bytes(
            self.read(bits // 8), byteorder='little', signed=signed)

    def read_bytes(self, length: int):
        return self.read(length)[::-1]

    def read(self, length: int = -1):
        """Read the given amount of bytes, or -1 to read all remaining."""
        if length >= 0:
            result = self.stream[self.position:self.position + length]
            self.position += length
        else:
            result = self.stream[self.position:]
            self.position += len(result)
        if (length >= 0) and (len(result) != length):
            raise BufferError(
                'No more data left to read (need {}, got {}: {}); last read {}'
                .format(length, len(result), repr(result), repr(self._last))
            )

        self._last = result
        return result

    def get_bytes(self):
        """Gets the byte array representing the current buffer as a whole."""
        return self.stream

    def tgread_bytes(self):
        """
        Reads a Telegram-encoded byte array, without the need of
        specifying its length.
        """
        first_byte: int = self.read_byte()
        if first_byte == 254:
            length = self.read_byte() | (self.read_byte() << 8) | (
                self.read_byte() << 16)
            padding = length % 4
        else:
            length = first_byte
            padding = (length + 1) % 4

        data = self.read(length)
        if padding > 0:
            padding = 4 - padding
            _ = self.read(padding)

        return data

    def tgread_string(self):
        """Reads a Telegram-encoded string."""
        return str(self.tgread_bytes(), encoding='utf-8', errors='replace')

    def tgread_bool(self):
        """Reads a Telegram boolean value."""
        value = self.read_int(signed=False)
        if value == 0x997275b5:  # boolTrue
            return True
        elif value == 0xbc799737:  # boolFalse
            return False
        else:
            raise RuntimeError('Invalid boolean code {}'.format(hex(value)))

    def tgread_object(self) -> typing.Any:  # pyright: ignore[reportAny]
        """Reads a TL object."""
        constructor_id = self.read_int(signed=False)
        class_ = self.tl_objects.get(constructor_id, None)
        if class_ is None:
            # The class was None, but there's still a
            # chance of it being a manually parsed value like bool!
            value = constructor_id
            if value == 0x997275b5:  # boolTrue
                return True
            elif value == 0xbc799737:  # boolFalse
                return False
            elif value == 0x1cb5c415:  # Vector
                return [self.tgread_object() for _ in range(self.read_int())]

            self.seek(-4)  # Go back
            pos = self.position
            error = Exception(constructor_id, self.read())
            self.position = pos
            raise error

        return class_.from_reader(self)


    def close(self):
        """Closes the reader, freeing the BytesIO stream."""
        self.stream = b''

    def seek(self, offset: int):
        """
        Seeks the stream position given an offset from the current position.
        The offset may be negative.
        """
        self.position += offset

    def __enter__(self):
        return self

    def __exit__(self, exc_type: str, exc_val: str, exc_tb: str):
        self.close()

