import { DistributedHelper } from '../integration/DistributedHelper';
import { SyncManager } from '../business/SyncManager';

interface DeviceItem {
  deviceId: string;
  deviceName: string;
}

@Entry
@Component
struct DeviceListPage {
  @State private devices: DeviceItem[] = [];
  private refreshTimer: number = -1;

  aboutToAppear(): void {
    DistributedHelper.init();
    DistributedHelper.startScan();
    this.refreshDevices();
    this.refreshTimer = setInterval(() => {
      this.refreshDevices();
    }, 1000);
  }

  aboutToDisappear(): void {
    if (this.refreshTimer !== -1) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = -1;
    }
  }

  private refreshDevices(): void {
    const list = DistributedHelper.getDiscoveredDevices() as DeviceItem[];
    this.devices = Array.isArray(list) ? list : [];
  }

  private onSyncClick(deviceId: string): void {
    SyncManager.syncToDevice(deviceId);
  }

  build() {
    Column({ space: 12 }) {
      Row() {
        Column({ space: 2 }) {
          Text('设备列表（调试）')
            .fontSize(24)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1A1A1A')
            .width('100%')
            .textAlign(TextAlign.Start)
          Text('已发现设备：' + this.devices.length)
            .fontSize(13)
            .fontColor('#6B7280')
            .width('100%')
            .textAlign(TextAlign.Start)
        }
        .layoutWeight(1)
      }
      .width('100%')

      if (this.devices.length === 0) {
        Column({ space: 10 }) {
          Text('暂未发现可接续设备')
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .fontColor('#374151')
          Text('请确认同一局域网和分布式认证状态')
            .fontSize(13)
            .fontColor('#6B7280')
        }
        .width('100%')
        .padding({ top: 28, bottom: 28, left: 16, right: 16 })
        .borderRadius(14)
        .backgroundColor('#FFFFFF')
      }
      else {
        List({ space: 10 }) {
          ForEach(this.devices, (item: DeviceItem) => {
            ListItem() {
              Row() {
                Column() {
                  Text(item.deviceName || '未知设备')
                    .fontSize(16)
                    .fontWeight(FontWeight.Medium)
                    .width('100%')
                    .textAlign(TextAlign.Start)
                    .fontColor('#111827')
                  Text(item.deviceId)
                    .fontSize(12)
                    .fontColor('#8A94A6')
                    .width('100%')
                    .textAlign(TextAlign.Start)
                }
                .layoutWeight(1)

                Button('同步')
                  .height(36)
                  .fontSize(14)
                  .fontWeight(FontWeight.Medium)
                  .backgroundColor('#3B82F6')
                  .fontColor('#FFFFFF')
                  .onClick(() => {
                    this.onSyncClick(item.deviceId);
                  })
              }
              .width('100%')
              .padding(12)
              .borderRadius(12)
              .backgroundColor('#FFFFFF')
              .border({ width: 1, color: '#E9ECF1' })
            }
          }, (item: DeviceItem) => item.deviceId)
        }
        .layoutWeight(1)
        .width('100%')
      }
    }
    .width('100%')
    .height('100%')
    .padding(16)
    .backgroundColor('#F2F4F7')
    .alignItems(HorizontalAlign.Start)
  }
}
