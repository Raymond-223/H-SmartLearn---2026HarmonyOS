/** Formal learner onboarding. This page always uses the real backend API. */
import { ApiService, LearnerCreateRequest, LearnerPreferences, LearnerDetailResponse } from '../service/ApiService';
import { DataStore } from '../business/DataStore';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';

@Entry
@Component
struct LearnerProfilePage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private education: string = '本科';
  @State private major: string = '';
  @State private targetRole: string = 'ROS2移动机器人开发工程师';
  @State private weeklyHours: number = 6;
  @State private explainStyle: string = '通俗';
  @State private resourcePriority: string = '实践优先';
  @State private submitting: boolean = false;
  @State private errorMsg: string = '';
  @State private privacyAccepted: boolean = false;
  @State private loadingProfile: boolean = false;

  private api: ApiService = new ApiService();
  private domainId: string = 'ros2_robotics';
  private learnerId: string = '';
  private editMode: boolean = false;
  private educations: string[] = ['专科', '本科', '硕士'];
  private explainStyles: string[] = ['通俗', '专业', '类比为主'];
  private resourcePriorities: string[] = ['实践优先', '理论优先', '均衡'];

  aboutToAppear(): void {
    const params: Object = this.getUIContext().getRouter().getParams();
    this.domainId = RouteParamUtil.string(params, 'domainId') || 'ros2_robotics';
    this.learnerId = RouteParamUtil.string(params, 'learnerId');
    this.editMode = RouteParamUtil.boolean(params, 'editMode');
    if (this.domainId === 'c_programming') {
      this.targetRole = 'C语言与嵌入式开发工程师';
    }
    ContinuationSession.update('pages/LearnerProfilePage');
    if (this.editMode && this.learnerId.length > 0) {
      this.loadExistingProfile();
    }
  }

  async loadExistingProfile(): Promise<void> {
    this.loadingProfile = true;
    this.errorMsg = '';
    try {
      const profile: LearnerDetailResponse = await this.api.getLearner(this.learnerId);
      this.education = profile.education || this.education;
      this.major = profile.major || '';
      this.targetRole = profile.target_role || this.targetRole;
      this.weeklyHours = profile.weekly_hours || this.weeklyHours;
      this.explainStyle = profile.preferences.explanation_style || this.explainStyle;
      this.resourcePriority = profile.preferences.resource_priority || this.resourcePriority;
      this.privacyAccepted = true;
    } catch (error) {
      this.errorMsg = `读取现有画像失败：${(error as Error).message}`;
    } finally {
      this.loadingProfile = false;
    }
  }

  build(): void {
    Column() {
      this.header();
      Scroll() {
        Column({ space: 15 }) {
          Text(this.editMode ? '更新正式学习画像' : '建立正式学习画像').fontSize(20).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
          Text(this.editMode ? '修改后将更新原学习者，不会创建重复账号。' : '正式流程只连接真实 FastAPI；网络不可达时会明确提示，不会自动替换成模拟结果。')
            .fontSize(11).fontColor(C.muted).lineHeight(18).width('100%')

          this.educationChoiceCard();
          this.majorInputCard();
          this.targetRoleInputCard();

          Column({ space: 10 }) {
            Row() {
              Text('每周学习时间').fontSize(14).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
              Blank()
              Text(`${this.weeklyHours} 小时`).fontSize(16).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
            }.width('100%')
            Slider({ value: this.weeklyHours, min: 1, max: 30, step: 1 })
              .width('100%').blockColor(C.sakura).selectedColor(C.sky).trackColor('#E6EEF5')
              .onChange((value: number) => { this.weeklyHours = Math.round(value); })
          }.width('100%').padding(16).backgroundColor(C.surfaceBlue).borderRadius(20)
            .border({ width: 1, color: C.border })

          this.explainStyleChoiceCard();
          this.resourcePriorityChoiceCard();

          Button() {
            Row() {
              Text(this.privacyAccepted ? '✓' : '○').fontSize(22)
                .fontColor(this.privacyAccepted ? C.mintDeep : C.muted)
              Column({ space: 4 }) {
                Text('同意画像用于个性化学习').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
                Text('只上传完成能力适配所需的信息。').fontSize(10).fontColor(C.muted)
              }.layoutWeight(1).alignItems(HorizontalAlign.Start).margin({ left: 10 })
              Text(this.privacyAccepted ? '已同意' : '未同意').fontSize(10)
                .fontColor(this.privacyAccepted ? C.mintDeep : C.muted)
            }.width('100%').padding(15)
          }.width('100%').height(70).type(ButtonType.Normal)
            .backgroundColor(this.privacyAccepted ? C.surfaceMint : C.surface)
            .borderRadius(20).border({ width: 1.5, color: this.privacyAccepted ? C.mint : C.border })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
              disabled: this.buttonDisabledStyle })
            .onClick(() => { this.privacyAccepted = !this.privacyAccepted; this.errorMsg = ''; })

          if (this.errorMsg) {
            Text(this.errorMsg).fontSize(11).fontColor(C.danger).lineHeight(18).width('100%')
              .padding(14).backgroundColor(C.surfaceSoft).borderRadius(15)
              .border({ width: 1, color: '#F3C8D3' })
          }

          Button(this.submitting ? (this.editMode ? '正在保存画像…' : '正在创建画像…') : (this.editMode ? '保存画像并返回首页' : '连接真实服务并开始诊断  →'))
            .width('100%').height(54).type(ButtonType.Capsule).fontWeight(FontWeight.Bold)
            .fontColor(C.white).backgroundColor(C.skyDeep)
            .enabled(!this.submitting && !this.loadingProfile && this.privacyAccepted)
            .opacity(this.submitting || this.loadingProfile || !this.privacyAccepted ? 0.5 : 1.0)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.onSubmit())

          Button('🌸 进入春日演示中心').width('100%').height(50).type(ButtonType.Capsule)
            .fontWeight(FontWeight.Bold).fontColor(C.sakuraDeep).backgroundColor(C.surfaceSoft)
            .border({ width: 1.5, color: C.sakura })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/DemoCenterPage' }))

          Button('真实 API 连接设置').width('100%').height(46).type(ButtonType.Capsule)
            .fontColor(C.skyDeep).backgroundColor(C.surfaceBlue).border({ width: 1, color: C.sky })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/ConnectionPage' })).margin({ bottom: 28 })
        }.width('100%').padding({ left: 18, right: 18, top: 20 })
      }.layoutWeight(1)
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  header(): void {
    Stack() {
      Column() {
        Text('H-SMARTLEARN · FORMAL').fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
        Text('在春风里开始学习').fontSize(31).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 20 })
        Text('晴空蓝 × 樱花粉 × 新叶绿').fontSize(13).fontColor(C.sakuraDeep).margin({ top: 7 })
      }.width('100%').padding({ left: 22, right: 22, top: 30, bottom: 24 })
      Circle().width(170).height(170).fill(C.sky).opacity(0.15).position({ x: '66%', y: -85 })
      Circle().width(100).height(100).fill(C.sakura).opacity(0.16).position({ x: '82%', y: 88 })
    }.width('100%').height(180).backgroundColor(C.backgroundBlue)
  }

  @Builder
  majorInputCard(): void {
    Column({ space: 9 }) {
      Text('专业背景').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      TextInput({ placeholder: '例如：机械工程、计算机科学', text: this.major })
        .width('100%').height(48).fontSize(14).fontColor(C.textStrong).placeholderColor('#A3AFBB')
        .padding({ left: 14, right: 14 }).backgroundColor(C.surface).borderRadius(14)
        .border({ width: 1.5, color: C.border })
        .onChange((input: string) => { this.major = input; this.errorMsg = ''; })
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  @Builder
  targetRoleInputCard(): void {
    Column({ space: 9 }) {
      Text('目标岗位').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      TextInput({ placeholder: '例如：ROS2开发工程师', text: this.targetRole })
        .width('100%').height(48).fontSize(14).fontColor(C.textStrong).placeholderColor('#A3AFBB')
        .padding({ left: 14, right: 14 }).backgroundColor(C.surface).borderRadius(14)
        .border({ width: 1.5, color: C.border })
        .onChange((input: string) => { this.targetRole = input; this.errorMsg = ''; })
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  @Builder
  educationChoiceCard(): void {
    Column({ space: 11 }) {
      Text('学历背景').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      Row({ space: 8 }) {
        ForEach(this.educations, (option: string) => {
          Row({ space: 6 }) {
            Radio({ value: option, group: 'profile_education' })
              .checked(this.education === option)
              .width(24).height(24)
              .onChange((checked: boolean) => {
                if (checked) { this.education = option; this.errorMsg = ''; }
              })
            Text(option).fontSize(11)
              .fontWeight(this.education === option ? FontWeight.Bold : FontWeight.Regular)
              .fontColor(this.education === option ? C.white : C.textStrong)
          }.layoutWeight(1).height(46).justifyContent(FlexAlign.Center)
            .backgroundColor(this.education === option ? C.skyDeep : C.surface)
            .borderRadius(14).border({ width: 2, color: this.education === option ? C.skyDeep : C.border })
            .focusable(true)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
              disabled: this.buttonDisabledStyle })
            .onClick(() => { this.education = option; this.errorMsg = ''; })
        }, (option: string) => option)
      }.width('100%')
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  @Builder
  explainStyleChoiceCard(): void {
    Column({ space: 11 }) {
      Text('讲解风格').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      Row({ space: 8 }) {
        ForEach(this.explainStyles, (option: string) => {
          Row({ space: 5 }) {
            Radio({ value: option, group: 'profile_explain_style' })
              .checked(this.explainStyle === option)
              .width(22).height(22)
              .onChange((checked: boolean) => {
                if (checked) { this.explainStyle = option; this.errorMsg = ''; }
              })
            Text(option).fontSize(10)
              .fontWeight(this.explainStyle === option ? FontWeight.Bold : FontWeight.Regular)
              .fontColor(this.explainStyle === option ? C.white : C.textStrong)
          }.layoutWeight(1).height(48).justifyContent(FlexAlign.Center)
            .backgroundColor(this.explainStyle === option ? C.sakuraDeep : C.surface)
            .borderRadius(14).border({ width: 2, color: this.explainStyle === option ? C.sakuraDeep : C.border })
            .focusable(true)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
              disabled: this.buttonDisabledStyle })
            .onClick(() => { this.explainStyle = option; this.errorMsg = ''; })
        }, (option: string) => option)
      }.width('100%')
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  @Builder
  resourcePriorityChoiceCard(): void {
    Column({ space: 11 }) {
      Text('资源偏好').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
      Row({ space: 8 }) {
        ForEach(this.resourcePriorities, (option: string) => {
          Row({ space: 5 }) {
            Radio({ value: option, group: 'profile_resource_priority' })
              .checked(this.resourcePriority === option)
              .width(22).height(22)
              .onChange((checked: boolean) => {
                if (checked) { this.resourcePriority = option; this.errorMsg = ''; }
              })
            Text(option).fontSize(10)
              .fontWeight(this.resourcePriority === option ? FontWeight.Bold : FontWeight.Regular)
              .fontColor(this.resourcePriority === option ? C.white : C.textStrong)
          }.layoutWeight(1).height(48).justifyContent(FlexAlign.Center)
            .backgroundColor(this.resourcePriority === option ? C.mintDeep : C.surface)
            .borderRadius(14).border({ width: 2, color: this.resourcePriority === option ? C.mintDeep : C.border })
            .focusable(true)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
              disabled: this.buttonDisabledStyle })
            .onClick(() => { this.resourcePriority = option; this.errorMsg = ''; })
        }, (option: string) => option)
      }.width('100%')
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(20)
      .border({ width: 1, color: C.border })
  }

  async onSubmit(): Promise<void> {
    if (!this.privacyAccepted) {
      this.errorMsg = '请先点击并同意画像数据使用说明';
      return;
    }
    if (!this.targetRole.trim()) {
      this.errorMsg = '请填写目标岗位';
      return;
    }
    this.submitting = true;
    this.errorMsg = '';
    try {
      const preferences: LearnerPreferences = {
        explanation_style: this.explainStyle,
        resource_priority: this.resourcePriority,
      };
      const request: LearnerCreateRequest = {
        education: this.education,
        major: this.major.trim() || undefined,
        target_role: this.targetRole.trim(),
        weekly_hours: this.weeklyHours,
        preferences: preferences,
      };
      if (this.editMode && this.learnerId.length > 0) {
        await this.api.updateLearner(this.learnerId, request);
        await DataStore.saveLearnerId(this.learnerId);
        await DataStore.saveLastDomainId(this.domainId);
        this.getUIContext().getRouter().replaceUrl({ url: 'pages/Index' });
      } else {
        const response = await this.api.createLearner(request);
        await DataStore.saveLearnerId(response.learner_id);
        await DataStore.saveLastDomainId(this.domainId);
        this.getUIContext().getRouter().replaceUrl({
          url: 'pages/QuizPage',
          params: { learnerId: response.learner_id, domainId: this.domainId, demoMode: false },
        });
      }
    } catch (error) {
      this.errorMsg = `真实服务连接失败：${(error as Error).message}`;
      this.submitting = false;
    }
  }
}
