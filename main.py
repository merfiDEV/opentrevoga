import asyncio
import contextlib
import logging
import signal

from trevoga.app import run


async def _main() -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(sig, stop.set)
    runner = asyncio.create_task(run())
    stopper = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait(
        {runner, stopper}, return_when=asyncio.FIRST_COMPLETED
    )
    if runner in done:
        stopper.cancel()
        await runner
        return
    logging.getLogger(__name__).info("Shutdown signal received")
    runner.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runner


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Interrupted by user")
