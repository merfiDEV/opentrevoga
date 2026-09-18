import contextlib
import functools
import logging


logger = logging.getLogger(__name__)


def command(context, *, admin: bool = False):
    """Guard a command handler: optional admin check + auto-delete of the command.

    Usage:
        @client.on(events.NewMessage(...))
        @command(context, admin=True)
        async def handler(event):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(event):
            if admin and not context.is_admin(event.sender_id):
                return
            try:
                await func(event)
            finally:
                with contextlib.suppress(Exception):
                    await event.delete()

        return wrapper

    return decorator
