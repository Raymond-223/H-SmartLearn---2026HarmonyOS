/**
 * Uses UIContext Router to avoid deprecated global page-router calls.
 * Full Navigation/NavPathStack migration remains an application-wide architectural option.
 * Explicit isolated demo entry; all downstream data comes from DemoBackend.
 */
import { router } from '@kit.ArkUI';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { DataStore } from '../business/DataStore';

interface DemoProfile {
  id: string;
  title: string;
  subtitle: string;
  tag: string;
  accent: string;
}

const PROFILES: DemoProfile[] = [
  { id: 'beginner', title: '零基础转专业', subtitle: '从环境与通信概念开始，讲解更通俗', tag: '基础', accent: C.sakura },
  { id: 'mechanical', title: '机械背景本科生', subtitle: '突出机器人实操与工程映射', tag: '实践', accent: C.sky },
  { id: 'developer', title: '软件开发进阶者', subtitle: '压缩基础内容，加入 QoS 挑战', tag: '进阶', accent: C.lavender },
];

@Entry
@Component
struct DemoCenterPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private selectedProfile: string = 'mechanical';
  @State private selectedDomain: string = 'ros2_robotics';
  @State private errorMsg: string = '';

  aboutToAppear(): void {
    ContinuationSession.update('pages/DemoCenterPage');
  }

  async startDemo(): Promise<void> {
    this.errorMsg = '';
    try {
      await DataStore.saveLastDomainId(this.selectedDomain);
      await DataStore.saveLastDemoProfile(this.selectedProfile);
      this.getUIContext().getRouter().pushUrl({
        url: 'pages/QuizPage',
        params: {
          learnerId: `learner_demo_${this.selectedProfile}`,
          domainId: this.selectedDomain,
          demoMode: true,
          demoProfile: this.selectedProfile,
        },
      }, router.RouterMode.Standard);
    } catch (error) {
      this.errorMsg = `启动演示失败：${(error as Error).message}`;
    }
  }

  build(): void {
    Column() {
      this.header();
      Scroll() {
        Column({ space: 18 }) {
          Column({ space: 6 }) {
            Text('选择演示画像').fontSize(20).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
            Text('此页面之后的题目、Agent 轨迹、资源和报告全部使用内置模拟数据，不访问真实 API。')
              .fontSize(12).fontColor(C.muted).lineHeight(19).width('100%')
          }.width('100%')

          Column({ space: 10 }) {
            ForEach(PROFILES, (profile: DemoProfile) => {
              Row() {
                Radio({ value: profile.id, group: 'demo_profile' })
                  .checked(this.selectedProfile === profile.id)
                  .width(28).height(28)
                  .onChange((checked: boolean) => {
                    if (checked) this.selectedProfile = profile.id;
                  })
                Column({ space: 5 }) {
                  Row({ space: 8 }) {
                    Text(profile.title).fontSize(15).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
                    Text(profile.tag).fontSize(9).fontColor(C.white)
                      .padding({ left: 8, right: 8, top: 4, bottom: 4 })
                      .backgroundColor(profile.accent).borderRadius(10)
                  }
                  Text(profile.subtitle).fontSize(11).fontColor(C.muted).width('100%')
                }.layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ left: 10 })
                Text(this.selectedProfile === profile.id ? '✓' : '').fontSize(21)
                  .fontColor(C.mintDeep).width(24)
              }.width('100%').height(88).padding(16)
                .backgroundColor(this.selectedProfile === profile.id ? C.surfaceMint : C.surface)
                .borderRadius(20).border({ width: 2, color: this.selectedProfile === profile.id ? C.mintDeep : C.border })
                .focusable(true)
                .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
                  disabled: this.buttonDisabledStyle })
                .onClick(() => { this.selectedProfile = profile.id; })
            }, (profile: DemoProfile) => profile.id)
          }.width('100%')

          Column({ space: 10 }) {
            Text('选择演示领域').fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
            Row({ space: 10 }) {
              this.domainButton('ros2_robotics', 'ROS2 移动机器人', 'Topic / QoS');
              this.domainButton('c_programming', 'C语言基础', '语法 / 指针');
            }.width('100%')
          }.width('100%')

          Column({ space: 8 }) {
            Text('演示流程').fontSize(16).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
            Row({ space: 6 }) {
              this.flowChip('1', '诊断', C.sakura);
              Text('→').fontColor(C.muted)
              this.flowChip('2', '检索', C.sky);
              Text('→').fontColor(C.muted)
              this.flowChip('3', '生成', C.lavender);
              Text('→').fontColor(C.muted)
              this.flowChip('4', '审核', C.mint);
            }.width('100%')
          }.width('100%').padding(16).backgroundColor(C.surfaceLavender).borderRadius(20)
            .border({ width: 1, color: C.border })

          if (this.errorMsg.length > 0) {
            Text(this.errorMsg).fontSize(11).fontColor(C.danger).lineHeight(18).width('100%')
          }
          Button('开始完整演示  →').width('100%').height(54).type(ButtonType.Capsule)
            .fontSize(15).fontWeight(FontWeight.Bold).fontColor(C.white).backgroundColor(C.sakuraDeep)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.startDemo())
          Button('返回正式应用').width('100%').height(48).type(ButtonType.Capsule)
            .fontColor(C.skyDeep).backgroundColor(C.surfaceBlue).border({ width: 1, color: C.sky })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().back()).margin({ bottom: 28 })
        }.width('100%').padding({ left: 18, right: 18, top: 20 })
      }.layoutWeight(1)
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  header(): void {
    Stack() {
      Column() {
        Row() {
          Text('SPRING DEMO').fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.sakuraDeep)
          Blank()
          Text('模拟数据专用').fontSize(9).fontColor(C.lavenderDeep)
            .padding({ left: 9, right: 9, top: 5, bottom: 5 }).backgroundColor(C.surfaceLavender).borderRadius(11)
        }.width('100%')
        Text('春日演示中心').fontSize(31).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 20 })
        Text('樱花色、晴空蓝与新叶绿组成的独立演示空间。').fontSize(12).fontColor(C.muted).margin({ top: 7 })
      }.width('100%').padding({ left: 22, right: 22, top: 28, bottom: 24 })
      Circle().width(150).height(150).fill(C.sakura).opacity(0.16).position({ x: '70%', y: -72 })
      Circle().width(92).height(92).fill(C.sky).opacity(0.14).position({ x: '84%', y: 96 })
    }.width('100%').height(184).backgroundColor(C.backgroundBlue)
  }

  @Builder
  domainButton(id: string, title: string, subtitle: string): void {
    Row() {
      Radio({ value: id, group: 'demo_domain' })
        .checked(this.selectedDomain === id)
        .width(26).height(26)
        .onChange((checked: boolean) => {
          if (checked) this.selectedDomain = id;
        })
      Column({ space: 6 }) {
        Text(title).fontSize(13).fontWeight(FontWeight.Bold)
          .fontColor(this.selectedDomain === id ? C.white : C.textStrong)
        Text(subtitle).fontSize(9).fontColor(this.selectedDomain === id ? '#F9FCFF' : C.muted)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ left: 8 })
    }.layoutWeight(1).height(82).padding(14).borderRadius(18)
      .backgroundColor(this.selectedDomain === id ? C.skyDeep : C.surface)
      .border({ width: 2, color: this.selectedDomain === id ? C.skyDeep : C.border })
      .focusable(true)
      .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
        disabled: this.buttonDisabledStyle })
      .onClick(() => { this.selectedDomain = id; })
  }

  @Builder
  flowChip(index: string, label: string, accent: string): void {
    Column({ space: 3 }) {
      Text(index).fontSize(9).fontWeight(FontWeight.Bold).fontColor(accent)
      Text(label).fontSize(10).fontColor(C.textStrong)
    }.layoutWeight(1).padding({ top: 8, bottom: 8 }).backgroundColor(C.surface).borderRadius(12)
      .alignItems(HorizontalAlign.Center)
  }
}
