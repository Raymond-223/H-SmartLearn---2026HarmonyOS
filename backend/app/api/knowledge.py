"""Public read-only knowledge/domain-package endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.skill_graph import SkillNode, SkillEdge
from app.services.domain_package_service import (
    load_concept_edges,
    load_concept_nodes,
    load_domain_manifest,
    load_knowledge_data_manifest,
    load_practice_tasks,
    load_validator_registry,
)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("/graph")
async def get_skill_graph(
    domain_id: str = Query(default="ros2_robotics"),
    db: AsyncSession = Depends(get_db),
):
    nodes = list((await db.execute(
        select(SkillNode)
        .where(SkillNode.domain_id == domain_id)
        .order_by(SkillNode.difficulty, SkillNode.id)
    )).scalars().all())
    if not nodes:
        raise HTTPException(status_code=404, detail=f"domain not found: {domain_id}")
    node_ids = [node.id for node in nodes]
    edges = list((await db.execute(
        select(SkillEdge)
        .where(
            SkillEdge.from_skill_id.in_(node_ids),
            SkillEdge.to_skill_id.in_(node_ids),
        )
        .order_by(SkillEdge.from_skill_id, SkillEdge.to_skill_id)
    )).scalars().all())
    return {
        "domain_id": domain_id,
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "difficulty": node.difficulty,
                "estimated_minutes": node.estimated_minutes or 60,
                "objectives": node.objectives_json or [],
                "criteria": node.criteria_json or [],
            }
            for node in nodes
        ],
        "edges": [
            {
                "from_skill_id": edge.from_skill_id,
                "to_skill_id": edge.to_skill_id,
                "relation_type": edge.relation_type,
            }
            for edge in edges
        ],
    }


@router.get("/concept-graph")
async def get_concept_graph(domain_id: str = Query(default="ros2_robotics")):
    """Expose KB2 concept nodes/edges for coverage and learning-path UI."""
    try:
        nodes = load_concept_nodes(domain_id)
        edges = load_concept_edges(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"domain not found: {domain_id}") from exc
    return {"domain_id": domain_id, "nodes": nodes, "edges": edges}


@router.get("/practice-tasks")
async def get_practice_tasks(
    domain_id: str = Query(default="ros2_robotics"),
    skill_id: str | None = Query(default=None),
):
    try:
        tasks = load_practice_tasks(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"domain not found: {domain_id}") from exc
    if skill_id:
        tasks = [task for task in tasks if str(task.get("skill_id")) == skill_id]
    return {"domain_id": domain_id, "skill_id": skill_id, "tasks": tasks}


@router.get("/validators")
async def get_validator_specs(domain_id: str = Query(default="ros2_robotics")):
    """Return validator specifications. implementation_status remains explicit."""
    try:
        validators = load_validator_registry(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"domain not found: {domain_id}") from exc
    return {"domain_id": domain_id, "validators": validators}


@router.get("/dataset")
async def get_dataset_metadata(domain_id: str = Query(default="ros2_robotics")):
    """Return the public domain manifest and KB audit manifest, not review secrets."""
    try:
        manifest = load_domain_manifest(domain_id)
        data_manifest = load_knowledge_data_manifest(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"domain not found: {domain_id}") from exc
    return {
        "domain_id": domain_id,
        "manifest": manifest,
        "knowledge_data_manifest": data_manifest,
    }
