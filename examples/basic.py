import uvicorn
from typing import TYPE_CHECKING

from litestar import Litestar, get, websocket, MediaType
from litestar.config.compression import CompressionConfig
from litestar_zstd import ZstdCompressionMiddleware, ZstandardCompressionFacade

if TYPE_CHECKING:
    from litestar import WebSocket

@websocket("/my-websocket")
async def websocket_handler(socket: "WebSocket") -> None:
    """
    Websocket handler - is excluded because the middleware scopes includes 'ScopeType.HTTP'
    """
    await socket.accept()
    await socket.send_json({"hello websocket"})
    await socket.close()


@get("/first_path", sync_to_thread=False)
def first_handler() -> dict[str, str]:
    """Handler is excluded due to regex pattern matching "first_path"."""
    return {"hello": "first"}


@get("/second_path", sync_to_thread=False)
def second_handler() -> dict[str, str]:
    """Handler is excluded due to regex pattern matching "second_path"."""
    return {"hello": "second"}


@get("/third_path", exclude_from_zstd=True, sync_to_thread=False)
def third_handler() -> dict[str, str]:
    """Handler is excluded due to the opt key 'exclude_from_zstd' matching the middleware 'exclude_opt_key'."""
    return {"hello": "second"}


@get("/greet", sync_to_thread=False)
def not_excluded_handler() -> dict[str, str]:
    """This handler is not excluded, and thus the middleware will execute on every incoming request to it."""
    return {"hello": "world"}


config = CompressionConfig(
        minimum_size=1,
        backend="zstd",
        middleware_class=ZstdCompressionMiddleware,
        compression_facade=ZstandardCompressionFacade,
        exclude_opt_key="exclude_from_zstd",
    )

app = Litestar(
    route_handlers=[
        websocket_handler,
        first_handler,
        second_handler,
        third_handler,
        not_excluded_handler,
    ],
    compression_config=config,
)


if __name__ == "__main__":
    uvicorn.run(
        app
    )