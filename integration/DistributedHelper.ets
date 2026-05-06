import deviceManager from '@ohos.distributedHardware.deviceManager';
import distributedData from '@ohos.data.distributedDataObject';

export class DistributedHelper {
  private static dmInstance: deviceManager.DeviceManager | null = null;
  private static distributedObject: distributedData.DataObject | null = null;
  private static dataReceivedCallback: ((fromDeviceId: string, masteryMap: Map<string, number>) => void) | null = null;

  static async init(): Promise<boolean> {
    try {
      const bundleName = 'com.example.smartlearn';
      deviceManager.createDeviceManager(bundleName, (err, dm) => {
        if (err) {
          console.error(`[DistributedHelper] 设备管理器初始化失败: ${err}`);
          return;
        }
        DistributedHelper.dmInstance = dm;
      });

      // 初始化分布式对象，声明内部包含一个 masteryData 字段
      DistributedHelper.distributedObject = distributedData.createDistributedObject({
        masteryData: {}
      });

      // 监听底层软总线的数据变化事件
      DistributedHelper.distributedObject.on('change', (sessionId: string, fields: Array<string>) => {
        if (fields.includes('masteryData') && DistributedHelper.dataReceivedCallback) {
          // 软总线传过来的是 Record，需要反序列化回 Map 交给业务层
          const rawData = DistributedHelper.distributedObject['masteryData'] as Record<string, number>;
          const newMasteryMap = new Map<string, number>(Object.entries(rawData));
          DistributedHelper.dataReceivedCallback(sessionId, newMasteryMap);
        }
      });

      return true;
    } catch (error) {
      console.error(`[DistributedHelper] 初始化异常: ${error}`);
      return false;
    }
  }

  static onDataReceived(callback: (fromDeviceId: string, masteryMap: Map<string, number>) => void): void {
    DistributedHelper.dataReceivedCallback = callback;
  }

  static async startScan(): Promise<void> {
    if (!DistributedHelper.dmInstance) return;
    const subscribeInfo = {
      subscribeId: 100, mode: 0xAA, medium: 0, freq: 2, isSameAccount: false, isWakeRemote: false, capability: 0
    };
    DistributedHelper.dmInstance.startDeviceDiscovery(subscribeInfo);
  }

  static async stopScan(): Promise<void> {
    if (!DistributedHelper.dmInstance) return;
    DistributedHelper.dmInstance.stopDeviceDiscovery(100);
  }

  static async getDiscoveredDevices(): Promise<Array<{ deviceId: string, deviceName: string }>> {
    if (!DistributedHelper.dmInstance) return [];
    const deviceList = DistributedHelper.dmInstance.getTrustedDeviceListSync();
    return deviceList.map(dev => ({ deviceId: dev.deviceId, deviceName: dev.deviceName }));
  }

  static async sendData(targetDeviceId: string, masteryMap: Map<string, number>): Promise<boolean> {
    if (!DistributedHelper.distributedObject) return false;
    try {
      // 业务层传来的是 Map，将其扁平化为普通对象以适应底层传输
      const rawObj: Record<string, number> = {};
      masteryMap.forEach((value, key) => { rawObj[key] = value; });

      DistributedHelper.distributedObject['masteryData'] = rawObj;
      // 建立指定设备的通信 Session，触发同步
      DistributedHelper.distributedObject.setSessionId(targetDeviceId);
      return true;
    } catch (error) {
      return false;
    }
  }

  static async release(): Promise<void> {
    if (DistributedHelper.dmInstance) {
      DistributedHelper.dmInstance.release();
      DistributedHelper.dmInstance = null;
    }
    if (DistributedHelper.distributedObject) {
      DistributedHelper.distributedObject.setSessionId('');
      DistributedHelper.distributedObject = null;
    }
  }
}