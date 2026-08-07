/** Bright spring-themed formal application home. */
import { DataStore } from '../business/DataStore';
import { OfflineSyncService } from '../business/OfflineSyncService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { PrivacyGuard } from '../integration/PrivacyGuard';
import { ApiService } from '../service/ApiService';
import { SpringColors as C } from '../theme/SpringTheme';
import { LogUtil } from '../utils/LogUtil';
import { promptAction } from '@kit.ArkUI';

const TAG: string = 'Index';

@Entry
@Component
struct Index {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private currentTab: number = 0;
  @State private learnerId: string = '';
  @State private lastResourceId: string = '';
  @State private pendingFeedbackCount: number = 0;
  @State private loading: boolean = true;
  @State private apiOnline: boolean = false;
  @State private hasProfile: boolean = false;
  @State private lastDomainId: string = 'ros2_robotics';

  aboutToAppear(): void {
    ContinuationSession.update('pages/Index');
    this.loadSession();
  }

  async loadSession(): Promise<void> {
    this.loading = true;
    const learnerId: string | null = await DataStore.getLearnerId();
    this.learnerId = learnerId || '';
    this.hasProfile = this.learnerId.length > 0;
    this.lastResourceId = this.hasProfile ? await DataStore.getLastResourceId() || '' : '';
    this.lastDomainId = await DataStore.getLastDomainId();
    try {
      await new ApiService().healthCheck();
      this.apiOnline = true;
      if (this.hasProfile) {
        await DataStore.getAllPendingFeedback();
        await OfflineSyncService.flushFeedback();
      }
    } catch (error) {
      LogUtil.warn(TAG, `Formal API unavailable: ${(error as Error).message}`);
      this.apiOnline = false;
    }
    this.pendingFeedbackCount = (await DataStore.getAllPendingFeedback()).length;
    ContinuationSession.update('pages/Index', this.learnerId, '', this.lastResourceId);
    this.loading = false;
  }

  async openQuiz(domainId: string = ''): Promise<void> {
    const selectedDomain: string = domainId || this.lastDomainId;
    this.lastDomainId = selectedDomain;
    try {
      await DataStore.saveLastDomainId(selectedDomain);
      if (!this.hasProfile) {
        this.getUIContext().getRouter().pushUrl({
          url: 'pages/LearnerProfilePage',
          params: { domainId: selectedDomain },
        });
        return;
      }
      this.getUIContext().getRouter().pushUrl({
        url: 'pages/QuizPage',
        params: { learnerId: this.learnerId, domainId: selectedDomain, demoMode: false },
      });
    } catch (error) {
      LogUtil.error(TAG, `Open diagnosis page failed: ${(error as Error).message}`);
    }
  }

  openTool(page: string): void {
    try {
      if ((page === 'pages/SkillGraphPage' || page === 'pages/ReportPage') && !this.hasProfile) {
        this.getUIContext().getRouter().pushUrl({
          url: 'pages/LearnerProfilePage',
          params: { domainId: this.lastDomainId },
        });
        return;
      }
      this.getUIContext().getRouter().pushUrl({
        url: page,
        params: { learnerId: this.learnerId, domainId: this.lastDomainId, demoMode: false },
      });
    } catch (error) {
      LogUtil.error(TAG, `Open tool page failed: ${(error as Error).message}`);
    }
  }

  openLatestResource(): void {
    if (!this.lastResourceId) {
      this.openQuiz();
      return;
    }
    try {
      this.getUIContext().getRouter().pushUrl({
        url: 'pages/ResourceViewPage',
        params: { learnerId: this.learnerId, resourceId: this.lastResourceId, demoMode: false },
      });
    } catch (error) {
      LogUtil.error(TAG, `Open latest resource failed: ${(error as Error).message}`);
    }
  }

  confirmClearLocalData(): void {
    this.confirmClearLocalDataAsync();
  }

  private async confirmClearLocalDataAsync(): Promise<void> {
    try {
      const result: promptAction.ShowDialogSuccessResponse =
        await this.getUIContext().getPromptAction().showDialog({
          title: '清除本地数据',
          message: '将删除学习者标识、缓存资源和待同步反馈，且无法撤销。',
          buttons: [
            { text: '取消', color: C.muted },
            { text: '确认清除', color: C.danger },
          ],
        });
      if (result.index !== 1) return;
      await DataStore.clearAll();
      try {
        this.getUIContext().getRouter().replaceUrl({ url: 'pages/LearnerProfilePage' });
      } catch (error) {
        LogUtil.error(TAG, `Navigation after clearing data failed: ${(error as Error).message}`);
      }
    } catch (error) {
      const message: string = (error as Error).message || 'Unknown clear-data error';
      LogUtil.error(TAG, `Clear local data failed: ${message}`);
      try {
        await this.getUIContext().getPromptAction().showDialog({
          title: '清除失败',
          message: `本地缓存未被完整删除，请稍后重试。技术信息：${message}`,
          buttons: [{ text: '知道了', color: C.skyDeep }],
        });
      } catch (dialogError) {
        LogUtil.error(TAG, `Failed to show clear-data error dialog: ${(dialogError as Error).message}`);
      }
    }
  }

  build(): void {
    Column() {
      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(48).height(48).color(C.skyDeep)
          Text('正在打开春日学习空间').fontSize(14).fontColor(C.muted)
        }.width('100%').height('100%').justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else {
        Column() {
          if (this.currentTab === 0) {
            this.home();
          } else if (this.currentTab === 1) {
            this.training();
          } else if (this.currentTab === 2) {
            this.analytics();
          } else {
            this.profile();
          }
        }.layoutWeight(1)
        this.navigation();
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  navigation(): void {
    Row({ space: 5 }) {
      this.navButton(0, '⌂', '首页');
      this.navButton(1, '▷', '学习');
      this.navButton(2, '⌁', '学情');
      this.navButton(3, '◎', '我的');
    }.width('100%').height(72).padding({ left: 10, right: 10, top: 7, bottom: 8 })
      .backgroundColor(C.surface).border({ width: { top: 1 }, color: C.border })
  }

  @Builder
  navButton(index: number, icon: string, label: string): void {
    Button() {
      Column({ space: 3 }) {
        Text(icon).fontSize(19).fontColor(this.currentTab === index ? C.skyDeep : C.muted)
        Text(label).fontSize(9).fontWeight(this.currentTab === index ? FontWeight.Bold : FontWeight.Regular)
          .fontColor(this.currentTab === index ? C.textStrong : C.muted)
      }.width('100%').height('100%').justifyContent(FlexAlign.Center)
    }.layoutWeight(1).height(56).type(ButtonType.Normal).borderRadius(17)
      .backgroundColor(this.currentTab === index ? C.surfaceBlue : C.surface)
      .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.currentTab = index; })
  }

  @Builder
  home(): void {
    Scroll() {
      Column({ space: 18 }) {
        this.hero();
        this.statusCard();

        Text('开始学习').fontSize(20).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
        this.domainButton('ROS2 移动机器人', 'Topic 通信 · QoS · 故障排查', C.skyDeep,
          () => this.openQuiz('ros2_robotics'));
        this.domainButton('C语言基础', '变量 · 控制 · 数组 · 函数 · 指针', C.lavenderDeep,
          () => this.openQuiz('c_programming'));

        Text('应用功能').fontSize(20).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
        GridRow({ columns: 4, gutter: 10 }) {
          GridCol({ span: 2 }) { this.toolButton('◇', '技能图谱', C.mintDeep, 'pages/SkillGraphPage'); }
          GridCol({ span: 2 }) { this.toolButton('▥', '学情报告', C.skyDeep, 'pages/ReportPage'); }
          GridCol({ span: 2 }) { this.toolButton('◫', '竞赛指标', C.sakuraDeep, 'pages/BenchmarkPage'); }
          GridCol({ span: 2 }) { this.toolButton('⌁', 'API 设置', C.lavenderDeep, 'pages/ConnectionPage'); }
        }.width('100%')

        Button('🌸 独立春日演示中心').width('100%').height(52).type(ButtonType.Capsule)
          .fontSize(14).fontWeight(FontWeight.Bold).fontColor(C.sakuraDeep)
          .backgroundColor(C.surfaceSoft).border({ width: 1.5, color: C.sakura })
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/DemoCenterPage' })).margin({ bottom: 28 })
      }.width('100%').padding({ left: 18, right: 18, top: 0 })
    }.layoutWeight(1)
  }

  @Builder
  hero(): void {
    Stack() {
      Circle().width(175).height(175).fill(C.sky).opacity(0.14).position({ x: '66%', y: -75 })
      Circle().width(105).height(105).fill(C.sakura).opacity(0.16).position({ x: '82%', y: 108 })
      Column() {
        Row() {
          Text('H-SMARTLEARN').fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
          Blank()
          Text(this.apiOnline ? '真实 API 在线' : '真实 API 离线').fontSize(9).fontColor(C.white)
            .padding({ left: 9, right: 9, top: 5, bottom: 5 })
            .backgroundColor(this.apiOnline ? C.mintDeep : C.warning).borderRadius(11)
        }.width('100%')
        Text('春日 AI 工程学园').fontSize(31).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 22 })
        Text(this.hasProfile ? '在晴空、樱花与新叶之间，完成可审计的多 Agent 学习闭环。' : '请选择正式模式建档，或直接进入免配置演示。')
          .fontSize(12).fontColor(C.muted).lineHeight(19).margin({ top: 8 })
        Row({ space: 10 }) {
          Button('开始 ROS2 诊断').layoutWeight(1).height(46).type(ButtonType.Capsule)
            .backgroundColor(C.skyDeep).fontColor(C.white).fontWeight(FontWeight.Bold)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openQuiz('ros2_robotics'))
          Button('免配置演示').layoutWeight(1).height(46).type(ButtonType.Capsule)
            .backgroundColor(C.surface).fontColor(C.sakuraDeep).border({ width: 1.5, color: C.sakura })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/DemoCenterPage' }))
        }.width('100%').margin({ top: 22 })
        if (this.lastResourceId) {
          Button('继续上次正式学习').width('100%').height(40).type(ButtonType.Capsule)
            .fontSize(11).backgroundColor(C.surfaceMint).fontColor(C.mintDeep)
            .border({ width: 1, color: C.mint }).margin({ top: 10 })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openLatestResource())
        }
      }.width('100%').padding(20)
    }.width('100%').height(258).backgroundColor(C.backgroundBlue).borderRadius({ bottomLeft: 28, bottomRight: 28 })
  }

  @Builder
  statusCard(): void {
    Row({ space: 10 }) {
      this.metric('5+1', '协同 Agent', C.skyDeep);
      this.metric('2', '领域包', C.sakuraDeep);
      this.metric('60', '测试用例', C.mintDeep);
    }.width('100%').padding(12).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  @Builder
  metric(value: string, label: string, accent: string): void {
    Column({ space: 4 }) {
      Text(value).fontSize(22).fontWeight(FontWeight.Bold).fontColor(accent)
      Text(label).fontSize(9).fontColor(C.muted)
    }.layoutWeight(1).padding({ top: 8, bottom: 8 }).alignItems(HorizontalAlign.Center)
  }

  @Builder
  domainButton(title: string, subtitle: string, accent: string, action: () => void): void {
    Button() {
      Row() {
        Column({ space: 6 }) {
          Text(title).fontSize(16).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
          Text(subtitle).fontSize(10).fontColor(C.muted)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Text('→').fontSize(23).fontColor(accent)
      }.width('100%').padding(17)
    }.width('100%').height(86).type(ButtonType.Normal).backgroundColor(C.surface)
      .borderRadius(20).border({ width: 1.5, color: C.border }).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => action())
  }

  @Builder
  toolButton(icon: string, title: string, accent: string, page: string): void {
    Button() {
      Column({ space: 8 }) {
        Text(icon).fontSize(26).fontColor(accent)
        Text(title).fontSize(12).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
      }.width('100%').alignItems(HorizontalAlign.Start)
    }.width('100%').height(94).type(ButtonType.Normal).padding(15).backgroundColor(C.surface)
      .borderRadius(18).border({ width: 1, color: C.border })
      .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openTool(page))
  }

  @Builder
  training(): void {
    Column({ space: 14 }) {
      this.sectionHeader('学习中心', '恢复资源或发起新的真实诊断', C.sky);
      this.actionButton('继续最近资源', '讲义、实操指南与分阶测试', C.skyDeep, () => this.openLatestResource());
      this.actionButton('重新诊断', '更新掌握度并重新规划路径', C.sakuraDeep, () => this.openQuiz());
      this.actionButton('技能图谱', '查看前置依赖和推荐顺序', C.mintDeep,
        () => this.openTool('pages/SkillGraphPage'));
    }.width('100%').height('100%').padding(18)
  }

  @Builder
  analytics(): void {
    Column({ space: 14 }) {
      this.sectionHeader('学情中心', '服务端数据是唯一可信来源', C.lavender);
      this.actionButton('学情报告', '技能掌握度、知识缺口和路径', C.skyDeep,
        () => this.openTool('pages/ReportPage'));
      this.actionButton('竞赛指标', '幻觉率、适配率与覆盖率', C.mintDeep,
        () => this.openTool('pages/BenchmarkPage'));
    }.width('100%').height('100%').padding(18)
  }

  @Builder
  profile(): void {
    Column({ space: 14 }) {
      this.sectionHeader('个人空间', '本地只保存必要标识与待同步反馈', C.mint);
      Column({ space: 8 }) {
        Text('学习者 ID').fontSize(10).fontColor(C.muted).width('100%')
        Text(PrivacyGuard.maskIdentifier(this.learnerId)).fontSize(17).fontWeight(FontWeight.Bold)
          .fontColor(C.textStrong).width('100%')
        Text(this.apiOnline ? '真实 API 已连接' : '真实 API 当前不可达').fontSize(10)
          .fontColor(this.apiOnline ? C.mintDeep : C.warning).width('100%')
        if (this.pendingFeedbackCount > 0) {
          Text(`${this.pendingFeedbackCount} 条反馈等待同步`).fontSize(10).fontColor(C.warning).width('100%')
        }
      }.width('100%').padding(17).backgroundColor(C.surface).borderRadius(20).border({ width: 1, color: C.border })
      this.actionButton('真实 API 设置', '修改地址并测试后端连接', C.skyDeep,
        () => this.openTool('pages/ConnectionPage'));
      this.actionButton('更新学习画像', '重新填写背景与目标', C.sakuraDeep,
        () => this.getUIContext().getRouter().pushUrl({ url: 'pages/LearnerProfilePage', params: { editMode: true, learnerId: this.learnerId, domainId: this.lastDomainId } }));
      Button('清除本地数据').width('100%').height(48).type(ButtonType.Capsule)
        .fontColor(C.danger).backgroundColor(C.surfaceSoft).border({ width: 1, color: '#F1C4D0' })
        .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.confirmClearLocalData())
    }.width('100%').height('100%').padding(18)
  }

  @Builder
  sectionHeader(title: string, subtitle: string, accent: string): void {
    Column({ space: 6 }) {
      Text(title).fontSize(29).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      Text(subtitle).fontSize(12).fontColor(C.muted).width('100%')
    }.width('100%').padding(20).backgroundColor(accent).opacity(0.82).borderRadius(22)
  }

  @Builder
  actionButton(title: string, subtitle: string, accent: string, action: () => void): void {
    Button() {
      Row() {
        Column({ space: 5 }) {
          Text(title).fontSize(15).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
          Text(subtitle).fontSize(10).fontColor(C.muted)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Text('›').fontSize(26).fontColor(accent)
      }.width('100%').padding(16)
    }.width('100%').height(76).type(ButtonType.Normal).backgroundColor(C.surface)
      .borderRadius(18).border({ width: 1, color: C.border }).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => action())
  }
}
