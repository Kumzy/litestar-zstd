from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from litestar.exceptions import MissingDependencyException
from litestar.middleware.compression.facade import CompressionFacade

try:
    from zstandard import ZstdCompressor
except ImportError as e:
    raise MissingDependencyException("zstandard") from e


if TYPE_CHECKING:
    from io import BytesIO

    from litestar.config.compression import CompressionConfig


class ZstandardCompressionFacade(CompressionFacade):
    __slots__ = ("compressor", "buffer", "compression_encoding")

    encoding = 'zstd'

    def __init__(
            self,
            buffer: BytesIO,
            compression_encoding: Literal['zstd'] | str,
            config: CompressionConfig,
    ) -> None:
        self.buffer = buffer
        self.compression_encoding = compression_encoding
        self.compressor = ZstdCompressor(
            level=3,
            dict_data=None,
            compression_params=None,
            write_checksum=None,
            write_content_size=None,
            write_dict_id=None,
            threads=0
        )

    def write(self, body: bytes) -> None:
        self.buffer.write(self.compressor.compress(body))

    def close(self) -> None:
        ...
