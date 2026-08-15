/**
 * ApiService: HarmonyOS client gateway for the single backend API.
 * Business pages never call model providers directly.
 */
import http from '@ohos.net.http';
import { LogUtil } from '../utils/LogUtil';
import { DataStore } from '../business/DataStore';
import { WorkflowStatus } from './WorkflowStatus';
import {
  AbilityProfile,
  ConceptMastery,
  DiagnosisAnswerRequest,
  DiagnosisAnswerResponse,
  DiagnosisConceptDelta,
  DiagnosisFatigueState,
  DiagnosisItem,
  DiagnosisItemResult,
  DiagnosisNextResponse,
  DiagnosisOption,
  DiagnosisResult,
  DiagnosisSession,
  DiagnosisStartRequest,
  DiagnosisStartResponse,
  LearnerMasteryQuery,
  LearnerMasteryResponse,
  SkillMastery,
  WeakConceptQuery,
  WeakConceptResponse,
} from './DiagnosisTypes';

// Diagnosis payload shapes live in DiagnosisTypes.ets, but callers have always
// imported every wire type from ApiService. Re-export so pages need one import.
export {
  AbilityProfile,
  ConceptMastery,
  DiagnosisAnswerRequest,
  DiagnosisAnswerResponse,
  DiagnosisConceptDelta,
  DiagnosisFatigueState,
  DiagnosisItem,
  DiagnosisItemResult,
  DiagnosisNextResponse,
  DiagnosisOption,
  DiagnosisResult,
  DiagnosisSession,
  DiagnosisStartRequest,
  DiagnosisStartResponse,
  LearnerMasteryQuery,
  LearnerMasteryResponse,
  SkillMastery,
  WeakConceptQuery,
  WeakConceptResponse,
};

const TAG: string = 'ApiService';
const DEFAULT_BASE_URL: string = 'http://10.0.2.2:8000';

export interface LearnerPreferences {
  explanation_style: string;
  resource_priority: string;
}

export interface LearnerCreateRequest {
  education?: string;
  major?: string;
  target_role?: string;
  weekly_hours?: number;
  preferences?: LearnerPreferences;
}

export interface LearnerCreateResponse {
  learner_id: string;
}

export interface LearnerDetailResponse {
  learner_id: string;
  education?: string;
  major?: string;
  target_role?: string;
  weekly_hours?: number;
  preferences: LearnerPreferences;
}

export interface AssessmentCreateRequest {
  learner_id: string;
  domain_id: string;
  target_goal?: string;
}

export interface QuizOptionDto {
  key: string;
  text: string;
}

export interface AssessmentQuizItem {
  item_id: string;
  skill_id: string;
  type: string;
  difficulty: number;
  stem: string;
  options: QuizOptionDto[];
  correct_answer?: string;
  explanation?: string;
  evidence_ids?: string[];
  misconception_tags?: string[];
  estimated_seconds?: number;
}

export interface AssessmentCreateResponse {
  assessment_id: string;
  items: AssessmentQuizItem[];
}

export interface AnswerItem {
  item_id: string;
  answer: string;
  duration_seconds?: number;
}

export interface AssessmentSubmitRequest {
  answers: AnswerItem[];
}

export interface AssessmentItemResult {
  item_id: string;
  skill_id: string;
  stem: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
  error_tags?: string[];
}

export interface AssessmentSubmitResponse {
  status: string;
  diagnosis_id: string;
  mastery?: Object;
  knowledge_gaps?: string[];
  recommended_level?: string;
  item_results?: AssessmentItemResult[];
}

export interface WorkflowCreateRequest {
  learner_id: string;
  domain_id: string;
  assessment_id?: string;
  target_goal?: string;
  target_skill_id?: string;
  requested_difficulty?: string;
  version_filter?: string;
}

export interface WorkflowCreateResponse {
  workflow_id: string;
  status: WorkflowStatus;
}

export interface WorkflowStatusResponse {
  workflow_id: string;
  status: WorkflowStatus;
  current_agent?: string;
  progress: number;
  resource_id?: string;
  error_message?: string;
}

export interface AgentTraceItem {
  agent: string;
  status: string;
  summary?: string;
  confidence?: number;
}

export interface WorkflowTraceResponse {
  runs: AgentTraceItem[];
}

export interface WorkflowSnapshotResponse {
  status: WorkflowStatusResponse;
  trace: WorkflowTraceResponse;
}

export interface LectureSection {
  heading: string;
  content: string;
  citations?: string[];
}

export interface LectureResource {
  title: string;
  sections: LectureSection[];
  estimated_read_time_minutes?: number;
}

export interface PracticeStep {
  order: number;
  title: string;
  command: string;
  expected_result: string;
  skill_id?: string;
  evidence_ids?: string[];
  validator_ids?: string[];
  risk_level?: string;
  ros_version?: string;
}

export interface PracticeGuideResource {
  title: string;
  steps: PracticeStep[];
  prerequisites?: string[];
  safety_notes?: string[];
  common_errors?: string[];
  rollback?: string[];
  expected_output?: string;
  evidence_ids?: string[];
  validator_ids?: string[];
  risk_level?: string;
  execution_verification_status?: string;
  time_estimate_minutes?: number;
}

export interface GradedTestOption {
  key: string;
  text: string;
}

export interface GradedTestItem {
  id: string;
  skill_id?: string;
  difficulty: string;
  stem: string;
  options: GradedTestOption[];
  correct_answer?: string;
  explanation?: string;
}

export interface GradedTestResource {
  title: string;
  items: GradedTestItem[];
}

export interface ResourceTestAnswer {
  item_id: string;
  answer: string;
}

export interface ResourceTestItemResult {
  item_id: string;
  skill_id: string;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
}

export interface ResourceTestResult {
  score: number;
  correct_count: number;
  total_count: number;
  error_tags: string[];
  item_results: ResourceTestItemResult[];
}

export interface CitationItem {
  evidence_id: string;
  title: string;
  source_url: string;
  source_type?: string;
  verification_status?: string;
}

export interface ReviewScores {
  factuality?: number;
  evidence_coverage?: number;
  difficulty_match?: number;
  actionability?: number;
  traceability?: number;
}

export interface RiskRouteData {
  route?: string;
  pre_risk?: number;
  domain_risk?: number;
  uncertainty?: number;
  retrieval_weakness?: number;
  novelty?: number;
  model_call_budget?: number;
  reasons?: string[];
}

export interface ProofGraphSummary {
  claim_count?: number;
  high_risk_claim_count?: number;
  supported_claim_count?: number;
  validated_claim_count?: number;
  rejected_claim_count?: number;
  needs_confirmation_count?: number;
  high_risk_traceability?: number;
}

export interface ResourceMetadata {
  risk_route?: RiskRouteData;
  proof_graph_summary?: ProofGraphSummary;
  model_version?: string;
  provider?: string;
  prompt_version?: string;
}

export interface ReviewData {
  decision?: string;
  scores?: ReviewScores;
  issues?: Object[];
}

export interface ResourceResponse {
  resource_id: string;
  workflow_id?: string;
  difficulty: string;
  target_skill?: string;
  lecture?: LectureResource;
  practice_guide?: PracticeGuideResource;
  graded_test?: GradedTestResource;
  citations: CitationItem[];
  review?: ReviewData;
  metadata?: ResourceMetadata;
  feedback_recorded?: boolean;
  feedback_decision?: string;
  feedback_reason?: string;
  next_workflow_id?: string;
}

export interface PracticeStepResult {
  order: number;
  success: boolean;
}

export interface FeedbackRequest {
  correct_rate?: number;
  practice_score?: number;
  practice_results: PracticeStepResult[];
  subjective_difficulty?: string;
  error_tags?: string[];
}

export interface FeedbackResponse {
  decision: string;
  reason?: string;
  next_workflow_id?: string;
}

export interface SkillMasteryData {
  skill_id: string;
  name: string;
  score: number;
  confidence: number;
  difficulty?: number;
}

export interface LearningPathData {
  order: number;
  skill_id: string;
  name: string;
  estimated_minutes?: number;
  mastery?: number;
}

export interface DifficultyCurveData {
  label: string;
  score: number;
  skill_count?: number;
}

export interface ProgressHistoryData {
  timestamp: string;
  event_type: string;
  label: string;
  score: number;
  skill_id?: string;
}

export interface LearnerReportData {
  learner_id: string;
  overall_mastery: number;
  domain: string;
  skill_mastery: SkillMasteryData[];
  knowledge_gaps: string[];
  strengths: string[];
  difficulty_curve: DifficultyCurveData[];
  learning_path: LearningPathData[];
  progress_history: ProgressHistoryData[];
  recommended_resources: string[];
}

export interface SkillGraphNodeDto {
  id: string;
  name: string;
  difficulty: number;
  estimated_minutes: number;
  objectives: string[];
  criteria: string[];
}

export interface SkillGraphEdgeDto {
  from_skill_id?: string;
  to_skill_id?: string;
  relation_type?: string;
  from?: string;
  to?: string;
  relation?: string;
}

export interface SkillGraphResponse {
  domain_id: string;
  nodes: SkillGraphNodeDto[];
  edges: SkillGraphEdgeDto[];
}

export interface ConceptGraphNodeDto {
  id: string;
  name: string;
  skill_id: string;
  difficulty: number;
  risk_level: string;
  importance: string;
  prerequisite_concept_ids?: string[];
  tags?: string[];
}

export interface ConceptGraphEdgeDto {
  from: string;
  to: string;
  relation: string;
}

export interface ConceptGraphResponse {
  domain_id: string;
  nodes: ConceptGraphNodeDto[];
  edges: ConceptGraphEdgeDto[];
}

export interface PracticeTaskResponse {
  domain_id: string;
  skill_id?: string;
  tasks: Object[];
}

export interface ValidatorSpecsResponse {
  domain_id: string;
  validators: Object[];
}

export interface KnowledgeDatasetResponse {
  domain_id: string;
  manifest: Object;
  knowledge_data_manifest: Object;
}

export interface BenchmarkMetrics {
  hallucination_rate: number;
  difficulty_match_accuracy: number;
  core_knowledge_coverage: number;
  review_pass_rate?: number;
}

export interface BenchmarkChecks {
  hallucination: boolean;
  difficulty_match: boolean;
  core_coverage: boolean;
  review_pass?: boolean;
  case_count: boolean;
  profile_count: boolean;
}

export interface BenchmarkSummaryResponse {
  suite: string;
  status: string;
  case_count: number;
  profile_count: number;
  profiles: string[];
  domains: string[];
  metrics: BenchmarkMetrics;
  checks: BenchmarkChecks;
  disclaimer: string;
}

interface ApiErrorPayload {
  detail?: string;
  raw?: string;
}

class ApiHttpError extends Error {
  statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

interface JsonRequestHeaders {
  'Content-Type': string;
  Accept: string;
}

class JsonRequestOptions {
  method: http.RequestMethod;
  header: JsonRequestHeaders;
  connectTimeout: number = 10000;
  readTimeout: number = 45000;
  extraData?: string;

  constructor(method: http.RequestMethod, body?: string) {
    this.method = method;
    this.header = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };
    if (body !== undefined) {
      this.extraData = body;
    }
  }
}

export interface ApiRuntimeState {
  baseUrl: string;
  lastError: string;
  lastChangedAt: number;
}

/** Single-runtime API client. All application traffic goes to the configured backend. */
export class ApiService {
  private static configuredBaseUrl: string = DEFAULT_BASE_URL;
  private static configurationLoaded: boolean = false;
  private static runtimeState: ApiRuntimeState = {
    baseUrl: DEFAULT_BASE_URL,
    lastError: '',
    lastChangedAt: Date.now(),
  };

  private baseUrl: string;
  private explicitBaseUrl: boolean;

  constructor(baseUrl?: string) {
    this.explicitBaseUrl = baseUrl !== undefined && baseUrl.trim().length > 0;
    this.baseUrl = this.explicitBaseUrl ? ApiService.normalizeBaseUrl(baseUrl || DEFAULT_BASE_URL) : ApiService.configuredBaseUrl;
  }

  static getRuntimeState(): ApiRuntimeState {
    return {
      baseUrl: ApiService.runtimeState.baseUrl,
      lastError: ApiService.runtimeState.lastError,
      lastChangedAt: ApiService.runtimeState.lastChangedAt,
    };
  }

  static async configure(baseUrl: string): Promise<void> {
    const normalized: string = ApiService.normalizeBaseUrl(baseUrl);
    ApiService.configuredBaseUrl = normalized;
    ApiService.configurationLoaded = true;
    ApiService.runtimeState = {
      baseUrl: normalized,
      lastError: '', lastChangedAt: Date.now(),
    };
    await DataStore.saveApiBaseUrl(normalized);
  }

  static async resetConfiguration(): Promise<void> {
    await ApiService.configure(DEFAULT_BASE_URL);
  }

  static getDefaultBaseUrl(): string {
    return DEFAULT_BASE_URL;
  }

  static async getConfiguredBaseUrl(): Promise<string> {
    await ApiService.ensureConfiguration();
    return ApiService.configuredBaseUrl;
  }

  private static normalizeBaseUrl(value: string): string {
    const trimmed: string = value.trim();
    const candidate: string = trimmed || DEFAULT_BASE_URL;
    return candidate.endsWith('/') ? candidate.substring(0, candidate.length - 1) : candidate;
  }

  private static async ensureConfiguration(): Promise<void> {
    if (ApiService.configurationLoaded) return;
    try {
      const storedUrl: string | null = await DataStore.getApiBaseUrl();
      ApiService.configuredBaseUrl = ApiService.normalizeBaseUrl(storedUrl || DEFAULT_BASE_URL);
    } catch (error) {
      LogUtil.warn(TAG, `Unable to read stored API configuration: ${(error as Error).message}`);
      ApiService.configuredBaseUrl = DEFAULT_BASE_URL;
    }
    ApiService.runtimeState = {
      baseUrl: ApiService.configuredBaseUrl,
      lastError: '', lastChangedAt: Date.now(),
    };
    ApiService.configurationLoaded = true;
  }

  async createLearner(data: LearnerCreateRequest): Promise<LearnerCreateResponse> {
    return await this.post('/api/v1/learners', data) as LearnerCreateResponse;
  }

  async getLearner(learnerId: string): Promise<LearnerDetailResponse> {
    return await this.get(`/api/v1/learners/${learnerId}`) as LearnerDetailResponse;
  }

  async updateLearner(learnerId: string, data: LearnerCreateRequest): Promise<LearnerDetailResponse> {
    return await this.put(`/api/v1/learners/${learnerId}`, data) as LearnerDetailResponse;
  }

  async getLearnerReport(learnerId: string, domainId?: string): Promise<LearnerReportData> {
    const query: string = domainId ? `?domain_id=${encodeURIComponent(domainId)}` : '';
    return await this.get(`/api/v1/learners/${learnerId}/report${query}`) as LearnerReportData;
  }

  /**
   * Open an adaptive diagnosis session and receive its first item.
   *
   * `workflow_id` is optional but load-bearing: a workflow started in adaptive
   * mode parks at DIAGNOSIS_QUESTIONING and only resumes once the session it
   * is linked to stops, so a session started without it leaves that workflow
   * waiting forever.
   */
  async startDiagnosis(data: DiagnosisStartRequest): Promise<DiagnosisStartResponse> {
    return await this.post('/api/v1/diagnosis/start', data) as DiagnosisStartResponse;
  }

  /**
   * Submit one answer. The response carries the grading, how the posterior
   * moved, and the next item — no separate fetch is needed while the session
   * is running. When `finished` is true, `result` is the terminal report.
   */
  async submitDiagnosisAnswer(sessionId: string, data: DiagnosisAnswerRequest): Promise<DiagnosisAnswerResponse> {
    return await this.post(`/api/v1/diagnosis/${sessionId}/answer`, data) as DiagnosisAnswerResponse;
  }

  /** Re-read the currently open item. Idempotent — safe after a UI restart. */
  async getNextDiagnosisItem(sessionId: string): Promise<DiagnosisNextResponse> {
    return await this.get(`/api/v1/diagnosis/${sessionId}/next`) as DiagnosisNextResponse;
  }

  async getDiagnosisResult(sessionId: string): Promise<DiagnosisResult> {
    return await this.get(`/api/v1/diagnosis/${sessionId}/result`) as DiagnosisResult;
  }

  async getDiagnosisSession(sessionId: string): Promise<DiagnosisSession> {
    return await this.get(`/api/v1/diagnosis/${sessionId}`) as DiagnosisSession;
  }

  async getLearnerMastery(learnerId: string, query?: LearnerMasteryQuery): Promise<LearnerMasteryResponse> {
    const params: string[] = [`domain_id=${encodeURIComponent(query?.domainId || 'ros2_robotics')}`];
    if (query?.skillId) {
      params.push(`skill_id=${encodeURIComponent(query.skillId)}`);
    }
    if (query?.testedOnly) {
      params.push('tested_only=true');
    }
    return await this.get(`/api/v1/learners/${learnerId}/mastery?${params.join('&')}`) as LearnerMasteryResponse;
  }

  async getLearnerWeakConcepts(learnerId: string, query?: WeakConceptQuery): Promise<WeakConceptResponse> {
    const params: string[] = [`domain_id=${encodeURIComponent(query?.domainId || 'ros2_robotics')}`];
    if (query?.skillId) {
      params.push(`skill_id=${encodeURIComponent(query.skillId)}`);
    }
    if (query?.threshold !== undefined) {
      params.push(`threshold=${query.threshold}`);
    }
    if (query?.limit !== undefined) {
      params.push(`limit=${query.limit}`);
    }
    return await this.get(`/api/v1/learners/${learnerId}/weak-concepts?${params.join('&')}`) as WeakConceptResponse;
  }

  async getLearnerAbilityProfile(learnerId: string, domainId: string = 'ros2_robotics'): Promise<AbilityProfile> {
    return await this.get(
      `/api/v1/learners/${learnerId}/ability-profile?domain_id=${encodeURIComponent(domainId)}`
    ) as AbilityProfile;
  }

  async createAssessment(data: AssessmentCreateRequest): Promise<AssessmentCreateResponse> {
    return await this.post('/api/v1/assessments', data) as AssessmentCreateResponse;
  }

  async submitAssessment(assessmentId: string, data: AssessmentSubmitRequest): Promise<AssessmentSubmitResponse> {
    return await this.post(`/api/v1/assessments/${assessmentId}/submit`, data) as AssessmentSubmitResponse;
  }

  async createWorkflow(data: WorkflowCreateRequest): Promise<WorkflowCreateResponse> {
    return await this.post('/api/v1/workflows', data) as WorkflowCreateResponse;
  }

  async getWorkflowStatus(workflowId: string): Promise<WorkflowStatusResponse> {
    return await this.get(`/api/v1/workflows/${workflowId}`) as WorkflowStatusResponse;
  }

  async getWorkflowTrace(workflowId: string): Promise<WorkflowTraceResponse> {
    return await this.get(`/api/v1/workflows/${workflowId}/trace`) as WorkflowTraceResponse;
  }

  async getWorkflowSnapshot(workflowId: string): Promise<WorkflowSnapshotResponse> {
    return await this.get(`/api/v1/workflows/${workflowId}/snapshot`) as WorkflowSnapshotResponse;
  }

  async retryWorkflow(workflowId: string): Promise<WorkflowCreateResponse> {
    return await this.post(`/api/v1/workflows/${workflowId}/retry`, JSON.parse('{}') as Object) as WorkflowCreateResponse;
  }

  async getResource(resourceId: string): Promise<ResourceResponse> {
    return await this.get(`/api/v1/resources/${resourceId}`) as ResourceResponse;
  }

  async submitResourceTest(resourceId: string, answers: ResourceTestAnswer[]): Promise<ResourceTestResult> {
    const payload: Object = JSON.parse('{"answers":' + JSON.stringify(answers) + '}') as Object;
    return await this.post(`/api/v1/resources/${resourceId}/test`, payload) as ResourceTestResult;
  }

  async submitFeedback(resourceId: string, data: FeedbackRequest): Promise<FeedbackResponse> {
    return await this.post(`/api/v1/resources/${resourceId}/feedback`, data) as FeedbackResponse;
  }

  async getSkillGraph(domainId: string): Promise<SkillGraphResponse> {
    return await this.get(`/api/v1/knowledge/graph?domain_id=${domainId}`) as SkillGraphResponse;
  }

  async getConceptGraph(domainId: string): Promise<ConceptGraphResponse> {
    return await this.get(`/api/v1/knowledge/concept-graph?domain_id=${encodeURIComponent(domainId)}`) as ConceptGraphResponse;
  }

  async getPracticeTasks(domainId: string, skillId?: string): Promise<PracticeTaskResponse> {
    const skillQuery: string = skillId ? `&skill_id=${encodeURIComponent(skillId)}` : '';
    return await this.get(`/api/v1/knowledge/practice-tasks?domain_id=${encodeURIComponent(domainId)}${skillQuery}`) as PracticeTaskResponse;
  }

  async getValidatorSpecs(domainId: string): Promise<ValidatorSpecsResponse> {
    return await this.get(`/api/v1/knowledge/validators?domain_id=${encodeURIComponent(domainId)}`) as ValidatorSpecsResponse;
  }

  async getKnowledgeDataset(domainId: string): Promise<KnowledgeDatasetResponse> {
    return await this.get(`/api/v1/knowledge/dataset?domain_id=${encodeURIComponent(domainId)}`) as KnowledgeDatasetResponse;
  }

  async getBenchmarkSummary(refresh: boolean = false): Promise<BenchmarkSummaryResponse> {
    const query: string = refresh ? '?refresh=true' : '';
    return await this.get('/api/v1/benchmarks/summary' + query) as BenchmarkSummaryResponse;
  }

  async healthCheck(): Promise<Object> {
    return await this.get('/health');
  }

  async healthCheckRemoteOnly(): Promise<Object> {
    return await this.get('/health');
  }

  private async get(path: string): Promise<Object> {
    return await this.request(path, http.RequestMethod.GET, undefined);
  }

  private async post(path: string, data: Object): Promise<Object> {
    return await this.request(path, http.RequestMethod.POST, JSON.stringify(data));
  }

  private async put(path: string, data: Object): Promise<Object> {
    return await this.request(path, http.RequestMethod.PUT, JSON.stringify(data));
  }

  private async request(path: string, method: http.RequestMethod, body?: string): Promise<Object> {
    return await this.requestRemote(path, method, body);
  }

  private async requestRemote(path: string, method: http.RequestMethod, body?: string): Promise<Object> {
    await ApiService.ensureConfiguration();
    if (!this.explicitBaseUrl) {
      this.baseUrl = ApiService.configuredBaseUrl;
    }

    const url: string = `${this.baseUrl}${path}`;
    LogUtil.info(TAG, `${method} ${url}`);
    const client: http.HttpRequest = http.createHttp();

    try {
      const options: JsonRequestOptions = new JsonRequestOptions(method, body);
      const response: http.HttpResponse = await client.request(url, options as http.HttpRequestOptions);
      const statusCode: number = response.responseCode;
      if (statusCode <= 0) {
        throw new Error('未收到有效 HTTP 响应');
      }
      const responsePayload: Object = ApiService.parseResponseResult(response.result);
      if (statusCode >= 200 && statusCode < 300) {
        ApiService.runtimeState = {
          baseUrl: this.baseUrl,
          lastError: '', lastChangedAt: Date.now(),
        };
        return responsePayload;
      }

      let message: string = `HTTP ${statusCode}`;
      const errorPayload: ApiErrorPayload = responsePayload as ApiErrorPayload;
      if (errorPayload.detail) {
        if (typeof errorPayload.detail === 'string') {
          message = errorPayload.detail;
        } else {
          message = JSON.stringify(errorPayload.detail);
        }
      } else {
        const responseText: string = ApiService.responseResultText(response.result);
        if (responseText) message = responseText;
      }
      throw new ApiHttpError(statusCode, message);
    } catch (error) {
      const err: Error = error as Error;
      if (error instanceof ApiHttpError) {
        ApiService.runtimeState = {
          baseUrl: this.baseUrl,
          lastError: err.message, lastChangedAt: Date.now(),
        };
        const apiError: ApiHttpError = error as ApiHttpError;
        LogUtil.warn(TAG, `${method} ${path} returned HTTP ${apiError.statusCode}: ${err.message}`);
        throw new ApiHttpError(apiError.statusCode, apiError.message);
      }
      const guidance: string = ApiService.networkGuidance(err.message, this.baseUrl);
      ApiService.runtimeState = {
        baseUrl: this.baseUrl,
        lastError: guidance, lastChangedAt: Date.now(),
      };
      LogUtil.error(TAG, `${method} ${path} failed: ${err.message}`);
      throw new Error(guidance);
    } finally {
      client.destroy();
    }
  }

  private static parseResponseResult(result: string | Object | ArrayBuffer): Object {
    if (typeof result === 'string') {
      return ApiService.parseTextPayload(result);
    }
    if (result instanceof ArrayBuffer) {
      return ApiService.parseTextPayload(ApiService.decodeUtf8(result));
    }
    return result as Object;
  }

  private static parseTextPayload(value: string): Object {
    const text: string = value.trim();
    if (text.length === 0) return JSON.parse('{}') as Object;
    try {
      return JSON.parse(text) as Object;
    } catch (error) {
      LogUtil.warn(TAG, `Non-JSON response received: ${(error as Error).message}`);
      return JSON.parse('{"raw":' + JSON.stringify(text) + '}') as Object;
    }
  }

  private static responseResultText(result: string | Object | ArrayBuffer): string {
    if (typeof result === 'string') return result;
    if (result instanceof ArrayBuffer) return ApiService.decodeUtf8(result);
    try {
      const serialized: string | undefined = JSON.stringify(result);
      return serialized || '';
    } catch (error) {
      LogUtil.warn(TAG, `Unable to serialize response payload: ${(error as Error).message}`);
      return '';
    }
  }

  private static decodeUtf8(buffer: ArrayBuffer): string {
    const bytes: Uint8Array = new Uint8Array(buffer);
    let encoded: string = '';
    for (let index: number = 0; index < bytes.length; index++) {
      let hex: string = bytes[index].toString(16);
      if (hex.length < 2) hex = '0' + hex;
      encoded += '%' + hex;
    }
    try {
      return decodeURIComponent(encoded);
    } catch (error) {
      LogUtil.warn(TAG, `UTF-8 decode fallback used: ${(error as Error).message}`);
      let fallback: string = '';
      for (let index: number = 0; index < bytes.length; index++) {
        fallback += String.fromCharCode(bytes[index]);
      }
      return fallback;
    }
  }

  private static networkGuidance(raw: string, baseUrl: string): string {
    return `后端服务暂时不可用。请在“API 设置”中检查 ${baseUrl} 并确认后端已启动。技术信息：${raw || 'Network Error'}`;
  }
}
