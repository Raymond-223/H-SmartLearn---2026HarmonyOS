/**
 * Wire types for the adaptive (information-gain) diagnosis and the
 * Beta-Bernoulli learner model.
 *
 * Field names are snake_case on purpose: these mirror the FastAPI response
 * bodies verbatim (`app/schemas/diagnosis.py`, `app/schemas/learner_model.py`),
 * so a payload can be cast straight from JSON without a translation layer.
 * Anything the backend declares Optional is declared optional here too.
 */

/** One selectable answer of a single-choice item. */
export interface DiagnosisOption {
  key: string;
  text: string;
}

/**
 * The next item to ask, together with the evidence that justified asking it.
 *
 * The scoring fields are the objective the server maximised —
 * `information_gain + 0.35 * coverage_gain - 0.15 * time_cost - 0.25 * fatigue`
 * — and are carried to the client so the UI can explain *why* this question,
 * not just show it. The correct answer is deliberately absent while the item
 * is open; it only arrives with DiagnosisAnswerResponse.
 */
export interface DiagnosisItem {
  item_id: string;
  skill_id?: string;
  concept_ids: string[];
  question_type: string;
  difficulty: number;
  stem: string;
  options: DiagnosisOption[];
  estimated_time_sec: number;
  importance: number;
  question_index: number;
  information_gain: number;
  coverage_gain: number;
  time_cost: number;
  fatigue: number;
  selection_score: number;
}

/** How one answer moved one concept posterior. */
export interface DiagnosisConceptDelta {
  concept_id: string;
  name?: string;
  mastery_before: number;
  mastery_after: number;
  uncertainty_before: number;
  uncertainty_after: number;
}

/** Posterior over a single concept. `uncertainty` is normalised to [0, 1]. */
export interface ConceptMastery {
  concept_id: string;
  skill_id?: string;
  name?: string;
  alpha: number;
  beta: number;
  mastery_probability: number;
  uncertainty: number;
  attempt_count: number;
  correct_count: number;
  last_response_time?: number;
  last_difficulty?: number;
}

/** Concept posteriors rolled up to one skill. */
export interface SkillMastery {
  skill_id: string;
  name?: string;
  mastery_probability: number;
  uncertainty: number;
  concept_count: number;
  tested_concept_count: number;
  attempt_count: number;
  weak_concept_ids: string[];
  concepts: ConceptMastery[];
}

/** Whole-domain ability picture — the planner's primary input. */
export interface AbilityProfile {
  learner_id: string;
  domain_id: string;
  overall_mastery: number;
  overall_uncertainty: number;
  recommended_level: string;
  concept_coverage: number;
  tested_concept_count: number;
  total_concept_count: number;
  total_attempts: number;
  skill_states: SkillMastery[];
  weak_concepts: ConceptMastery[];
  uncertain_concepts: ConceptMastery[];
  strong_concepts: ConceptMastery[];
  updated_at?: string;
}

/** Running fatigue estimate; feeds the penalty term of the selection score. */
export interface DiagnosisFatigueState {
  consecutive_hard?: number;
  elapsed_seconds?: number;
  level?: number;
}

/** One graded item in the terminal report. */
export interface DiagnosisItemResult {
  item_id: string;
  skill_id?: string;
  concept_ids: string[];
  difficulty: number;
  stem: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
  response_time_sec?: number;
  error_tags: string[];
}

/** Live state of a diagnosis session (GET /diagnosis/{session_id}). */
export interface DiagnosisSession {
  session_id: string;
  learner_id: string;
  domain_id: string;
  target_skill_id?: string;
  workflow_id?: string;
  status: string;
  question_count: number;
  answered_item_ids: string[];
  tested_concept_ids: string[];
  fatigue_state: DiagnosisFatigueState;
  started_at?: string;
  finished_at?: string;
}

/**
 * Terminal report for one adaptive run.
 *
 * `stop_reason` is one of `max_questions_reached`, `posterior_confident`,
 * `information_gain_exhausted`, `item_bank_exhausted`, `time_budget_exhausted`.
 */
export interface DiagnosisResult {
  session_id: string;
  learner_id: string;
  domain_id: string;
  target_skill_id?: string;
  status: string;
  question_count: number;
  correct_count: number;
  accuracy: number;
  total_time_sec: number;
  stop_reason?: string;
  overall_mastery: number;
  overall_uncertainty: number;
  recommended_level: string;
  tested_concept_ids: string[];
  weak_concepts: ConceptMastery[];
  uncertain_concepts: ConceptMastery[];
  skill_states: SkillMastery[];
  ability_profile?: AbilityProfile;
  misconceptions: string[];
  knowledge_gaps: string[];
  item_results: DiagnosisItemResult[];
  summary: string;
}

/**
 * Start an adaptive session.
 *
 * Pass `workflow_id` when a workflow is parked at DIAGNOSIS_QUESTIONING: the
 * backend resumes that workflow the moment this session stops, so the client
 * does not have to poke it afterwards.
 */
export interface DiagnosisStartRequest {
  learner_id: string;
  domain_id: string;
  target_skill_id?: string;
  workflow_id?: string;
}

export interface DiagnosisStartResponse {
  session_id: string;
  learner_id: string;
  domain_id: string;
  target_skill_id?: string;
  workflow_id?: string;
  status: string;
  question_count: number;
  next_item?: DiagnosisItem;
  started_at?: string;
}

export interface DiagnosisAnswerRequest {
  item_id: string;
  answer: string;
  response_time_sec?: number;
}

/**
 * Grading, the posterior delta, and the next item in one round trip.
 *
 * When `finished` is true there is no `next_item` and `result` is populated;
 * answering again is rejected with HTTP 409.
 */
export interface DiagnosisAnswerResponse {
  session_id: string;
  item_id: string;
  is_correct: boolean;
  correct_answer: string;
  explanation: string;
  error_tags: string[];
  misconception_tags: string[];
  concept_deltas: DiagnosisConceptDelta[];
  question_count: number;
  finished: boolean;
  stop_reason?: string;
  next_item?: DiagnosisItem;
  result?: DiagnosisResult;
}

/** GET /diagnosis/{session_id}/next — idempotent; re-asks the open item. */
export interface DiagnosisNextResponse {
  session_id: string;
  finished: boolean;
  stop_reason?: string;
  question_count: number;
  next_item?: DiagnosisItem;
}

/** GET /learners/{id}/mastery */
export interface LearnerMasteryResponse {
  learner_id: string;
  domain_id: string;
  overall_mastery: number;
  overall_uncertainty: number;
  skill_states: SkillMastery[];
  concept_states: ConceptMastery[];
}

/** GET /learners/{id}/weak-concepts — weakest first, attempted concepts only. */
export interface WeakConceptResponse {
  learner_id: string;
  domain_id: string;
  threshold: number;
  weak_concepts: ConceptMastery[];
}

/** Optional filters for GET /learners/{id}/mastery. */
export interface LearnerMasteryQuery {
  domainId?: string;
  skillId?: string;
  testedOnly?: boolean;
}

/** Optional filters for GET /learners/{id}/weak-concepts. */
export interface WeakConceptQuery {
  domainId?: string;
  skillId?: string;
  threshold?: number;
  limit?: number;
}
