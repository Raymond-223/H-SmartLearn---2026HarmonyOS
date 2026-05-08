import { DistributedHelper } from '../integration/DistributedHelper';
import { LogUtil } from '../utils/LogUtil';

export class SyncManager {
  static async syncToDevice(deviceId: string): Promise<void> {
    const found = DistributedHelper.getDiscoveredDevices().find((item) => item.deviceId === deviceId);
    if (!found) {
      LogUtil.warn('SyncManager', `device not found: ${deviceId}`);
      return;
    }
    LogUtil.info('SyncManager', `sync success: ${found.deviceName} (${deviceId})`);
  }
}
