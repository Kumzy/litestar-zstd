from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from litestar.exceptions import MissingDependencyException
from litestar.middleware.compression import CompressionMiddleware
from litestar.types.asgi_types import Receive, Send, Scope

try:
    from zstandard import ZstdCompressor
except ImportError as e:
    raise MissingDependencyException("zstandard") from e


if TYPE_CHECKING:
    from io import BytesIO

    from litestar.config.compression import CompressionConfig


class ZstdCompressionMiddleware(CompressionMiddleware):
    """Compression Middleware Wrapper.

    This is a wrapper allowing for generic compression configuration / handler middleware
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI callable.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive function.
            send: The ASGI send function.

        Returns:
            None
        """

        await self.app(
            scope,
            receive,
            self.create_compression_send_wrapper(
                send=send, compression_encoding='zstd', scope=scope
            ),
        )
        return
