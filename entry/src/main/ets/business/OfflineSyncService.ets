/** Replays ArkData offline actions after connectivity returns. */
import { LearningCacheDatabase, OfflineActionRecord } from './LearningCacheDatabase';
import { ApiService, PracticeStep, PracticeStepResult } from '../service/ApiService';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'OfflineSyncService';

interface OfflineFeedbackPayload {
  resource_id: string;
  correct_rate: number;
  practice_score: number;
  subjective_difficulty: string;
  error_tags: string;
  practice_results?: PracticeStepResult[];
  timestamp: number;
}

export interface SyncResult {
  submitted: number;
  remaining: number;
}

export class OfflineSyncService {
  static async flushFeedback(): Promise<SyncResult> {
    const actions: OfflineActionRecord[] = await LearningCacheDatabase.listPendingActions('feedback');
    const api = new ApiService();
    let submitted: number = 0;
    for (const action of actions) {
      try {
        const payload = JSON.parse(action.payload) as OfflineFeedbackPayload;
        const tags: string[] = payload.error_tags
          .split(',')
          .map((item: string): string => item.trim())
          .filter((item: string): boolean => item.length > 0);
        let practiceResults: PracticeStepResult[] = payload.practice_results || [];
        if (practiceResults.length === 0) {
          const resource = await api.getResource(payload.resource_id);
          const steps = resource.practice_guide?.steps || [];
          const successCount: number = Math.round(Math.max(0, Math.min(1, payload.practice_score)) * steps.length);
          practiceResults = steps.map((step: PracticeStep, index: number): PracticeStepResult => {
            return { order: step.order, success: index < successCount };
          });
        }
        await api.submitFeedback(payload.resource_id, {
          correct_rate: payload.correct_rate,
          practice_score: payload.practice_score,
          practice_results: practiceResults,
          subjective_difficulty: payload.subjective_difficulty,
          error_tags: tags,
        });
        await LearningCacheDatabase.deleteAction(action.id);
        submitted++;
      } catch (error) {
        LogUtil.warn(TAG, `Feedback ${action.id} remains queued: ${(error as Error).message}`);
        // Keep the action pending. A later foreground session will retry it.
      }
    }
    const remaining = (await LearningCacheDatabase.listPendingActions('feedback')).length;
    return { submitted: submitted, remaining: remaining };
  }
}
