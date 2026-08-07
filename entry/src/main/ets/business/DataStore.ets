/** Local cache. Server-side mastery and paths remain the source of truth. */
import preferences from '@ohos.data.preferences';
import { common } from '@kit.AbilityKit';
import { LearningCacheDatabase } from './LearningCacheDatabase';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'DataStore';

const PREF_NAME: string = 'smartlearn_store_v2';
const KEY_LEARNER_ID: string = 'learner_id';
const KEY_PENDING_FEEDBACK: string = 'pending_feedback';
const KEY_MASTERY_MAP: string = 'mastery_map';
const KEY_LAST_WORKFLOW_ID: string = 'last_workflow_id';
const KEY_LAST_RESOURCE_ID: string = 'last_resource_id';
const KEY_API_BASE_URL: string = 'api_base_url';
const KEY_DEMO_FALLBACK: string = 'demo_fallback';
const KEY_LAST_DOMAIN_ID: string = 'last_domain_id';
const KEY_LAST_DEMO_PROFILE: string = 'last_demo_profile';
const KEY_RESOURCE_NOTE_PREFIX: string = 'resource_note_';
const KEY_RESOURCE_BOOKMARK_PREFIX: string = 'resource_bookmark_';

export interface NodeMastery {
  nodeId: string;
  mastery: number;
}

export class DataStore {
  private static pref: preferences.Preferences | null = null;
  private static appContext: common.Context | null = null;

  static init(context: common.Context): void {
    DataStore.appContext = context;
    LearningCacheDatabase.init(context);
  }

  private static async getPreferences(): Promise<preferences.Preferences> {
    if (DataStore.pref !== null) {
      return DataStore.pref;
    }
    if (DataStore.appContext === null) {
      throw new Error('DataStore is not initialized');
    }
    try {
      DataStore.pref = await preferences.getPreferences(DataStore.appContext, PREF_NAME);
      return DataStore.pref;
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown Preferences error';
      LogUtil.error(TAG, `Open Preferences failed: ${message}`);
      throw new Error(`Local preferences unavailable: ${message}`);
    }
  }

  private static async saveString(key: string, value: string): Promise<void> {
    try {
      const pref: preferences.Preferences = await DataStore.getPreferences();
      await pref.put(key, value);
      await pref.flush();
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown Preferences write error';
      LogUtil.error(TAG, `Save local value failed for ${key}: ${message}`);
      throw new Error(`Unable to save local value: ${message}`);
    }
  }

  private static async getString(key: string): Promise<string> {
    try {
      const pref: preferences.Preferences = await DataStore.getPreferences();
      return await pref.get(key, '') as string;
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown Preferences read error';
      LogUtil.error(TAG, `Read local value failed for ${key}: ${message}`);
      throw new Error(`Unable to read local value: ${message}`);
    }
  }

  static async saveLearnerId(id: string): Promise<void> {
    await DataStore.saveString(KEY_LEARNER_ID, id);
  }

  static async getLearnerId(): Promise<string | null> {
    const value = await DataStore.getString(KEY_LEARNER_ID);
    return value || null;
  }

  static async saveLastWorkflowId(id: string): Promise<void> {
    await DataStore.saveString(KEY_LAST_WORKFLOW_ID, id);
  }

  static async getLastWorkflowId(): Promise<string | null> {
    const value = await DataStore.getString(KEY_LAST_WORKFLOW_ID);
    return value || null;
  }

  static async saveLastDomainId(domainId: string): Promise<void> {
    await DataStore.saveString(KEY_LAST_DOMAIN_ID, domainId);
  }

  static async getLastDomainId(): Promise<string> {
    const value = await DataStore.getString(KEY_LAST_DOMAIN_ID);
    return value || 'ros2_robotics';
  }

  static async saveLastDemoProfile(profileId: string): Promise<void> {
    await DataStore.saveString(KEY_LAST_DEMO_PROFILE, profileId);
  }

  static async getLastDemoProfile(): Promise<string> {
    const value = await DataStore.getString(KEY_LAST_DEMO_PROFILE);
    return value || 'beginner';
  }


  static async saveApiBaseUrl(url: string): Promise<void> {
    await DataStore.saveString(KEY_API_BASE_URL, url.trim());
  }

  static async getApiBaseUrl(): Promise<string | null> {
    const value = await DataStore.getString(KEY_API_BASE_URL);
    return value || null;
  }

  static async saveDemoFallbackEnabled(enabled: boolean): Promise<void> {
    await DataStore.saveString(KEY_DEMO_FALLBACK, enabled ? 'true' : 'false');
  }

  static async getDemoFallbackEnabled(): Promise<boolean> {
    const value = await DataStore.getString(KEY_DEMO_FALLBACK);
    return value === 'true';
  }

  static async saveResourceNote(resourceId: string, note: string): Promise<void> {
    await DataStore.saveString(KEY_RESOURCE_NOTE_PREFIX + resourceId, note);
  }

  static async getResourceNote(resourceId: string): Promise<string> {
    return await DataStore.getString(KEY_RESOURCE_NOTE_PREFIX + resourceId);
  }

  static async saveResourceBookmark(resourceId: string, bookmarked: boolean): Promise<void> {
    await DataStore.saveString(KEY_RESOURCE_BOOKMARK_PREFIX + resourceId, bookmarked ? 'true' : 'false');
  }

  static async getResourceBookmark(resourceId: string): Promise<boolean> {
    return await DataStore.getString(KEY_RESOURCE_BOOKMARK_PREFIX + resourceId) === 'true';
  }

  static async saveLastResourceId(id: string): Promise<void> {
    await DataStore.saveString(KEY_LAST_RESOURCE_ID, id);
  }

  static async getLastResourceId(): Promise<string | null> {
    const value = await DataStore.getString(KEY_LAST_RESOURCE_ID);
    return value || null;
  }


  private static feedbackResourceId(payload: string): string {
    try {
      const parsed = JSON.parse(payload) as Record<string, Object>;
      const value: Object | undefined = parsed['resource_id'];
      return typeof value === 'string' ? value : '';
    } catch (error) {
      LogUtil.warn(TAG, `Invalid pending feedback payload ignored: ${(error as Error).message}`);
      return '';
    }
  }

  private static containsResourceFeedback(payloads: string[], resourceId: string): boolean {
    if (!resourceId) return false;
    return payloads.some((payload: string): boolean => DataStore.feedbackResourceId(payload) === resourceId);
  }

  static async savePendingFeedback(feedbackJson: string): Promise<void> {
    const resourceId: string = DataStore.feedbackResourceId(feedbackJson);
    try {
      const existing = await LearningCacheDatabase.listPendingActions('feedback');
      if (DataStore.containsResourceFeedback(existing.map((item) => item.payload), resourceId)) return;
      await LearningCacheDatabase.enqueueAction('feedback', feedbackJson);
    } catch (error) {
      LogUtil.warn(TAG, `ArkData feedback queue unavailable, using Preferences fallback: ${(error as Error).message}`);
      // Preferences fallback keeps older devices and preview environments usable.
      try {
        const pref: preferences.Preferences = await DataStore.getPreferences();
        const list: string[] = await DataStore.getPreferenceFeedback();
        if (!DataStore.containsResourceFeedback(list, resourceId)) list.push(feedbackJson);
        await pref.put(KEY_PENDING_FEEDBACK, JSON.stringify(list));
        await pref.flush();
      } catch (fallbackError) {
        const message: string = (fallbackError as Error).message || 'Unknown fallback storage error';
        LogUtil.error(TAG, `Preferences feedback fallback failed: ${message}`);
        throw new Error(`Unable to cache pending feedback: ${message}`);
      }
    }
  }

  static async hasPendingFeedback(resourceId: string): Promise<boolean> {
    const payloads: string[] = await DataStore.getAllPendingFeedback();
    return DataStore.containsResourceFeedback(payloads, resourceId);
  }

  private static async getPreferenceFeedback(): Promise<string[]> {
    try {
      const pref: preferences.Preferences = await DataStore.getPreferences();
      const raw: string = await pref.get(KEY_PENDING_FEEDBACK, '[]') as string;
      try {
        return JSON.parse(raw) as string[];
      } catch (error) {
        LogUtil.warn(TAG, `Invalid Preferences feedback cache cleared: ${(error as Error).message}`);
        return [];
      }
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown Preferences feedback read error';
      LogUtil.error(TAG, `Read Preferences feedback queue failed: ${message}`);
      throw new Error(`Unable to read fallback feedback queue: ${message}`);
    }
  }

  private static async migratePreferenceFeedbackToDatabase(): Promise<void> {
    const fallback: string[] = await DataStore.getPreferenceFeedback();
    if (fallback.length === 0) return;
    const existing = await LearningCacheDatabase.listPendingActions('feedback');
    const known: Set<string> = new Set<string>();
    for (const action of existing) known.add(action.payload);
    for (const payload of fallback) {
      if (!known.has(payload)) {
        await LearningCacheDatabase.enqueueAction('feedback', payload);
        known.add(payload);
      }
    }
    await DataStore.saveString(KEY_PENDING_FEEDBACK, '[]');
    LogUtil.info(TAG, `Migrated ${fallback.length} fallback feedback records into ArkData`);
  }

  static async getAllPendingFeedback(): Promise<string[]> {
    try {
      await DataStore.migratePreferenceFeedbackToDatabase();
      const actions = await LearningCacheDatabase.listPendingActions('feedback');
      return actions.map((item) => item.payload);
    } catch (error) {
      LogUtil.warn(TAG, `Unable to read ArkData feedback queue: ${(error as Error).message}`);
      return await DataStore.getPreferenceFeedback();
    }
  }

  static async clearPendingFeedback(): Promise<void> {
    try {
      await LearningCacheDatabase.clearActions('feedback');
    } catch (error) {
      LogUtil.warn(TAG, `Unable to clear ArkData feedback queue: ${(error as Error).message}`);
    }
    await DataStore.saveString(KEY_PENDING_FEEDBACK, '[]');
  }

  static async saveMasteryList(masteryList: NodeMastery[]): Promise<void> {
    const current = await DataStore.getAllMastery();
    for (const item of masteryList) {
      current.set(item.nodeId, Math.max(0, Math.min(100, item.mastery)));
    }
    const entries: string[][] = [];
    current.forEach((value: number, key: string) => {
      entries.push([key, value.toString()]);
    });
    await DataStore.saveString(KEY_MASTERY_MAP, JSON.stringify(entries));
  }

  static async getAllMastery(): Promise<Map<string, number>> {
    const raw = await DataStore.getString(KEY_MASTERY_MAP);
    const result = new Map<string, number>();
    if (!raw) {
      return result;
    }
    try {
      const entries = JSON.parse(raw) as string[][];
      for (const entry of entries) {
        if (entry.length >= 2) {
          result.set(entry[0], Number(entry[1]));
        }
      }
    } catch (error) {
      LogUtil.warn(TAG, `Invalid mastery cache ignored: ${(error as Error).message}`);
    }
    return result;
  }

  static async clearAll(): Promise<void> {
    // Clear the structured cache first. If it fails, preserve Preferences so the
    // application does not enter a partially-cleared state.
    try {
      await LearningCacheDatabase.clearAll();
      const pref: preferences.Preferences = await DataStore.getPreferences();
      await pref.clear();
      await pref.flush();
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown local clear error';
      LogUtil.error(TAG, `Clear all local data failed: ${message}`);
      throw new Error(`Unable to clear local data: ${message}`);
    }
  }
}
