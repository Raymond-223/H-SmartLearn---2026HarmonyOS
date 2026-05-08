export interface DeviceInfo {
  deviceId: string;
  deviceName: string;
}

export class DistributedHelper {
  private static inited: boolean = false;
  private static devices: DeviceInfo[] = [];

  static init(): void {
    this.inited = true;
  }

  static startScan(): void {
    if (!this.inited) {
      this.init();
    }
    this.devices = [
      { deviceId: 'phone-001', deviceName: 'Mate 60 Pro' },
      { deviceId: 'pad-002', deviceName: 'MatePad Pro' }
    ];
  }

  static getDiscoveredDevices(): DeviceInfo[] {
    return this.devices;
  }
}
