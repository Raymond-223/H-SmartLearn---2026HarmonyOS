import { MasteryLevel } from '../model/MasteryLevel';
import { QuizRecord } from '../model/QuizRecord';
import preferences from '@ohos.data.preferences';

export class DataStore {
  private static readonly PREF_NAME = 'smartlearn_store';

  private static readonly KEY_MASTERY = 'mastery_map';

  private static readonly KEY_RECORDS = 'quiz_records';

  private static callbacks: Array<(nodeId: string, newMastery: number) => void> = [];

  private static pref: preferences.Preferences | null = null;

  private static async getPreferences(): Promise<preferences.Preferences> {
    if (DataStore.pref !== null) {
      return DataStore.pref;
    }

    const context = (globalThis as Record<string, Object>)['abilityContext'];
    if (!context) {
      throw new Error('DataStore requires global abilityContext before accessing preferences.');
    }

    DataStore.pref = await preferences.getPreferences(context, DataStore.PREF_NAME);
    return DataStore.pref;
  }

  static async saveMasteryList(masteryList: MasteryLevel[]): Promise<void> {
    const pref = await DataStore.getPreferences();
    const masteryMap = await DataStore.getAllMastery();

    masteryList.forEach((item) => {
      const safeMastery = Math.max(0, Math.min(1, item.mastery));
      masteryMap.set(item.nodeId, safeMastery);
      DataStore.emitMasteryChanged(item.nodeId, safeMastery);
    });

    const payload = JSON.stringify(Array.from(masteryMap.entries()));
    await pref.put(DataStore.KEY_MASTERY, payload);
    await pref.flush();
  }

  static async getMastery(nodeId: string): Promise<number> {
    const masteryMap = await DataStore.getAllMastery();
    return masteryMap.get(nodeId) ?? 0;
  }

  static async getAllMastery(): Promise<Map<string, number>> {
    const pref = await DataStore.getPreferences();
    const raw = await pref.get(DataStore.KEY_MASTERY, '[]') as string;

    let parsed: Array<[string, number]> = [];
    try {
      parsed = JSON.parse(raw) as Array<[string, number]>;
    } catch (_e) {
      parsed = [];
    }

    return new Map<string, number>(parsed);
  }

  static async addQuizRecord(record: QuizRecord): Promise<void> {
    const pref = await DataStore.getPreferences();
    const list = await DataStore.getRecentRecords(Number.MAX_SAFE_INTEGER);
    list.push(record);

    await pref.put(DataStore.KEY_RECORDS, JSON.stringify(list));
    await pref.flush();
  }

  static async getRecentRecords(limit: number): Promise<QuizRecord[]> {
    if (limit <= 0) {
      return [];
    }

    const pref = await DataStore.getPreferences();
    const raw = await pref.get(DataStore.KEY_RECORDS, '[]') as string;

    let parsed: QuizRecord[] = [];
    try {
      parsed = JSON.parse(raw) as QuizRecord[];
    } catch (_e) {
      parsed = [];
    }

    if (limit >= parsed.length) {
      return parsed;
    }

    return parsed.slice(parsed.length - limit);
  }

  static onMasteryChanged(callback: (nodeId: string, newMastery: number) => void): void {
    DataStore.callbacks.push(callback);
  }

  private static emitMasteryChanged(nodeId: string, newMastery: number): void {
    DataStore.callbacks.forEach((callback) => callback(nodeId, newMastery));
  }
}
