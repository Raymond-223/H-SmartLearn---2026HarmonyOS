"""Database engine, session factory, schema creation, and domain-package seeding."""

from sqlalchemy import event, inspect, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


_engine_kwargs: dict = {"echo": False}
_connect_args: dict = {}
if "sqlite" in settings.database_url:
    _connect_args["check_same_thread"] = False
else:
    _engine_kwargs.update(pool_size=5, max_overflow=10, pool_pre_ping=True)

engine = create_async_engine(settings.database_url, connect_args=_connect_args, **_engine_kwargs)

if "sqlite" in settings.database_url:
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _seed_domain_packages(session: AsyncSession) -> None:
    """Seed packaged domain data without inventing verification state.

    KB 2.x evidence uses stable evidence_id values and explicit verification
    states (trusted_source / verified / pending). These are preserved verbatim.
    The function remains backwards compatible with v1.x domain packages.
    """
    from app.models.skill_graph import SkillNode, SkillEdge
    from app.models.assessment import AssessmentItem
    from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
    from app.services.domain_package_service import (
        DOMAIN_ROOT,
        load_skill_nodes,
        load_skill_edges,
        load_assessment_bank,
        load_knowledge,
    )

    domain_ids = sorted(
        path.name for path in DOMAIN_ROOT.iterdir()
        if path.is_dir() and (path / "manifest.yaml").exists()
    )

    for domain_id in domain_ids:
        # Skill nodes: stable IDs, update descriptive fields when package evolves.
        for raw in load_skill_nodes(domain_id):
            node = await session.get(SkillNode, raw["id"])
            if node is None:
                node = SkillNode(id=raw["id"], domain_id=domain_id, name=raw["name"])
                session.add(node)
            node.domain_id = domain_id
            node.name = raw["name"]
            node.difficulty = raw.get("difficulty", 1)
            node.estimated_minutes = raw.get("estimated_minutes")
            node.objectives_json = raw.get("objectives", [])
            node.criteria_json = raw.get("criteria", [])
        await session.flush()

        for raw in load_skill_edges(domain_id):
            source = raw.get("from_skill_id") or raw.get("from")
            target = raw.get("to_skill_id") or raw.get("to")
            relation = raw.get("relation_type") or raw.get("relation", "prerequisite")
            existing_edge = (await session.execute(
                select(SkillEdge).where(
                    SkillEdge.from_skill_id == source,
                    SkillEdge.to_skill_id == target,
                    SkillEdge.relation_type == relation,
                ).limit(1)
            )).scalar_one_or_none()
            if existing_edge is None:
                session.add(SkillEdge(
                    from_skill_id=source,
                    to_skill_id=target,
                    relation_type=relation,
                ))

        # Assessment bank: keep richer KB2 metadata inside content_json so later
        # information-gain/BKT work can use it without another migration.
        for raw in load_assessment_bank(domain_id):
            item = await session.get(AssessmentItem, raw["id"])
            if item is None:
                item = AssessmentItem(id=raw["id"], skill_id=raw["skill_id"])
                session.add(item)
            item.skill_id = raw["skill_id"]
            item.question_type = raw.get("type", "single_choice")
            item.difficulty = raw.get("difficulty", 1)
            item.content_json = {
                "stem": raw["stem"],
                "options": raw.get("options", []),
                "explanation": raw.get("explanation", ""),
                "estimated_seconds": raw.get("estimated_seconds", raw.get("estimated_time_sec")),
                "concept_ids": raw.get("concept_ids", []),
                "evidence_ids": raw.get("evidence_ids", []),
                "misconception_tags": raw.get("misconception_tags", []),
            }
            item.correct_answer = raw["correct_answer"]
            item.error_tags = raw.get("error_tags", [])
            item.scoring_rules = raw.get("scoring_rules", {"correct": 1.0, "incorrect": 0.0})

        # Evidence: one stable DB chunk per EvidenceUnit. Package provenance is
        # rehydrated by RetrievalAgent using the stable evidence_id.
        for index, raw in enumerate(load_knowledge(domain_id), start=1):
            evidence_id = str(raw.get("evidence_id") or f"pkg_{domain_id}_{index:03d}")
            document_id = f"doc_{evidence_id}"
            verification_status = str(raw.get("verification_status", "pending"))
            source_locator = raw.get("source_locator") or {}

            doc = await session.get(KnowledgeDocument, document_id)
            if doc is None:
                doc = KnowledgeDocument(id=document_id, domain_id=domain_id, title=raw.get("title") or evidence_id)
                session.add(doc)
            doc.title = raw.get("title") or evidence_id
            doc.source_url = raw.get("source_url") or raw.get("source")
            doc.source_type = raw.get("source_type", "local")
            doc.domain_id = domain_id
            doc.version = raw.get("version")
            doc.verification_status = verification_status
            await session.flush()

            chunk = await session.get(KnowledgeChunk, evidence_id)
            if chunk is None:
                chunk = KnowledgeChunk(id=evidence_id, document_id=document_id, content=raw.get("claim") or raw.get("content", ""))
                session.add(chunk)
            chunk.document_id = document_id
            chunk.skill_id = raw.get("skill_id")
            chunk.content = raw.get("claim") or raw.get("content", "")
            chunk.section = source_locator.get("value") or raw.get("title")
            chunk.page_number = raw.get("page_number")
            chunk.version = raw.get("version")
            chunk.verification_status = verification_status

    await session.commit()


def _add_missing_sqlite_columns(connection) -> None:
    """Bring an existing SQLite file up to date with the current models.

    ``create_all`` adds new *tables* but never new *columns*, so a developer or
    test database created before a model gained a field keeps failing inserts
    until it is deleted by hand. SQLite's ``ADD COLUMN`` covers the only kind of
    change made here — nullable columns appended to a table. Anything else
    (drops, type changes, constraints) still needs a real migration, and other
    backends are left alone entirely.
    """
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present or not column.nullable:
                continue
            column_type = column.type.compile(connection.dialect)
            connection.exec_driver_sql(
                f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'
            )


async def init_db() -> None:
    import app.models  # noqa: F401 - registers all metadata
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.database_url:
            await connection.run_sync(_add_missing_sqlite_columns)
    async with async_session_factory() as session:
        await _seed_domain_packages(session)
