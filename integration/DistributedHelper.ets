// 导入鸿蒙原生的设备管理和分布式数据 SDK
import deviceManager from '@ohos.distributedHardware.deviceManager';
import distributedData from '@ohos.data.distributedDataObject';

export class DistributedHelper {
  // 设备管理器实例
  private static dmInstance: deviceManager.DeviceManager | null = null;
  // 维护一个统一的分布式数据对象，用于跨端同步掌握度字典
  private static distributedObject: distributedData.DataObject | null = null;

  // 业务层传进来的回调函数，当收到其他设备发来的数据时触发
  private static dataReceivedCallback: ((fromDeviceId: string, masteryMap: Map<string, number>) => void) | null = null;

  /**
   * 初始化分布式环境
   */
  static async init(): Promise<boolean> {
    try {
      const bundleName = 'com.example.smartlearn'; // 应用的包名

      // 1. 创建系统的设备管理器实例
      deviceManager.createDeviceManager(bundleName, (err, dm) => {
        if (err) {
          console.error(`[Distributed] 创建设备管理器失败: ${err}`);
          return;
        }
        DistributedHelper.dmInstance = dm;
      });

      // 2. 初始化分布式数据对象（相当于建一个云端共享的变量）
      // 这里声明了共享的数据结构：一个名为 masteryData 的字典
      DistributedHelper.distributedObject = distributedData.createDistributedObject({
        masteryData: {}
      });

      // 3. 监听分布式数据对象的变化（这是鸿蒙软总线的核心能力，远端修改，本地自动触发回调）
      DistributedHelper.distributedObject.on('change', (sessionId: string, fields: Array<string>) => {
        if (fields.includes('masteryData') && DistributedHelper.dataReceivedCallback) {
          // 当远端设备修改了 masteryData，我们将数据解析回 Map 并通知业务层 (SyncManager)
          const rawData = DistributedHelper.distributedObject['masteryData'];
          const newMasteryMap = new Map<string, number>(Object.entries(rawData));
          // 假设 sessionId 就是发来数据的设备 ID
          DistributedHelper.dataReceivedCallback(sessionId, newMasteryMap);
        }
      });

      console.info('[Distributed] 分布式软总线初始化成功');
      return true;
    } catch (error) {
      console.error(`[Distributed] 初始化异常: ${error}`);
      return false;
    }
  }

  /**
   * 注册收到数据的回调（由 SyncManager 注册）
   */
  static onDataReceived(callback: (fromDeviceId: string, masteryMap: Map<string, number>) => void): void {
    DistributedHelper.dataReceivedCallback = callback;
  }

  /**
   * 开始扫描周围的鸿蒙设备
   */
  static async startScan(): Promise<void> {
    if (!DistributedHelper.dmInstance) return;

    // 构造发现设备的参数（比如只扫描支持蓝牙和 Wi-Fi 的设备）
    const subscribeInfo = {
      subscribeId: 100, // 任务ID
      mode: 0xAA, // 主动发现模式
      medium: 0,  // 自动选择介质
      freq: 2,    // 高频率扫描
      isSameAccount: false,
      isWakeRemote: false,
      capability: 0
    };

    DistributedHelper.dmInstance.startDeviceDiscovery(subscribeInfo);
    console.info('[Distributed] 开始扫描周围设备...');
  }

  /**
   * 停止扫描
   */
  static async stopScan(): Promise<void> {
    if (!DistributedHelper.dmInstance) return;
    DistributedHelper.dmInstance.stopDeviceDiscovery(100);
    console.info('[Distributed] 停止扫描设备');
  }

  /**
   * 获取当前可用的受信任设备列表
   */
  static async getDiscoveredDevices(): Promise<Array<{ deviceId: string, deviceName: string }>> {
    if (!DistributedHelper.dmInstance) return [];

    // 从系统获取已经认证信任的设备列表
    const deviceList = DistributedHelper.dmInstance.getTrustedDeviceListSync();

    return deviceList.map(dev => ({
      deviceId: dev.deviceId,
      deviceName: dev.deviceName
    }));
  }

  /**
   * 将本地掌握度数据发送给指定设备
   */
  static async sendData(targetDeviceId: string, masteryMap: Map<string, number>): Promise<boolean> {
    if (!DistributedHelper.distributedObject) return false;

    try {
      // 1. 将 Map 转换为标准的 JSON 对象，因为底层软总线更适合传输基础对象
      const rawObj: Record<string, number> = {};
      masteryMap.forEach((value, key) => {
        rawObj[key] = value;
      });

      // 2. 将数据写入分布式的对象中
      DistributedHelper.distributedObject['masteryData'] = rawObj;

      // 3. 将这个共享对象加入到一个特定的网络 Session 中（使用目标设备的 ID）
      // 鸿蒙底层会自动将对象内的数据推送到目标设备上
      DistributedHelper.distributedObject.setSessionId(targetDeviceId);

      console.info(`[Distributed] 数据已通过软总线推送至设备: ${targetDeviceId}`);
      return true;
    } catch (error) {
      console.error(`[Distributed] 数据同步失败: ${error}`);
      return false;
    }
  }

  /**
   * 释放分布式资源
   */
  static async release(): Promise<void> {
    if (DistributedHelper.dmInstance) {
      DistributedHelper.dmInstance.release();
      DistributedHelper.dmInstance = null;
    }
    if (DistributedHelper.distributedObject) {
      DistributedHelper.distributedObject.setSessionId(''); // 退出共享网络
      DistributedHelper.distributedObject = null;
    }
    console.info('[Distributed] 分布式资源已释放');
  }
}