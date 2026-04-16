import { SyncManager } from '../business/SyncManager';
import router from '@ohos.router';

@Entry
@Component
struct PadContinuePage {
  @State private fromDeviceId: string = '';
  @State private loading: boolean = false;

  aboutToAppear(): void {
    const params = router.getParams() as Record<string, Object>;
    const deviceId = params?.fromDeviceId;
    this.fromDeviceId = typeof deviceId === 'string' ? deviceId : '';
  }

  private async onContinue(): Promise<void> {
    if (!this.fromDeviceId) {
      return;
    }
    this.loading = true;
    try {
      await SyncManager.syncToDevice(this.fromDeviceId);
      router.replaceUrl({ url: 'pages/Graph3DPage' });
    } finally {
      this.loading = false;
    }
  }

  build() {
    Column() {
      Column({ space: 14 }) {
        Text('检测到手机学习进度')
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor('#111827')
          .textAlign(TextAlign.Center)
        Text('是否在平板上继续学习？')
          .fontSize(17)
          .fontColor('#4B5563')
          .textAlign(TextAlign.Center)

        Text(this.fromDeviceId ? `来源设备：${this.fromDeviceId}` : '来源设备：未知')
          .fontSize(13)
          .fontColor('#6B7280')
          .textAlign(TextAlign.Center)

        Button(this.loading ? '同步中...' : '继续')
          .width('100%')
          .height(46)
          .enabled(!this.loading && !!this.fromDeviceId)
          .fontSize(17)
          .fontWeight(FontWeight.Medium)
          .backgroundColor(!this.loading && !!this.fromDeviceId ? '#3B82F6' : '#B7C6E6')
          .onClick(() => {
            this.onContinue();
          })
      }
      .width('100%')
      .padding({ left: 18, right: 18, top: 24, bottom: 24 })
      .borderRadius(18)
      .backgroundColor('#FFFFFF')
      .border({ width: 1, color: '#E9ECF1' })
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .backgroundColor('#F2F4F7')
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
  }
}
