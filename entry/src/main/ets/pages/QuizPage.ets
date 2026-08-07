/** Diagnostic assessment. Formal mode uses real API; demo mode is explicit via route params. */
import { ApiService, AssessmentQuizItem, QuizOptionDto, AnswerItem, AssessmentItemResult } from '../service/ApiService';
import { DataStore } from '../business/DataStore';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';
import { SelectionStateUtil } from '../utils/SelectionStateUtil';

@Entry
@Component
struct QuizPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private items: AssessmentQuizItem[] = [];
  @State private currentIndex: number = 0;
  // Selection state uses primitive arrays and primitive flags so ArkUI can observe it directly.
  @State private selectedKeys: string[] = [];
  @State private answerDurations: number[] = [];
  @State private currentSelectedKey: string = '';
  @State private answeredCountState: number = 0;
  @State private progressState: number = 0;
  @State private canSubmit: boolean = false;
  @State private loading: boolean = true;
  @State private submitting: boolean = false;
  @State private errorMsg: string = '';
  @State private demoMode: boolean = false;
  @State private reviewItems: AssessmentItemResult[] = [];

  private api: ApiService = new ApiService();
  private learnerId: string = '';
  @State private domainId: string = 'ros2_robotics';
  private assessmentId: string = '';
  private demoProfile: string = '';
  private questionStartTime: number = 0;

  get domainLabel(): string {
    return this.domainId === 'c_programming' ? 'C语言基础' : 'ROS2 Topic';
  }

  get targetGoal(): string {
    return this.domainId === 'c_programming' ? '掌握C语言基础与指针' : '掌握ROS2 Topic话题通信';
  }

  aboutToAppear(): void {
    this.initialize();
  }

  async initialize(): Promise<void> {
    try {
      const params: Object = this.getUIContext().getRouter().getParams();
      this.demoMode = RouteParamUtil.boolean(params, 'demoMode');
      this.demoProfile = RouteParamUtil.string(params, 'demoProfile');
      this.api = this.demoMode ? ApiService.createDemo() : new ApiService();
      this.learnerId = RouteParamUtil.string(params, 'learnerId') ||
        (this.demoMode ? 'learner_demo_guest' : await DataStore.getLearnerId() || '');
      this.domainId = RouteParamUtil.string(params, 'domainId', 'ros2_robotics');
      await DataStore.saveLastDomainId(this.domainId);
      if (this.demoMode && this.demoProfile.length > 0) {
        await DataStore.saveLastDemoProfile(this.demoProfile);
      }
      ContinuationSession.update('pages/QuizPage', this.learnerId);
      if (!this.learnerId) {
        this.getUIContext().getRouter().replaceUrl({ url: 'pages/LearnerProfilePage' });
        return;
      }
      await this.loadAssessment();
    } catch (error) {
      this.loading = false;
      this.errorMsg = `诊断初始化失败：${(error as Error).message}`;
    }
  }

  async loadAssessment(): Promise<void> {
    this.loading = true;
    this.errorMsg = '';
    try {
      const response = await this.api.createAssessment({
        learner_id: this.learnerId,
        domain_id: this.domainId,
        target_goal: this.targetGoal,
      });
      this.assessmentId = response.assessment_id;
      this.items = response.items || [];
      this.currentIndex = 0;
      this.selectedKeys = SelectionStateUtil.empty(this.items.length);
      this.answerDurations = this.items.map((_item: AssessmentQuizItem): number => 0);
      this.currentSelectedKey = '';
      this.answeredCountState = 0;
      this.progressState = 0;
      this.canSubmit = false;
      this.questionStartTime = Date.now();
    } catch (error) {
      this.errorMsg = `题目加载失败：${(error as Error).message}`;
    } finally {
      this.loading = false;
    }
  }

  selectAnswer(key: string): void {
    if (this.currentIndex < 0 || this.currentIndex >= this.items.length || this.submitting) return;
    const duration: number = Math.max(1, Math.floor((Date.now() - this.questionStartTime) / 1000));
    const nextKeys: string[] = SelectionStateUtil.replace(this.selectedKeys, this.currentIndex, key);
    const nextDurations: number[] = this.answerDurations.slice();
    nextDurations[this.currentIndex] = duration;

    // Reassign the complete primitive arrays; this is an observable ArkUI state update.
    this.selectedKeys = nextKeys;
    this.answerDurations = nextDurations;
    this.currentSelectedKey = key;
    this.answeredCountState = SelectionStateUtil.answeredCount(nextKeys);
    this.progressState = this.items.length === 0 ? 0 :
      Math.round(this.answeredCountState / this.items.length * 100);
    this.canSubmit = SelectionStateUtil.allAnswered(nextKeys, this.items.length);
    this.errorMsg = '';
  }

  goTo(index: number): void {
    if (index >= 0 && index < this.items.length) {
      this.currentIndex = index;
      this.currentSelectedKey = this.selectedKeys[index] || '';
      this.questionStartTime = Date.now();
      this.errorMsg = '';
    }
  }

  async submit(): Promise<void> {
    if (this.submitting) return;
    if (!this.canSubmit) {
      const missingIndex: number = SelectionStateUtil.firstUnanswered(this.selectedKeys);
      if (missingIndex >= 0) this.goTo(missingIndex);
      this.errorMsg = `还有 ${this.items.length - this.answeredCountState} 道题未作答，已定位到第一道未答题`;
      return;
    }
    this.submitting = true;
    this.errorMsg = '';
    try {
      const answerItems: AnswerItem[] = this.items.map((item: AssessmentQuizItem, index: number): AnswerItem => {
        return {
          item_id: item.item_id,
          answer: this.selectedKeys[index] || '',
          duration_seconds: this.answerDurations[index] || 1,
        };
      });
      const result = await this.api.submitAssessment(this.assessmentId, {
        answers: answerItems,
      });
      if (!result.item_results || result.item_results.length === 0) {
        throw new Error('服务端未返回逐题判分结果');
      }
      this.reviewItems = result.item_results;
    } catch (error) {
      this.errorMsg = `提交失败：${(error as Error).message}`;
    } finally {
      this.submitting = false;
    }
  }


  async startWorkflow(): Promise<void> {
    if (this.submitting) return;
    this.submitting = true;
    this.errorMsg = '';
    try {
      const workflow = await this.api.createWorkflow({
        learner_id: this.learnerId,
        domain_id: this.domainId,
        assessment_id: this.assessmentId,
        target_goal: this.targetGoal,
      });
      if (!this.demoMode) await DataStore.saveLastWorkflowId(workflow.workflow_id);
      this.getUIContext().getRouter().replaceUrl({
        url: 'pages/WorkflowProcessPage',
        params: {
          workflowId: workflow.workflow_id,
          learnerId: this.learnerId,
          demoMode: this.demoMode,
          demoProfile: this.demoProfile,
          domainId: this.domainId,
        },
      });
    } catch (error) {
      this.errorMsg = `工作流启动失败：${(error as Error).message}`;
      this.submitting = false;
    }
  }

  build(): void {
    Column() {
      this.header();
      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(46).height(46).color(C.skyDeep)
          Text('正在装载诊断题库').fontSize(14).fontColor(C.muted)
        }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.items.length === 0) {
        Column({ space: 14 }) {
          Text('!').fontSize(48).fontColor(C.danger)
          Text(this.errorMsg || '题库为空').fontSize(13).fontColor(C.muted).textAlign(TextAlign.Center)
          Button('重新加载').height(46).type(ButtonType.Capsule).backgroundColor(C.skyDeep).fontColor(C.white)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.loadAssessment())
          if (!this.demoMode) {
            Button('切换到免配置演示').height(46).type(ButtonType.Capsule)
              .backgroundColor(C.surfaceSoft).fontColor(C.sakuraDeep).border({ width: 1, color: C.sakura })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
              .onClick(() => this.getUIContext().getRouter().replaceUrl({
                url: 'pages/QuizPage',
                params: { learnerId: 'learner_demo_guest', domainId: this.domainId, demoMode: true, demoProfile: 'mechanical' },
              }))
          }
        }.width('100%').layoutWeight(1).padding(28).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.reviewItems.length > 0) {
        this.reviewBody();
      } else {
        this.quizBody();
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  header(): void {
    Stack() {
      Column() {
        Row() {
          Button('返回').height(32).type(ButtonType.Capsule).fontSize(10)
            .backgroundColor(C.surface).fontColor(C.skyDeep).border({ width: 1, color: C.border })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.getUIContext().getRouter().back())
          Text(this.demoMode ? 'SPRING DEMO' : 'FORMAL ASSESSMENT').fontSize(10).fontWeight(FontWeight.Bold)
            .fontColor(this.demoMode ? C.sakuraDeep : C.skyDeep).margin({ left: 8 })
          Blank()
          Text(this.demoMode ? '模拟数据' : '真实 API').fontSize(9).fontColor(C.white)
            .padding({ left: 9, right: 9, top: 5, bottom: 5 })
            .backgroundColor(this.demoMode ? C.sakura : C.mintDeep).borderRadius(11)
        }.width('100%')
        Text(`${this.domainLabel} 诊断`).fontSize(29).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 20 })
        Text('选择答案后会立即显示选中状态。').fontSize(12).fontColor(C.muted).margin({ top: 7 })
      }.width('100%').padding({ left: 22, right: 22, top: 27, bottom: 23 })
      Circle().width(165).height(165).fill(C.sakura).opacity(0.14).position({ x: '68%', y: -80 })
      Circle().width(95).height(95).fill(C.sky).opacity(0.14).position({ x: '84%', y: 84 })
    }.width('100%').height(180).backgroundColor(C.backgroundBlue)
  }

  @Builder
  reviewBody(): void {
    Scroll() {
      Column({ space: 12 }) {
        Text('诊断答案回看').fontSize(24).fontWeight(FontWeight.Bold).fontColor(C.textStrong).width('100%')
        Text('先核对错题与解析，再启动个性化资源工作流。').fontSize(12).fontColor(C.muted).width('100%')
        ForEach(this.reviewItems, (item: AssessmentItemResult, index: number) => {
          Column({ space: 8 }) {
            Row() {
              Text(`${index + 1}`).fontSize(11).fontWeight(FontWeight.Bold).fontColor(C.white)
                .width(27).height(27).textAlign(TextAlign.Center)
                .backgroundColor(item.is_correct ? C.mintDeep : C.danger).borderRadius(9)
              Text(item.is_correct ? '回答正确' : '需要复习').fontSize(11)
                .fontColor(item.is_correct ? C.mintDeep : C.danger).margin({ left: 9 })
            }.width('100%')
            Text(item.stem).fontSize(15).fontWeight(FontWeight.Medium).fontColor(C.textStrong).lineHeight(23).width('100%')
            Text(`你的答案：${item.user_answer || '未作答'}　正确答案：${item.correct_answer}`)
              .fontSize(12).fontColor(C.skyDeep).width('100%')
            if (item.explanation) {
              Text(item.explanation).fontSize(11).fontColor(C.muted).lineHeight(19).width('100%')
            }
          }.width('100%').padding(15).backgroundColor(C.surface).borderRadius(16)
            .border({ width: 1, color: item.is_correct ? C.mint : '#F1C4D0' })
        }, (item: AssessmentItemResult) => item.item_id)
        if (this.errorMsg) {
          Text(this.errorMsg).fontSize(11).fontColor(C.danger).width('100%')
        }
        Button(this.submitting ? '启动中…' : '确认并启动 Agent 工作流').width('100%').height(49)
          .type(ButtonType.Capsule).backgroundColor(C.lavenderDeep).fontColor(C.white).fontWeight(FontWeight.Bold)
          .enabled(!this.submitting).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.startWorkflow())
      }.width('100%').padding({ left: 18, right: 18, top: 18, bottom: 30 })
    }.layoutWeight(1)
  }

  @Builder
  quizBody(): void {
    Column() {
      Scroll() {
        Row({ space: 8 }) {
          ForEach(this.items, (item: AssessmentQuizItem, index: number) => {
            Button(`${index + 1}`).width(38).height(38).type(ButtonType.Circle).fontSize(11).fontWeight(FontWeight.Bold)
              .fontColor(index === this.currentIndex || (this.selectedKeys[index] || '').length > 0 ? C.white : C.textStrong)
              .backgroundColor(index === this.currentIndex ? C.skyDeep :
                ((this.selectedKeys[index] || '').length > 0 ? C.mintDeep : C.surface))
              .border({ width: 1.5, color: index === this.currentIndex ? C.skyDeep : C.border })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.goTo(index))
          }, (item: AssessmentQuizItem) => item.item_id)
        }.padding({ left: 18, right: 18, top: 12, bottom: 12 })
      }.width('100%').scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off)
        .backgroundColor(C.surface).border({ width: { bottom: 1 }, color: C.border })

      Scroll() {
        Column({ space: 15 }) {
          Row() {
            Text(`QUESTION ${this.currentIndex + 1}`).fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
            Blank()
            Text(`${this.answeredCountState}/${this.items.length} · ${this.progressState}%`).fontSize(10).fontColor(C.muted)
          }.width('100%')

          Column({ space: 10 }) {
            Text(this.items[this.currentIndex].stem).fontSize(19).fontWeight(FontWeight.Bold)
              .fontColor(C.textStrong).lineHeight(29).width('100%')
            Text(`难度等级 ${this.items[this.currentIndex].difficulty}`).fontSize(10).fontColor(C.lavenderDeep).width('100%')
          }.width('100%').padding(18).backgroundColor(C.surfaceLavender).borderRadius(20)
            .border({ width: 1, color: C.border })

          Column({ space: 10 }) {
            ForEach(this.items[this.currentIndex].options, (option: QuizOptionDto) => {
              Row() {
                Radio({
                  value: option.key,
                  group: `diagnosis_${this.assessmentId}_${this.currentIndex}`,
                })
                  .checked(this.currentSelectedKey === option.key)
                  .width(30).height(30)
                  .onChange((checked: boolean) => {
                    if (checked) this.selectAnswer(option.key);
                  })
                Text(option.key).fontSize(13).fontWeight(FontWeight.Bold)
                  .fontColor(this.currentSelectedKey === option.key ? C.white : C.skyDeep)
                  .width(38).height(38).textAlign(TextAlign.Center)
                  .backgroundColor(this.currentSelectedKey === option.key ? C.skyDeep : C.surfaceBlue).borderRadius(19)
                  .margin({ left: 8 })
                Text(option.text).fontSize(13).fontColor(C.textStrong).lineHeight(20)
                  .layoutWeight(1).margin({ left: 12 })
                Text(this.currentSelectedKey === option.key ? '✓' : '').fontSize(18)
                  .fontColor(C.mintDeep).width(24)
              }.width('100%').height(72).padding(14)
                .backgroundColor(this.currentSelectedKey === option.key ? C.surfaceMint : C.surface)
                .borderRadius(18)
                .border({ width: 2, color: this.currentSelectedKey === option.key ? C.mintDeep : C.border })
                .focusable(true)
                .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
                  disabled: this.buttonDisabledStyle })
                .onClick(() => this.selectAnswer(option.key))
            }, (option: QuizOptionDto) => `${this.currentIndex}_${option.key}`)
          }.width('100%')

          Text(this.canSubmit ? '全部题目已完成，可以提交诊断。' : `还需完成 ${this.items.length - this.answeredCountState} 题`)
            .fontSize(10).fontColor(this.canSubmit ? C.mintDeep : C.muted).width('100%')

          Row({ space: 10 }) {
            Button('← 上一题').layoutWeight(1).height(46).type(ButtonType.Capsule)
              .backgroundColor(C.surfaceBlue).fontColor(C.skyDeep).border({ width: 1, color: C.sky })
              .enabled(this.currentIndex > 0).opacity(this.currentIndex > 0 ? 1.0 : 0.45)
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
              .onClick(() => this.goTo(this.currentIndex - 1))
            Button('下一题 →').layoutWeight(1).height(46).type(ButtonType.Capsule)
              .backgroundColor(C.lavenderDeep).fontColor(C.white)
              .enabled(this.currentIndex < this.items.length - 1)
              .opacity(this.currentIndex < this.items.length - 1 ? 1.0 : 0.45)
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
              .onClick(() => this.goTo(this.currentIndex + 1))
          }.width('100%')

          Button(this.submitting ? '提交中…' : `提交诊断（${this.answeredCountState}/${this.items.length}）`)
            .width('100%').height(50).type(ButtonType.Capsule)
            .backgroundColor(this.canSubmit ? C.sakuraDeep : '#9FAAB5').fontColor(C.white)
            .fontWeight(FontWeight.Bold).enabled(!this.submitting)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.submit())

          if (this.errorMsg) {
            Text(this.errorMsg).fontSize(11).fontColor(C.danger).lineHeight(18).width('100%')
              .padding(14).backgroundColor(C.surfaceSoft).borderRadius(15)
          }
        }.width('100%').padding({ left: 18, right: 18, top: 16, bottom: 30 })
      }.layoutWeight(1)
    }.width('100%').layoutWeight(1)
  }
}
