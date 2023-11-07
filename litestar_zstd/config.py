from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, TypeVar, cast

from zstandard import compress, decompress, ZstdCompressor, ZstdDecompressor, ZstdCompressionDict, ZstdCompressionWriter, ZstdCompressionReader
from litestar.constants import HTTP_DISCONNECT, HTTP_RESPONSE_START, WEBSOCKET_CLOSE, WEBSOCKET_DISCONNECT, SCOPE_STATE_IS_CACHED, SCOPE_STATE_RESPONSE_COMPRESSED
from litestar.datastructures import Headers, MutableScopeHeaders
from litestar.exceptions import ImproperlyConfiguredException
from litestar.serialization import decode_json, encode_json
from litestar.types import Empty
from litestar.utils import delete_litestar_scope_state, get_litestar_scope_state, set_litestar_scope_state
from litestar.utils.dataclass import simple_asdict

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from collections.abc import AsyncGenerator, Callable, Coroutine
    from typing import Any
    from litestar import Litestar
    from litestar.datastructures.state import State
    from litestar.types import BeforeMessageSendHookHandler, EmptyType, Message, Scope, Send, HTTPResponseStartEvent


SESSION_SCOPE_KEY = "_asyncpg_db_connection"
SESSION_TERMINUS_ASGI_EVENTS = {HTTP_RESPONSE_START, HTTP_DISCONNECT, WEBSOCKET_DISCONNECT, WEBSOCKET_CLOSE}
T = TypeVar("T")


@dataclass
class ZstdConfig:
    """Zstd Configuration."""

    level: int = 3
    """Integer compression level. Valid values are all negative integers through 22.
    Lower values generally yield faster operations with lower compression ratios.
    Higher values are generally slower but compress better. 
    The default is 3, which is what the zstd CLI uses.
    Negative levels effectively engage --fast mode from the zstd CLI."""

    dict_data: ZstdCompressionDict | None = None
    """A ZstdCompressionDict to be used to compress with dictionary data. """

    write_checksum: bool | None = None
    """If True, a 4 byte content checksum will be written with the compressed data,
    allowing the decompressor to perform content verification."""

    compressor = ZstdCompressionWriter()


    def __post_init__(self) -> None:
        if self.level > 22:
            raise ImproperlyConfiguredException("level must be inferior of 22")


    @property
    def signature_namespace(self) -> dict[str, Any]:
        """Return the plugin's signature namespace.

        Returns:
            A string keyed dict of names to be added to the namespace for signature forward reference resolution.
        """
        return {"Zstd": Zstd}


    def write(self, body: bytes) -> None:
        """Write compressed bytes.

        Args:
            body: Message body to process

        Returns:
            None
        """

        self.compressor.write(body)
        self.compressor.flush()

    def send_wrapper(
        self,
        send: Send,
        scope: Scope,
    ) -> Send:
        """Wrap ``send`` to handle brotli compression.

        Args:
            send: The ASGI send function.
            scope: The ASGI connection scope

        Returns:
            An ASGI send function.
        """
        bytes_buffer = BytesIO()

        initial_message: HTTPResponseStartEvent | None = None
        started = False

        async def send_wrapper(message: Message) -> None:
            """Handle and compresses the HTTP Message with brotli.

            Args:
                message (Message): An ASGI Message.
            """
            nonlocal started
            nonlocal initial_message

            if message["type"] == "http.response.start":
                initial_message = message
                return

            if initial_message and get_litestar_scope_state(scope, SCOPE_STATE_IS_CACHED):
                await send(initial_message)
                await send(message)
                return

            if initial_message and message["type"] == "http.response.body":
                body = message["body"]
                more_body = message.get("more_body")

                if not started:
                    started = True
                    if more_body:
                        headers = MutableScopeHeaders(initial_message)
                        headers["Content-Encoding"] = "zstd"
                        headers.extend_header_value("vary", "Accept-Encoding")
                        del headers["Content-Length"]
                        set_litestar_scope_state(scope, SCOPE_STATE_RESPONSE_COMPRESSED, True)

                        self.write(body)

                        message["body"] = bytes_buffer.getvalue()
                        bytes_buffer.seek(0)
                        bytes_buffer.truncate()
                        await send(initial_message)
                        await send(message)

                    elif len(body) >= self.config.minimum_size:
                        self.write(body)
                        self.decompressor.close()
                        body = bytes_buffer.getvalue()

                        headers = MutableScopeHeaders(initial_message)
                        headers["Content-Encoding"] = "zstd"
                        headers["Content-Length"] = str(len(body))
                        headers.extend_header_value("vary", "Accept-Encoding")
                        message["body"] = body
                        set_litestar_scope_state(scope, SCOPE_STATE_RESPONSE_COMPRESSED, True)

                        await send(initial_message)
                        await send(message)

                    else:
                        await send(initial_message)
                        await send(message)

                else:
                    self.write(body)
                    if not more_body:
                        self.decompressor.close()

                    message["body"] = bytes_buffer.getvalue()

                    bytes_buffer.seek(0)
                    bytes_buffer.truncate()

                    if not more_body:
                        bytes_buffer.close()

                    await send(message)

        return send_wrapper