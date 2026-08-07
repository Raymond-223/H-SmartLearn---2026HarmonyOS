/** Real API connection settings. Demo mode is intentionally not configured here. */
import { ApiRuntimeState, ApiService } from '../service/ApiService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';

@Entry
@Component
struct ConnectionPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private baseUrl: string = ApiService.getDefaultBaseUrl();
  @State private testing: boolean = false;
  @State private message: string = '';
  @State private success: boolean = false;
  @State private technicalMessage: string = '';
  @State private showTechnical: boolean = false;

  aboutToAppear(): void {
    ContinuationSession.update('pages/ConnectionPage');
    this.loadConnectionState();
  }

  async loadConnectionState(): Promise<void> {
    const state: ApiRuntimeState = ApiService.getRuntimeState();
    this.message = state.lastError;
    try {
      this.baseUrl = await ApiService.getConfiguredBaseUrl();
    } catch (error) {
      this.baseUrl = ApiService.getDefaultBaseUrl();
      this.technicalMessage = `读取已保存地址失败：${(error as Error).message}`;
    }
  }

  isValidBaseUrl(value: string): boolean {
    const trimmed: string = value.trim();
    return /^https?:\/\/[^\s/]+(?::\d{1,5})?(?:\/[^\s]*)?$/.test(trimmed);
  }

  async testAndSave(): Promise<void> {
    if (!this.isValidBaseUrl(this.baseUrl)) {
      this.success = false;
      this.message = '地址格式不正确，请填写以 http:// 或 https:// 开头的服务地址。';
      this.technicalMessage = '';
      return;
    }
    this.baseUrl = this.baseUrl.trim();
    this.testing = true;
    this.message = '';
    this.success = false;
    this.technicalMessage = '';
    this.showTechnical = false;
    try {
      const api: ApiService = new ApiService(this.baseUrl, false);
      await api.healthCheckRemoteOnly();
      await ApiService.configure(this.baseUrl, false);
      this.success = true;
      this.message = '连接成功，正式应用已保存该真实 API 地址。';
    } catch (error) {
      this.message = '未连接到正式服务。可检查地址与后端状态，或直接进入免配置演示。';
      this.technicalMessage = (error as Error).message;
    } finally {
      this.testing = false;
    }
  }

  build(): void {
    Column() {
      Stack() {
        Column() {
          Text('REAL API SETTINGS').fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
          Text('真实服务连接').fontSize(30).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 19 })
          Text('这里仅配置正式 API。模拟数据只能从独立演示中心进入。')
            .fontSize(12).fontColor(C.muted).lineHeight(19).margin({ top: 7 })
        }.width('100%').padding({ left: 22, right: 22, top: 29, bottom: 24 })
        Circle().width(165).height(165).fill(C.sky).opacity(0.14).position({ x: '68%', y: -80 })
        Circle().width(94).height(94).fill(C.mint).opacity(0.15).position({ x: '84%', y: 91 })
      }.width('100%').height(185).backgroundColor(C.backgroundBlue)

      Scroll() {
        Column({ space: 15 }) {
          Column({ space: 10 }) {
            Text('API 地址').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
            TextInput({ text: this.baseUrl, placeholder: 'http://10.0.2.2:8000' })
              .width('100%').height(50).fontSize(14).fontColor(C.textStrong).placeholderColor('#A3AFBB')
              .backgroundColor(C.surface).borderRadius(14).padding({ left: 14, right: 14 })
              .border({ width: 1.5, color: C.border }).onChange((value: string) => { this.baseUrl = value; })
            Text('模拟器使用 http://10.0.2.2:8000；浏览器健康检查使用 http://127.0.0.1:8000/health。')
              .fontSize(10).fontColor(C.muted).lineHeight(17).width('100%')
          }.width('100%').padding(17).backgroundColor(C.surface).borderRadius(20)
            .border({ width: 1, color: C.border })

          Column({ space: 8 }) {
            Text('启动检查').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
            this.checkRow('1', '双击项目根目录 start.bat');
            this.checkRow('2', '等待窗口显示 Uvicorn running');
            this.checkRow('3', '浏览器打开 /health');
            this.checkRow('4', '回到此页点击测试并保存');
          }.width('100%').padding(17).backgroundColor(C.surfaceMint).borderRadius(20)
            .border({ width: 1, color: C.border })

          if (this.message) {
            Column({ space: 8 }) {
              Text(this.message).fontSize(11).fontColor(this.success ? C.mintDeep : C.danger).lineHeight(18).width('100%')
              if (this.technicalMessage) {
                Button(this.showTechnical ? '收起技术信息' : '查看技术信息').height(34).type(ButtonType.Capsule)
                  .fontSize(10).fontColor(C.muted).backgroundColor(C.surface)
                  .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.showTechnical = !this.showTechnical; })
                if (this.showTechnical) {
                  Text(this.technicalMessage).fontSize(9).fontColor(C.muted).lineHeight(15).width('100%')
                }
              }
            }.width('100%').padding(14).backgroundColor(this.success ? C.surfaceMint : C.surfaceSoft).borderRadius(15)
          }

          Button(this.testing ? '正在连接…' : '测试真实 API 并保存').width('100%').height(52).type(ButtonType.Capsule)
            .fontWeight(FontWeight.Bold).fontColor(C.white).backgroundColor(C.skyDeep)
            .enabled(!this.testing).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.testAndSave())
          Button('打开独立演示中心').width('100%').height(48).type(ButtonType.Capsule)
            .fontColor(C.sakuraDeep).backgroundColor(C.surfaceSoft).border({ width: 1.5, color: C.sakura })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/DemoCenterPage' }))
          Button('返回').width('100%').height(46).type(ButtonType.Capsule)
            .fontColor(C.skyDeep).backgroundColor(C.surfaceBlue).border({ width: 1, color: C.sky })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().back()).margin({ bottom: 28 })
        }.width('100%').padding({ left: 18, right: 18, top: 20 })
      }.layoutWeight(1)
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  checkRow(index: string, text: string): void {
    Row({ space: 10 }) {
      Text(index).width(26).height(26).textAlign(TextAlign.Center).fontSize(11).fontWeight(FontWeight.Bold)
        .fontColor(C.white).backgroundColor(C.mintDeep).borderRadius(13)
      Text(text).fontSize(11).fontColor(C.textStrong).layoutWeight(1)
    }.width('100%')
  }
}
