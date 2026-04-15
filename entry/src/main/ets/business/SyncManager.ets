import { DataStore } from './DataStore';
import { DistributedHelper } from '../integration/DistributedHelper';

export class SyncManager {
  private static initialized = false;

  private static debounceTimer: number | undefined = undefined;

  static async init(): Promise<void> {
    if (SyncManager.initialized) {
      return;
    }

    DistributedHelper.onDataReceived(async (_fromDeviceId: string, masteryMap: Map<string, number>) => {
      const masteryList = Array.from(masteryMap.entries()).map(([nodeId, mastery]) => ({
        nodeId,
        mastery,
        updatedAt: Date.now(),
      }));

      await DataStore.saveMasteryList(masteryList);
    });

    DataStore.onMasteryChanged(() => {
      if (SyncManager.debounceTimer !== undefined) {
        clearTimeout(SyncManager.debounceTimer);
      }

      SyncManager.debounceTimer = setTimeout(() => {
        void SyncManager.broadcastToAll();
      }, 300) as unknown as number;
    });

    SyncManager.initialized = true;
  }

  static async syncToDevice(deviceId: string): Promise<boolean> {
    const masteryMap = await DataStore.getAllMastery();
    return DistributedHelper.sendData(deviceId, masteryMap);
  }

  static async broadcastToAll(): Promise<boolean> {
    const devices = await DistributedHelper.getDiscoveredDevices();
    if (devices.length === 0) {
      return false;
    }

    const results = await Promise.all(devices.map((device) => SyncManager.syncToDevice(device.deviceId)));
    return results.some((ok) => ok);
  }
}
