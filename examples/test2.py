from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from litestar.exceptions import MissingDependencyException
from litestar.middleware.compression.facade import CompressionFacade
from litestar.testing import create_test_client
from litestar.handlers import HTTPRouteHandler
from litestar.status_codes import HTTP_200_OK
from litestar import MediaType, get
import pytest
from litestar.config.compression import CompressionConfig

try:
    from zstandard import ZstdCompressor, ZstdCompressionWriter
except ImportError as e:
    raise MissingDependencyException("zstandard") from e


if TYPE_CHECKING:
    from io import BytesIO


@pytest.fixture()
def handler() -> HTTPRouteHandler:
    @get(path="/", media_type=MediaType.TEXT)
    def handler_fn() -> str:
        return "_litestar_" * 4000

    return handler_fn

def test_compression_with_custom_backend(handler: HTTPRouteHandler) -> None:
    class ZstdCompression(CompressionFacade):
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
            # modes: dict[Literal["generic", "text", "font"], int] = {
            #     "text": int(MODE_TEXT),
            #     "font": int(MODE_FONT),
            #     "generic": int(MODE_GENERIC),
            # }
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

    config = CompressionConfig(backend="zstd", compression_facade=ZstdCompression,minimum_size=1)
    with create_test_client([handler], compression_config=config) as client:
        response = client.get("/", headers={"Accept-Encoding": "zstd"})
        assert response.status_code == HTTP_200_OK
        assert response.text == '(�/�`@��\x00\x00P_litestar_\x01\x003��\x05\t'
        assert response.headers["Content-Encoding"] == "zstd"
        assert int(response.headers["Content-Length"]) < 40000

