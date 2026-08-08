"""Export all SQLAlchemy models so metadata is complete at startup."""

from app.models.learner import LearnerProfile
from app.models.skill_graph import SkillNode, SkillEdge
from app.models.assessment import AssessmentSession, AssessmentItem, AssessmentAttempt, MasteryState
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.models.workflow import WorkflowSession, AgentRun
from app.models.resource import GeneratedResource, ResourceCitation, ReviewRecord
from app.models.feedback import FeedbackRecord
from app.models.learner_concept_mastery import LearnerConceptMastery
from app.models.diagnosis_session import DiagnosisSession, DiagnosisResponse

__all__ = [
    "LearnerProfile", "SkillNode", "SkillEdge", "AssessmentSession",
    "AssessmentItem", "AssessmentAttempt", "MasteryState", "KnowledgeDocument",
    "KnowledgeChunk", "WorkflowSession", "AgentRun",
    "GeneratedResource", "ResourceCitation", "ReviewRecord", "FeedbackRecord",
    "LearnerConceptMastery", "DiagnosisSession", "DiagnosisResponse",
]
