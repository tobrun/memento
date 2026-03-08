"""Entry point — python -m memento"""

import asyncio
import logging
import signal
from pathlib import Path

from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M]",
)
log = logging.getLogger("memory-agent")


async def main_async(args) -> None:
    # Wire db module to the configured DB directory
    import memento.db as db_module
    import memento.agents as agents_module

    db_module.MEMORY_DB_DIR = args.db_dir

    # Wire model into agents module
    from memento.config import build_model
    agents_module.MODEL = build_model()

    from memento.agents import MemoryAgent
    from memento.api import build_http
    from memento.watcher import consolidation_loop, watcher_manager
    from memento.config import MODEL_NAME, OPENAI_API_BASE

    agent = MemoryAgent()

    model_desc = f"{MODEL_NAME} via {OPENAI_API_BASE}" if OPENAI_API_BASE else MODEL_NAME
    log.info("Memento starting")
    log.info(f"  Model: {model_desc}")
    log.info(f"  Database dir: {args.db_dir}")
    log.info(f"  Watch: {args.watch}")
    log.info(f"  Consolidate: every {args.consolidate_every}m")
    log.info(f"  API: http://localhost:{args.port}")

    inbox_root = Path(args.watch)
    inbox_root.mkdir(parents=True, exist_ok=True)

    # Ensure general datasource DB exists on startup
    from memento.db import init_datasource_db
    init_datasource_db("general")

    # Background tasks
    tasks = [
        asyncio.create_task(watcher_manager(agent, inbox_root, args.db_dir)),
        asyncio.create_task(consolidation_loop(agent, inbox_root, args.consolidate_every)),
    ]

    # HTTP server
    app = build_http(agent, watch_path=args.watch)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", args.port)
    await site.start()

    log.info(f"Agent running. Drop files in {args.watch}/ or POST to http://localhost:{args.port}/api/ingest/general")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


def main() -> None:
    from memento.config import parse_args
    args = parse_args()

    loop = asyncio.new_event_loop()

    def shutdown(sig):
        log.info(f"Shutting down (signal {sig})...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown, sig)

    try:
        loop.run_until_complete(main_async(args))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        loop.close()
        log.info("Memento stopped.")


if __name__ == "__main__":
    main()
