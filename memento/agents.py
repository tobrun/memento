"""ADK agent definitions — orchestrator, sub-agents, and MemoryAgent runner."""

import logging
import mimetypes
from pathlib import Path

from memento.config import OPENAI_API_BASE


def _extract_pdf_text(file_path: Path) -> str:
    """Extract plain text from a PDF using pypdf."""
    import pypdf
    reader = pypdf.PdfReader(str(file_path))
    pages = [page.extract_text() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from memento.db import (
    MEDIA_EXTENSIONS,
    TEXT_EXTENSIONS,
    clear_all_memories,
    delete_memory,
    get_memory_stats,
    read_all_memories,
    read_consolidation_history,
    read_unconsolidated_memories,
    store_consolidation,
    store_memory,
)

log = logging.getLogger("memory-agent")

# Populated by config.py
MODEL = None


def build_agents(datasource: str = "general"):
    """Build the orchestrator and sub-agents, with tools bound to datasource.

    Each sub-agent receives tool closures that forward calls to the correct
    datasource DB without exposing datasource as a visible ADK tool parameter.
    """

    def _store_memory(
        raw_text: str,
        summary: str,
        entities: list[str],
        topics: list[str],
        importance: float,
        source: str = "",
    ) -> dict:
        """Store a processed memory in the database.

        Args:
            raw_text: The original input text.
            summary: A concise 1-2 sentence summary.
            entities: Key people, companies, products, or concepts.
            topics: 2-4 topic tags.
            importance: Float 0.0 to 1.0 indicating importance.
            source: Where this memory came from (filename, URL, etc).

        Returns:
            dict with memory_id and confirmation.
        """
        return store_memory(datasource, raw_text, summary, entities, topics, importance, source)

    def _read_all_memories() -> dict:
        """Read all stored memories from the database, most recent first.

        Returns:
            dict with list of memories and count.
        """
        return read_all_memories(datasource)

    def _read_unconsolidated_memories() -> dict:
        """Read memories that haven't been consolidated yet.

        Returns:
            dict with list of unconsolidated memories and count.
        """
        return read_unconsolidated_memories(datasource)

    def _store_consolidation(
        source_ids: list[int],
        summary: str,
        insight: str,
        connections: list[dict],
    ) -> dict:
        """Store a consolidation result and mark source memories as consolidated.

        Args:
            source_ids: List of memory IDs that were consolidated.
            summary: A synthesized summary across all source memories.
            insight: One key pattern or insight discovered.
            connections: List of dicts with 'from_id', 'to_id', 'relationship'.

        Returns:
            dict with confirmation.
        """
        return store_consolidation(datasource, source_ids, summary, insight, connections)

    def _read_consolidation_history() -> dict:
        """Read past consolidation insights.

        Returns:
            dict with list of consolidation records.
        """
        return read_consolidation_history(datasource)

    def _get_memory_stats() -> dict:
        """Get current memory statistics.

        Returns:
            dict with counts of memories, consolidations, etc.
        """
        return get_memory_stats(datasource)

    ingest_agent = Agent(
        name="ingest_agent",
        model=MODEL,
        description="Processes raw text or media into structured memory. Call this when new information arrives.",
        instruction=(
            "You are a Memory Ingest Agent. You handle ALL types of input — text, images,\n"
            "audio, video, and PDFs. For any input you receive:\n"
            "1. Thoroughly describe what the content contains\n"
            "2. Create a concise 1-2 sentence summary\n"
            "3. Extract key entities (people, companies, products, concepts, objects, locations)\n"
            "4. Assign 2-4 topic tags\n"
            "5. Rate importance from 0.0 to 1.0\n"
            "6. Call store_memory with all extracted information\n\n"
            "For images: describe the scene, objects, text, people, and any visual details.\n"
            "For audio/video: describe the spoken content, sounds, scenes, and key moments.\n"
            "For PDFs: extract and summarize the document content.\n\n"
            "Use the full description as raw_text in store_memory so the context is preserved.\n"
            "Always call store_memory. Be concise and accurate.\n"
            "After storing, confirm what was stored in one sentence."
        ),
        tools=[_store_memory],
    )

    consolidate_agent = Agent(
        name="consolidate_agent",
        model=MODEL,
        description="Merges related memories and finds patterns. Call this periodically.",
        instruction=(
            "You are a Memory Consolidation Agent. You:\n"
            "1. Call read_unconsolidated_memories to see what needs processing\n"
            "2. If fewer than 2 memories, say nothing to consolidate\n"
            "3. Find connections and patterns across the memories\n"
            "4. Create a synthesized summary and one key insight\n"
            "5. Call store_consolidation with source_ids, summary, insight, and connections\n\n"
            "Connections: list of dicts with 'from_id', 'to_id', 'relationship' keys.\n"
            "Think deeply about cross-cutting patterns."
        ),
        tools=[_read_unconsolidated_memories, _store_consolidation],
    )

    query_agent = Agent(
        name="query_agent",
        model=MODEL,
        description="Answers questions using stored memories.",
        instruction=(
            "You are a Memory Query Agent. When asked a question:\n"
            "1. Call read_all_memories to access the memory store\n"
            "2. Call read_consolidation_history for higher-level insights\n"
            "3. Synthesize an answer based ONLY on stored memories\n"
            "4. Reference memory IDs: [Memory 1], [Memory 2], etc.\n"
            "5. If no relevant memories exist, say so honestly\n\n"
            "Be thorough but concise. Always cite sources."
        ),
        tools=[_read_all_memories, _read_consolidation_history],
    )

    orchestrator = Agent(
        name="memory_orchestrator",
        model=MODEL,
        description="Routes memory operations to specialist agents.",
        instruction=(
            "You are the Memory Orchestrator for an always-on memory system.\n"
            "Route requests to the right sub-agent:\n"
            "- New information -> ingest_agent\n"
            "- Consolidation request -> consolidate_agent\n"
            "- Questions -> query_agent\n"
            "- Status check -> call get_memory_stats and report\n\n"
            "After the sub-agent completes, give a brief summary."
        ),
        sub_agents=[ingest_agent, consolidate_agent, query_agent],
        tools=[_get_memory_stats],
    )

    return orchestrator


class MemoryAgent:
    """Runs ADK agents against a datasource-specific memory database.

    Agent instances are cached per datasource to avoid rebuilding on every
    request while keeping tool closures bound to the correct datasource.
    """

    def __init__(self):
        self._agent_cache: dict[str, tuple[Agent, Runner, InMemorySessionService]] = {}

    def _get_or_build(self, datasource: str) -> tuple[Agent, Runner, InMemorySessionService]:
        if datasource not in self._agent_cache:
            agent = build_agents(datasource)
            session_service = InMemorySessionService()
            runner = Runner(
                agent=agent,
                app_name="memory_layer",
                session_service=session_service,
            )
            self._agent_cache[datasource] = (agent, runner, session_service)
        return self._agent_cache[datasource]

    async def run(self, message: str, datasource: str = "general") -> str:
        _, runner, session_service = self._get_or_build(datasource)
        session = await session_service.create_session(
            app_name="memory_layer", user_id="agent",
        )
        content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        return await self._execute(runner, session, content)

    async def run_multimodal(
        self,
        text: str,
        file_bytes: bytes,
        mime_type: str,
        datasource: str = "general",
    ) -> str:
        """Send a multimodal message with both text and a media file."""
        _, runner, session_service = self._get_or_build(datasource)
        session = await session_service.create_session(
            app_name="memory_layer", user_id="agent",
        )
        parts = [
            types.Part.from_text(text=text),
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        ]
        content = types.Content(role="user", parts=parts)
        return await self._execute(runner, session, content)

    async def _execute(self, runner: Runner, session, content: types.Content) -> str:
        response = ""
        async for event in runner.run_async(
            user_id="agent", session_id=session.id, new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response += part.text
        return response

    async def ingest(self, text: str, source: str = "", datasource: str = "general") -> str:
        msg = (
            f"Remember this information (source: {source}):\n\n{text}"
            if source
            else f"Remember this information:\n\n{text}"
        )
        return await self.run(msg, datasource=datasource)

    async def ingest_file(self, file_path: Path, datasource: str = "general") -> str:
        """Ingest a media file (image, audio, video, PDF).

        When using a local OpenAI-compatible model, PDFs are ingested via text
        extraction (pypdf). Other binary formats are not supported in that mode
        and will be skipped. When using Gemini the file is sent inline as bytes.
        """
        suffix = file_path.suffix.lower()
        mime_type = MEDIA_EXTENSIONS.get(suffix)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or "application/octet-stream"

        if OPENAI_API_BASE:
            if suffix == ".pdf":
                log.info(f"Ingesting PDF as text (local model): {file_path.name}")
                text = _extract_pdf_text(file_path)
                if not text.strip():
                    log.warning(f"No extractable text in {file_path.name}, skipping")
                    return f"Skipped: no extractable text in {file_path.name}"
                return await self.ingest(text, source=file_path.name, datasource=datasource)
            else:
                log.warning(
                    f"Skipping {file_path.name}: local model mode does not support "
                    f"{mime_type.split('/')[0]} files"
                )
                return f"Skipped: local model mode does not support {mime_type.split('/')[0]} files"

        file_bytes = file_path.read_bytes()
        size_mb = len(file_bytes) / (1024 * 1024)

        if size_mb > 20:
            log.warning(f"Skipping {file_path.name} ({size_mb:.1f}MB) — exceeds 20MB limit")
            return f"Skipped: file too large ({size_mb:.1f}MB)"

        prompt = (
            f"Remember this file (source: {file_path.name}, type: {mime_type}).\n\n"
            f"Thoroughly analyze the content of this {mime_type.split('/')[0]} file and "
            f"extract all meaningful information for memory storage."
        )
        log.info(f"Ingesting {mime_type.split('/')[0]}: {file_path.name} ({size_mb:.1f}MB)")
        return await self.run_multimodal(prompt, file_bytes, mime_type, datasource=datasource)

    async def consolidate(self, datasource: str = "general") -> str:
        return await self.run(
            "Consolidate unconsolidated memories. Find connections and patterns.",
            datasource=datasource,
        )

    async def query(self, question: str, datasource: str = "general") -> str:
        return await self.run(f"Based on my memories, answer: {question}", datasource=datasource)

    async def status(self, datasource: str = "general") -> str:
        return await self.run("Give me a status report on my memory system.", datasource=datasource)
