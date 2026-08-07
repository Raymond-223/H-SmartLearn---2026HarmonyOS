/** Interactive personalized resource bundle and feedback loop. */
import {
  ApiService, ResourceResponse, LectureSection, PracticeStep,
  GradedTestItem, GradedTestOption, CitationItem, ResourceTestAnswer,
  ResourceTestItemResult, PracticeStepResult,
} from '../service/ApiService';
import { DataStore } from '../business/DataStore';
import { HarmonyNotificationService } from '../integration/HarmonyNotificationService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';
import { SelectionStateUtil } from '../utils/SelectionStateUtil';
import { LogUtil } from '../utils/LogUtil';

const TAG: string = 'ResourceViewPage';

interface PendingFeedback {
  resource_id: string;
  correct_rate: number;
  practice_score: number;
  subjective_difficulty: string;
  error_tags: string;
  practice_results: PracticeStepResult[];
  timestamp: number;
}

const TABS: string[] = ['讲义', '实操', '测试', '溯源', '笔记'];
const DIFFICULTIES: string[] = ['太简单', '合适', '太难'];

@Entry
@Component
struct ResourceViewPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private resource: ResourceResponse | null = null;
  @State private loading: boolean = true;
  @State private errorMsg: string = '';
  @State private currentTab: number = 0;
  @State private showFeedback: boolean = false;
  @State private feedbackSubmitted: boolean = false;
  @State private feedbackMessage: string = '';
  @State private correctRate: number = 0;
  @State private practiceScore: number = 0;
  @State private subjectiveDifficulty: number = 1;
  @State private errorTags: string = '';
  @State private submitting: boolean = false;
  @State private demoMode: boolean = false;
  // Primitive selection state is directly bound to ArkUI controls.
  @State private testSelectedKeys: string[] = [];
  @State private testAnsweredCountState: number = 0;
  @State private canSubmitTest: boolean = false;
  @State private testResults: ResourceTestItemResult[] = [];
  @State private testSubmitted: boolean = false;
  @State private testSubmitting: boolean = false;
  @State private practiceStatuses: string[] = [];
  @State private nextWorkflowId: string = '';
  @State private feedbackRecorded: boolean = false;
  @State private noteText: string = '';
  @State private noteSaved: boolean = false;
  @State private bookmarked: boolean = false;

  private api: ApiService = new ApiService();
  private workflowId: string = '';
  private learnerId: string = '';
  private resourceId: string = '';
  private demoProfile: string = '';

  aboutToAppear(): void {
    this.initialize();
  }

  async initialize(): Promise<void> {
    const params: Object = this.getUIContext().getRouter().getParams();
    this.demoMode = RouteParamUtil.boolean(params, 'demoMode');
    this.demoProfile = RouteParamUtil.string(params, 'demoProfile');
    this.api = this.demoMode ? ApiService.createDemo() : new ApiService();
    this.workflowId = RouteParamUtil.string(params, 'workflowId');
    this.learnerId = RouteParamUtil.string(params, 'learnerId') ||
      (this.demoMode ? 'learner_demo_guest' : await DataStore.getLearnerId() || '');
    this.resourceId = RouteParamUtil.string(params, 'resourceId') ||
      (this.demoMode ? '' : await DataStore.getLastResourceId() || '');
    ContinuationSession.update('pages/ResourceViewPage', this.learnerId, this.workflowId, this.resourceId);
    if (!this.resourceId) {
      this.loading = false;
      this.errorMsg = '暂无可用资源，请先完成诊断';
      return;
    }
    await this.loadResource();
  }

  async loadResource(): Promise<void> {
    this.loading = true;
    this.errorMsg = '';
    try {
      this.resource = await this.api.getResource(this.resourceId);
      const testItems: GradedTestItem[] = this.resource?.graded_test?.items || [];
      const practiceSteps: PracticeStep[] = this.resource?.practice_guide?.steps || [];
      this.testSelectedKeys = SelectionStateUtil.empty(testItems.length);
      this.testAnsweredCountState = 0;
      this.canSubmitTest = false;
      this.testResults = [];
      this.testSubmitted = false;
      this.practiceStatuses = practiceSteps.map((_step: PracticeStep): string => '');
      this.correctRate = 0;
      this.practiceScore = 0;
      this.feedbackRecorded = this.resource.feedback_recorded === true;
      this.nextWorkflowId = this.resource.next_workflow_id || '';
      this.feedbackMessage = this.resource.feedback_reason || '';
      this.noteText = await DataStore.getResourceNote(this.resource.resource_id);
      this.bookmarked = await DataStore.getResourceBookmark(this.resource.resource_id);
      this.noteSaved = this.noteText.length > 0;
      if (!this.demoMode && !this.feedbackRecorded && await DataStore.hasPendingFeedback(this.resource.resource_id)) {
        this.feedbackRecorded = true;
        this.feedbackMessage = '该资源反馈已离线缓存，恢复网络后会自动补交';
      }
      if (!this.demoMode) await DataStore.saveLastResourceId(this.resource.resource_id);
      await DataStore.saveLastDomainId(this.getDomainId());
    } catch (error) {
      this.errorMsg = `资源加载失败：${(error as Error).message}`;
    } finally {
      this.loading = false;
    }
  }

  getDifficultyLabel(): string {
    const raw: string = this.resource?.difficulty || 'basic';
    if (raw === 'advanced') return '进阶';
    if (raw === 'intermediate') return '中等';
    return '基础';
  }

  getReviewScore(): number {
    const scores = this.resource?.review?.scores;
    if (!scores) return 0;
    const values: number[] = [
      scores.factuality ?? 0,
      scores.evidence_coverage ?? 0,
      scores.difficulty_match ?? 0,
      scores.actionability ?? 0,
    ];
    return Math.round(values.reduce((sum: number, value: number) => sum + value, 0) / values.length * 100);
  }

  splitErrorTags(): string[] {
    const result: string[] = [];
    for (const value of this.errorTags.split(',')) {
      const trimmed: string = value.trim();
      if (trimmed) result.push(trimmed);
    }
    return result;
  }

  getDomainId(): string {
    return (this.resource?.target_skill || '').startsWith('c_') ? 'c_programming' : 'ros2_robotics';
  }

  getRuntimeTag(): string {
    return this.getDomainId() === 'c_programming' ? 'C17 / GCC' : 'ROS2 HUMBLE';
  }

  getTestAnswer(itemId: string): string {
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    const index: number = items.findIndex((item: GradedTestItem): boolean => item.id === itemId);
    return index >= 0 ? (this.testSelectedKeys[index] || '') : '';
  }

  getTestResult(itemId: string): ResourceTestItemResult | null {
    const result: ResourceTestItemResult | undefined = this.testResults.find(
      (item: ResourceTestItemResult): boolean => item.item_id === itemId);
    return result || null;
  }

  optionBackground(itemIndex: number, optionKey: string): string {
    const selected: boolean = (this.testSelectedKeys[itemIndex] || '') === optionKey;
    if (!this.testSubmitted) return selected ? C.surfaceMint : C.surface;
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    const itemId: string = itemIndex < items.length ? items[itemIndex].id : '';
    const result: ResourceTestItemResult | null = this.getTestResult(itemId);
    if (result !== null && optionKey === result.correct_answer) return C.surfaceMint;
    if (result !== null && selected && !result.is_correct) return C.surfaceSoft;
    return C.surface;
  }

  optionBorder(itemIndex: number, optionKey: string): string {
    const selected: boolean = (this.testSelectedKeys[itemIndex] || '') === optionKey;
    if (!this.testSubmitted) return selected ? C.mintDeep : C.border;
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    const itemId: string = itemIndex < items.length ? items[itemIndex].id : '';
    const result: ResourceTestItemResult | null = this.getTestResult(itemId);
    if (result !== null && optionKey === result.correct_answer) return C.mintDeep;
    if (result !== null && selected && !result.is_correct) return C.danger;
    return C.border;
  }

  buildPracticeResults(): PracticeStepResult[] {
    const steps: PracticeStep[] = this.resource?.practice_guide?.steps || [];
    return steps.map((step: PracticeStep, index: number): PracticeStepResult => {
      return { order: step.order, success: this.practiceStatuses[index] === 'success' };
    });
  }

  selectTestAnswer(itemIndex: number, answer: string): void {
    if (this.testSubmitted || itemIndex < 0 || itemIndex >= this.testSelectedKeys.length) return;
    const next: string[] = SelectionStateUtil.replace(this.testSelectedKeys, itemIndex, answer);
    this.testSelectedKeys = next;
    this.testAnsweredCountState = SelectionStateUtil.answeredCount(next);
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    this.canSubmitTest = SelectionStateUtil.allAnswered(next, items.length);
    this.errorMsg = '';
  }

  allTestAnswered(): boolean {
    return this.canSubmitTest;
  }

  async submitResourceTest(): Promise<void> {
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    if (!this.resource || !this.allTestAnswered() || this.testSubmitting) {
      this.errorMsg = '请完成全部测试题后再提交';
      return;
    }
    this.testSubmitting = true;
    this.errorMsg = '';
    try {
      const answers: ResourceTestAnswer[] = items.map((item: GradedTestItem, index: number): ResourceTestAnswer => {
        return { item_id: item.id, answer: this.testSelectedKeys[index] || '' };
      });
      const result = await this.api.submitResourceTest(this.resource.resource_id, answers);
      this.correctRate = Math.round(result.score * 100);
      this.errorTags = result.error_tags.join(',');
      this.testResults = result.item_results;
      this.testSubmitted = true;
    } catch (error) {
      this.errorMsg = `测试提交失败：${(error as Error).message}`;
    } finally {
      this.testSubmitting = false;
    }
  }

  retryResourceTest(): void {
    const items: GradedTestItem[] = this.resource?.graded_test?.items || [];
    this.testSelectedKeys = SelectionStateUtil.empty(items.length);
    this.testAnsweredCountState = 0;
    this.canSubmitTest = false;
    this.testResults = [];
    this.testSubmitted = false;
    this.correctRate = 0;
    this.errorMsg = '';
  }

  markPractice(stepIndex: number, success: boolean): void {
    if (stepIndex < 0 || stepIndex >= this.practiceStatuses.length) return;
    const next: string[] = this.practiceStatuses.slice();
    next[stepIndex] = success ? 'success' : 'failed';
    this.practiceStatuses = next;
    const successCount: number = next.filter((value: string): boolean => value === 'success').length;
    this.practiceScore = next.length > 0 ? Math.round(successCount * 100 / next.length) : 0;
    this.errorMsg = '';
  }

  practiceAllMarked(): boolean {
    return this.practiceStatuses.length > 0 &&
      this.practiceStatuses.every((value: string): boolean => value === 'success' || value === 'failed');
  }

  openFeedbackPanel(): void {
    if (this.feedbackRecorded) {
      this.errorMsg = '当前资源反馈已提交，不会重复更新掌握度';
      return;
    }
    if (!this.testSubmitted) {
      this.currentTab = 2;
      this.errorMsg = '请先完成并提交分阶测试';
      return;
    }
    if (!this.practiceAllMarked()) {
      this.currentTab = 1;
      this.errorMsg = '请逐项确认实操结果后再提交反馈';
      return;
    }
    this.errorMsg = '';
    this.showFeedback = true;
  }

  async submitFeedback(): Promise<void> {
    if (!this.resource || this.submitting) return;
    this.submitting = true;
    const difficultyCodes: string[] = ['too_easy', 'appropriate', 'too_hard'];
    try {
      const response = await this.api.submitFeedback(this.resource.resource_id, {
        correct_rate: this.correctRate / 100,
        practice_score: this.practiceScore / 100,
        practice_results: this.buildPracticeResults(),
        subjective_difficulty: difficultyCodes[this.subjectiveDifficulty],
        error_tags: this.splitErrorTags(),
      });
      this.feedbackMessage = response.reason || '反馈已记录，学习路径已更新';
      this.nextWorkflowId = response.next_workflow_id || '';
      this.feedbackRecorded = true;
      this.feedbackSubmitted = true;
      if (this.nextWorkflowId && !this.demoMode) {
        await DataStore.saveLastWorkflowId(this.nextWorkflowId);
      }
    } catch (error) {
      if (this.demoMode) {
        this.errorMsg = `演示反馈失败：${(error as Error).message}`;
        this.feedbackMessage = '';
        this.feedbackSubmitted = false;
        return;
      }
      const pending: PendingFeedback = {
        resource_id: this.resource.resource_id,
        correct_rate: this.correctRate / 100,
        practice_score: this.practiceScore / 100,
        practice_results: this.buildPracticeResults(),
        subjective_difficulty: difficultyCodes[this.subjectiveDifficulty],
        error_tags: this.errorTags,
        timestamp: Date.now(),
      };
      await DataStore.savePendingFeedback(JSON.stringify(pending));
      try {
        await HarmonyNotificationService.publishOfflineQueued();
      } catch (notificationError) {
        LogUtil.warn(TAG, `Unable to publish offline notification: ${(notificationError as Error).message}`);
      }
      this.feedbackMessage = '当前离线，反馈已安全缓存；恢复网络后会自动补交';
      this.feedbackRecorded = true;
      this.feedbackSubmitted = true;
    } finally {
      this.submitting = false;
    }
  }


  async saveNote(): Promise<void> {
    if (!this.resource) return;
    await DataStore.saveResourceNote(this.resource.resource_id, this.noteText.trim());
    this.noteText = this.noteText.trim();
    this.noteSaved = true;
  }

  async toggleBookmark(): Promise<void> {
    if (!this.resource) return;
    this.bookmarked = !this.bookmarked;
    await DataStore.saveResourceBookmark(this.resource.resource_id, this.bookmarked);
  }

  openNextWorkflow(): void {
    if (!this.nextWorkflowId) return;
    try {
      this.getUIContext().getRouter().replaceUrl({
        url: 'pages/WorkflowProcessPage',
        params: {
          workflowId: this.nextWorkflowId,
          learnerId: this.learnerId,
          demoMode: this.demoMode,
          demoProfile: this.demoProfile,
          domainId: this.getDomainId(),
        },
      });
    } catch (error) {
      this.errorMsg = `打开下一学习任务失败：${(error as Error).message}`;
    }
  }

  build(): void {
    Column() {
      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(46).height(46).color(C.sky)
          Text('正在解锁个性化资源').fontSize(14).fontColor(C.muted)
          Button('取消并返回').height(42).type(ButtonType.Capsule).backgroundColor(C.surfaceBlue).fontColor(C.skyDeep)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.getUIContext().getRouter().back())
        }.width('100%').height('100%').justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (!this.resource) {
        Column({ space: 14 }) {
          Text('◇').fontSize(54).fontColor(C.lavenderDeep)
          Text(this.errorMsg).fontSize(13).fontColor(C.muted).textAlign(TextAlign.Center)
          Button('重新加载资源').backgroundColor(C.sky).fontColor('#06121C').borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.loadResource())
          Button('重新诊断').backgroundColor(C.surfaceBlue).fontColor(C.skyDeep).borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().replaceUrl({
              url: 'pages/QuizPage',
              params: { learnerId: this.learnerId, domainId: this.getDomainId(), demoMode: this.demoMode,
                demoProfile: this.demoProfile },
            }))
          if (!this.demoMode) {
            Button('进入免配置演示').backgroundColor(C.surfaceSoft).fontColor(C.sakuraDeep).borderRadius(14)
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
              .onClick(() => this.getUIContext().getRouter().replaceUrl({
                url: 'pages/DemoCenterPage'
              }))
          }
        }.width('100%').height('100%').padding(30).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.feedbackSubmitted) {
        this.buildFeedbackResult();
      } else {
        this.buildResource();
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  buildFeedbackResult(): void {
    Column({ space: 14 }) {
      Text('✓').fontSize(64).fontColor(C.mintDeep)
      Text('反馈已进入决策闭环').fontSize(21).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
      Text(this.feedbackMessage).fontSize(13).fontColor(C.muted).lineHeight(20).textAlign(TextAlign.Center)
      if (this.nextWorkflowId) {
        Button('进入下一阶段学习').width(230).height(48).type(ButtonType.Capsule)
          .backgroundColor(C.lavenderDeep).fontColor(C.white).fontWeight(FontWeight.Bold)
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openNextWorkflow())
      }
      Button('继续查看当前资源').width(230).height(44).type(ButtonType.Capsule)
        .backgroundColor(C.surfaceBlue).fontColor(C.skyDeep).border({ width: 1, color: C.sky })
        .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.feedbackSubmitted = false; this.showFeedback = false; })
      Button(this.demoMode ? '查看模拟学情报告' : '查看学情报告').width(230).height(44).type(ButtonType.Capsule)
        .backgroundColor(C.surfaceMint).fontColor(C.mintDeep).border({ width: 1, color: C.mint })
        .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().replaceUrl({
          url: 'pages/ReportPage',
          params: { learnerId: this.learnerId, domainId: this.getDomainId(), demoMode: this.demoMode,
            demoProfile: this.demoProfile },
        }))
      Button(this.demoMode ? '返回春日演示中心' : '返回首页').width(230).height(44).type(ButtonType.Capsule)
        .backgroundColor(C.surfaceSoft).fontColor(C.sakuraDeep).border({ width: 1, color: C.sakura })
        .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().replaceUrl({ url: this.demoMode ? 'pages/DemoCenterPage' : 'pages/Index' }))
    }.width('100%').height('100%').padding(32).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
  }

  @Builder
  buildResource(): void {
    Column() {
      Stack() {
        Rect().width('100%').height(248)
          .linearGradient({ angle: 138, colors: [['#F2FAFF', 0.0], ['#FFF3F7', 0.55], ['#F6F1FF', 1.0]] })
        Circle().width(220).height(220).fill(C.sky).opacity(0.25).position({ x: '59%', y: -110 })
        Circle().width(125).height(125).fill(C.sakura).opacity(0.20).position({ x: '82%', y: 108 })
        Column() {
          Row() {
            Text(this.demoMode ? 'SPRING DEMO / VERIFIED' : 'REAL API / VERIFIED').fontSize(9)
              .fontColor(C.skyDeep).fontWeight(FontWeight.Bold)
            Blank()
            Text(`审核 ${this.getReviewScore()}%`).fontSize(9).fontColor(C.mintDeep)
              .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor(C.surfaceMint).borderRadius(11)
          }.width('100%')
          Text(this.resource?.lecture?.title || '个性化学习资源')
            .fontSize(23).fontWeight(FontWeight.Bold).fontColor(C.textStrong).maxLines(2).margin({ top: 25 })
          Text('讲义 · 可验证实操 · 可作答测试 · 证据链 · 本地笔记').fontSize(10).fontColor(C.muted).margin({ top: 8 })
          Row({ space: 8 }) {
            Text(this.getDifficultyLabel()).fontSize(9).fontColor(C.white).backgroundColor(C.skyDeep)
              .padding({ left: 9, right: 9, top: 5, bottom: 5 }).borderRadius(11)
            Text(this.getRuntimeTag()).fontSize(9).fontColor(C.lavenderDeep).backgroundColor(C.surfaceLavender)
              .padding({ left: 9, right: 9, top: 5, bottom: 5 }).borderRadius(11)
            Text(`${this.resource?.citations.length || 0} EVIDENCE`).fontSize(9).fontColor(C.mintDeep)
              .backgroundColor(C.surfaceMint).padding({ left: 9, right: 9, top: 5, bottom: 5 }).borderRadius(11)
          }.margin({ top: 18 })
        }.width('100%').padding({ left: 20, right: 20, top: 25, bottom: 20 })
      }.width('100%').height(248)

      Row({ space: 6 }) {
        ForEach(TABS, (label: string, index: number) => {
          Button(label).layoutWeight(1).height(42).type(ButtonType.Normal).fontSize(12)
            .fontWeight(this.currentTab === index ? FontWeight.Bold : FontWeight.Regular)
            .fontColor(this.currentTab === index ? C.white : C.textStrong)
            .backgroundColor(this.currentTab === index ? C.skyDeep : C.surface)
            .borderRadius(14).border({ width: 1, color: this.currentTab === index ? C.skyDeep : C.border })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.currentTab = index; this.showFeedback = false; this.errorMsg = ''; })
        }, (label: string) => label)
      }.width('100%').padding({ left: 12, right: 12, top: 10, bottom: 10 })
        .backgroundColor(C.surfaceSoft).border({ width: { bottom: 1 }, color: C.border })

      Scroll() {
        Column() {
          if (this.errorMsg) {
            Text(this.errorMsg).fontSize(11).fontColor(C.danger).lineHeight(18).width('100%')
              .padding(12).backgroundColor(C.surfaceSoft).borderRadius(13).margin({ bottom: 12 })
          }
          if (this.currentTab === 0) {
            this.buildLecture();
          } else if (this.currentTab === 1) {
            this.buildPractice();
          } else if (this.currentTab === 2) {
            this.buildTest();
          } else if (this.currentTab === 3) {
            this.buildCitations();
          } else {
            this.buildNotes();
          }

          if (this.showFeedback) {
            this.buildFeedbackPanel();
          } else if (this.feedbackRecorded) {
            this.buildRecordedActions();
          } else {
            Button('完成学习并提交反馈').width('100%').height(50)
              .backgroundColor(C.lavenderDeep).fontColor(C.white).fontWeight(FontWeight.Bold)
              .borderRadius(15).margin({ top: 18 }).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openFeedbackPanel())
          }
        }.padding({ left: 18, right: 18, top: 17, bottom: 30 })
      }.layoutWeight(1)
    }.width('100%').height('100%')
  }

  @Builder
  sectionTitle(kicker: string, title: string): void {
    Column({ space: 4 }) {
      Text(kicker).fontSize(9).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
      Text(title).fontSize(19).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
    }.width('100%').margin({ bottom: 14 })
  }

  @Builder
  buildLecture(): void {
    Column() {
      this.sectionTitle('LECTURE', this.resource?.lecture?.title || '讲义');
      ForEach(this.resource?.lecture?.sections || [], (section: LectureSection, index: number) => {
        Column() {
          Row() {
            Text(`${index + 1}`).fontSize(11).fontWeight(FontWeight.Bold).fontColor(C.white)
              .width(26).height(26).textAlign(TextAlign.Center).backgroundColor(C.skyDeep).borderRadius(8)
            Text(section.heading).fontSize(15).fontWeight(FontWeight.Medium).fontColor(C.textStrong).margin({ left: 10 })
          }.width('100%')
          Text(section.content).fontSize(13).fontColor(C.muted).lineHeight(22).width('100%').margin({ top: 12 })
          if ((section.citations || []).length > 0) {
            Text(`证据 · ${(section.citations || []).join(' / ')}`).fontSize(9).fontColor(C.mintDeep)
              .margin({ top: 10 }).width('100%')
          }
        }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(16)
          .border({ width: 1, color: C.border }).margin({ bottom: 11 })
      })
    }.width('100%')
  }

  @Builder
  buildPractice(): void {
    Column() {
      this.sectionTitle('PRACTICE', this.resource?.practice_guide?.title || '实操指南');
      Text('长按命令文本可复制；每一步必须选择“符合预期”或“未达预期”。')
        .fontSize(10).fontColor(C.muted).width('100%').margin({ bottom: 10 })
      if ((this.resource?.practice_guide?.prerequisites || []).length > 0) {
        Text(`前置条件 · ${(this.resource?.practice_guide?.prerequisites || []).join('、')}`)
          .fontSize(11).fontColor(C.lavenderDeep).width('100%').padding(12)
          .backgroundColor(C.surfaceLavender).borderRadius(12).margin({ bottom: 12 })
      }
      ForEach(this.resource?.practice_guide?.steps || [], (step: PracticeStep, index: number) => {
        Column() {
          Row() {
            Text(`${step.order}`).fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.white)
              .width(30).height(30).textAlign(TextAlign.Center).backgroundColor(C.skyDeep).borderRadius(9)
            Text(step.title).fontSize(15).fontWeight(FontWeight.Medium).fontColor(C.textStrong).margin({ left: 10 })
            Blank()
            if (this.practiceStatuses[index] === 'success') {
              Text('✓').fontSize(18).fontColor(C.mintDeep)
            } else if (this.practiceStatuses[index] === 'failed') {
              Text('!').fontSize(18).fontColor(C.danger)
            }
          }.width('100%')
          Text(step.command).fontSize(12).fontColor('#16344A').lineHeight(19).width('100%')
            .copyOption(CopyOptions.LocalDevice)
            .padding(12).backgroundColor(C.surfaceBlue).borderRadius(11)
            .border({ width: 1, color: C.sky }).margin({ top: 12 })
          Text(`预期 · ${step.expected_result}`).fontSize(11).fontColor(C.mintDeep).lineHeight(18)
            .margin({ top: 9 }).width('100%')
          Row({ space: 8 }) {
            Button('符合预期').layoutWeight(1).height(38).type(ButtonType.Normal).fontSize(10)
              .fontColor(this.practiceStatuses[index] === 'success' ? C.white : C.mintDeep)
              .backgroundColor(this.practiceStatuses[index] === 'success' ? C.mintDeep : C.surfaceMint)
              .borderRadius(12).border({ width: 1, color: C.mint })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.markPractice(index, true))
            Button('未达预期').layoutWeight(1).height(38).type(ButtonType.Normal).fontSize(10)
              .fontColor(this.practiceStatuses[index] === 'failed' ? C.white : C.danger)
              .backgroundColor(this.practiceStatuses[index] === 'failed' ? C.danger : C.surfaceSoft)
              .borderRadius(12).border({ width: 1, color: C.sakura })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.markPractice(index, false))
          }.width('100%').margin({ top: 12 })
        }.width('100%').padding(15).backgroundColor(C.surface).borderRadius(16)
          .border({ width: 1, color: C.border }).margin({ bottom: 11 })
      })
      Text(`实操得分：${this.practiceScore}%`).fontSize(13).fontWeight(FontWeight.Bold)
        .fontColor(C.skyDeep).width('100%').margin({ bottom: 12 })
      if ((this.resource?.practice_guide?.safety_notes || []).length > 0) {
        Column({ space: 6 }) {
          Text('安全与版本提示').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.warning).width('100%')
          ForEach(this.resource?.practice_guide?.safety_notes || [], (note: string) => {
            Text(`• ${note}`).fontSize(11).fontColor(C.muted).lineHeight(18).width('100%')
          })
        }.width('100%').padding(14).backgroundColor('#FFF7E7').borderRadius(14)
          .border({ width: 1, color: '#D8B86A' })
      }
    }.width('100%')
  }

  @Builder
  buildTest(): void {
    Column() {
      this.sectionTitle('GRADED TEST', this.resource?.graded_test?.title || '分阶测试');
      ForEach(this.resource?.graded_test?.items || [], (item: GradedTestItem, index: number) => {
        Column() {
          Row() {
            Text(`${index + 1}`).fontSize(11).fontWeight(FontWeight.Bold).fontColor(C.white)
              .width(25).height(25).textAlign(TextAlign.Center).backgroundColor(C.lavenderDeep).borderRadius(8)
            Text(item.difficulty).fontSize(9).fontColor(C.lavenderDeep).margin({ left: 9 })
            Blank()
            if (this.testSubmitted) {
              Text(this.getTestResult(item.id)?.is_correct ? '正确' : '错误').fontSize(10)
                .fontColor(this.getTestResult(item.id)?.is_correct ? C.mintDeep : C.danger)
            }
          }.width('100%')
          Text(item.stem).fontSize(15).fontColor(C.textStrong).lineHeight(23).width('100%')
            .margin({ top: 10, bottom: 9 })
          ForEach(item.options || [], (option: GradedTestOption) => {
            Row() {
              Radio({ value: option.key, group: `resource_test_${item.id}` })
                .checked((this.testSelectedKeys[index] || '') === option.key)
                .enabled(!this.testSubmitted)
                .width(28).height(28)
                .onChange((checked: boolean) => {
                  if (checked) this.selectTestAnswer(index, option.key);
                })
              Text(option.key).fontSize(11).fontWeight(FontWeight.Bold)
                .fontColor((this.testSelectedKeys[index] || '') === option.key ? C.white : C.skyDeep)
                .width(32).height(32).textAlign(TextAlign.Center)
                .backgroundColor((this.testSelectedKeys[index] || '') === option.key ? C.skyDeep : C.surfaceBlue)
                .borderRadius(16).margin({ left: 8 })
              Text(option.text).fontSize(12).fontColor(C.textStrong).layoutWeight(1).margin({ left: 10 })
              Text((this.testSelectedKeys[index] || '') === option.key ? '✓' : '').fontSize(16)
                .fontColor(C.mintDeep).width(22)
            }.width('100%').height(64).padding(10)
              .backgroundColor(!this.testSubmitted ?
                ((this.testSelectedKeys[index] || '') === option.key ? C.surfaceMint : C.surface) :
                this.optionBackground(index, option.key))
              .borderRadius(13).border({ width: 2, color: !this.testSubmitted ?
                ((this.testSelectedKeys[index] || '') === option.key ? C.mintDeep : C.border) :
                this.optionBorder(index, option.key) })
              .enabled(!this.testSubmitted).opacity(this.testSubmitted ? 0.86 : 1.0)
              .focusable(true).margin({ bottom: 7 })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle,
                disabled: this.buttonDisabledStyle })
              .onClick(() => this.selectTestAnswer(index, option.key))
          }, (option: GradedTestOption) => `${item.id}_${option.key}`)
          if (this.testSubmitted) {
            Text(`答案 · ${this.getTestResult(item.id)?.correct_answer || '-'}`).fontSize(11)
              .fontWeight(FontWeight.Bold).fontColor(C.mintDeep).width('100%').margin({ top: 7 })
            if (this.getTestResult(item.id)?.explanation) {
              Text(this.getTestResult(item.id)?.explanation || '').fontSize(11).fontColor(C.muted)
                .lineHeight(18).width('100%').margin({ top: 5 })
            }
          }
        }.width('100%').padding(15).backgroundColor(C.surface).borderRadius(16)
          .border({ width: 1, color: C.border }).margin({ bottom: 11 })
      })
      if (this.testSubmitted) {
        Row({ space: 10 }) {
          Text(`测试得分：${this.correctRate}%`).fontSize(15).fontWeight(FontWeight.Bold)
            .fontColor(this.correctRate >= 60 ? C.mintDeep : C.danger).layoutWeight(1)
          Button('重新作答').height(38).type(ButtonType.Capsule).fontSize(10)
            .backgroundColor(C.surfaceBlue).fontColor(C.skyDeep).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.retryResourceTest())
        }.width('100%')
      } else {
        Text(this.canSubmitTest ? '全部测试题已完成，可以提交评分。' :
          `还需完成 ${(this.resource?.graded_test?.items || []).length - this.testAnsweredCountState} 题`)
          .fontSize(10).fontColor(this.canSubmitTest ? C.mintDeep : C.muted).width('100%').margin({ bottom: 8 })
        Button(this.testSubmitting ? '评分中…' : `提交测试（${this.testAnsweredCountState}/${(this.resource?.graded_test?.items || []).length}）`)
          .width('100%').height(46).type(ButtonType.Capsule)
          .backgroundColor(this.canSubmitTest ? C.lavenderDeep : '#9FAAB5').fontColor(C.white)
          .enabled(!this.testSubmitting)
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
          .onClick(() => this.submitResourceTest())
      }
    }.width('100%')
  }

  @Builder
  buildNotes(): void {
    Column({ space: 12 }) {
      this.sectionTitle('NOTES', '学习笔记与收藏');
      Button(this.bookmarked ? '★ 已收藏当前资源' : '☆ 收藏当前资源').width('100%').height(44)
        .type(ButtonType.Capsule).fontWeight(FontWeight.Bold)
        .backgroundColor(this.bookmarked ? C.surfaceMint : C.surfaceBlue)
        .fontColor(this.bookmarked ? C.mintDeep : C.skyDeep)
        .border({ width: 1.5, color: this.bookmarked ? C.mint : C.sky })
        .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
        .onClick(() => this.toggleBookmark())
      TextArea({ placeholder: '记录关键概念、命令、错误现象和复习计划', text: this.noteText })
        .width('100%').height(190).fontSize(13).fontColor(C.textStrong).placeholderColor(C.muted)
        .padding(14).backgroundColor(C.surface).borderRadius(15).border({ width: 1, color: C.border })
        .onChange((value: string) => { this.noteText = value; this.noteSaved = false; })
      Button(this.noteSaved ? '✓ 笔记已保存' : '保存笔记').width('100%').height(46).type(ButtonType.Capsule)
        .backgroundColor(this.noteSaved ? C.mintDeep : C.lavenderDeep).fontColor(C.white)
        .enabled(!this.noteSaved).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
        .onClick(() => this.saveNote())
      Text('笔记与收藏仅保存在本机，清除本地数据时会一并删除。').fontSize(9).fontColor(C.muted)
        .lineHeight(15).width('100%')
    }.width('100%')
  }

  @Builder
  buildCitations(): void {
    Column() {
      this.sectionTitle('EVIDENCE', '知识溯源与审核');
      Column() {
        Row() {
          Text('综合审核分').fontSize(12).fontColor(C.muted).layoutWeight(1)
          Text(`${this.getReviewScore()}%`).fontSize(22).fontWeight(FontWeight.Bold).fontColor(C.mintDeep)
        }.width('100%')
        Text('结构、证据、答案一致性、领域一致性和实操可执行性').fontSize(10).fontColor(C.muted).margin({ top: 4 })
      }.width('100%').padding(15).backgroundColor(C.surfaceMint).borderRadius(15)
        .border({ width: 1, color: C.mint }).margin({ bottom: 12 })

      ForEach(this.resource?.citations || [], (citation: CitationItem, index: number) => {
        Column({ space: 7 }) {
          Row() {
            Text(`EV-${index + 1}`).fontSize(9).fontWeight(FontWeight.Bold).fontColor(C.white)
              .padding({ left: 7, right: 7, top: 4, bottom: 4 }).backgroundColor(C.skyDeep).borderRadius(8)
            Blank()
            Text(citation.verification_status || 'verified').fontSize(9).fontColor(C.mintDeep)
          }.width('100%')
          Text(citation.title || citation.evidence_id).fontSize(14).fontWeight(FontWeight.Medium)
            .fontColor(C.textStrong).width('100%')
          if (citation.source_url.startsWith('https://') || citation.source_url.startsWith('http://')) {
            Hyperlink(citation.source_url, '打开原始证据 ↗')
            Text(citation.source_url).fontSize(9).fontColor(C.muted).lineHeight(15).width('100%')
              .copyOption(CopyOptions.LocalDevice)
            Text('长按上方地址可复制').fontSize(8).fontColor(C.muted).width('100%')
          } else {
            Text('已审核的本地知识库证据').fontSize(11).fontColor(C.mintDeep)
            Text(citation.title || citation.evidence_id).fontSize(9).fontColor(C.muted).lineHeight(15).width('100%')
              .copyOption(CopyOptions.LocalDevice)
            Text('本地来源路径不暴露给客户端；长按标题可复制').fontSize(8).fontColor(C.muted).width('100%')
          }
        }.width('100%').padding(14).backgroundColor(C.surface).borderRadius(15)
          .border({ width: 1, color: C.border }).margin({ bottom: 10 })
      })
    }.width('100%')
  }

  @Builder
  buildRecordedActions(): void {
    Column({ space: 10 }) {
      Text('该资源反馈已提交').fontSize(13).fontWeight(FontWeight.Bold).fontColor(C.mintDeep).width('100%')
      Text(this.feedbackMessage || '掌握度已更新，不会重复提交。').fontSize(10).fontColor(C.muted)
        .lineHeight(17).width('100%')
      if (this.nextWorkflowId) {
        Button('进入下一阶段学习').width('100%').height(46).type(ButtonType.Capsule)
          .backgroundColor(C.lavenderDeep).fontColor(C.white).fontWeight(FontWeight.Bold)
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openNextWorkflow())
      } else {
        Button('查看完整学情报告').width('100%').height(44).type(ButtonType.Capsule)
          .backgroundColor(C.surfaceMint).fontColor(C.mintDeep).border({ width: 1, color: C.mint })
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({
            url: 'pages/ReportPage',
            params: { learnerId: this.learnerId, domainId: this.getDomainId(), demoMode: this.demoMode,
              demoProfile: this.demoProfile },
          }))
      }
    }.width('100%').padding(15).backgroundColor(C.surfaceMint).borderRadius(16)
      .border({ width: 1, color: C.mint }).margin({ top: 18 })
  }

  @Builder
  buildFeedbackPanel(): void {
    Column() {
      Row() {
        Text('学习反馈').fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong).layoutWeight(1)
        Text('测试与实操已自动计分').fontSize(9).fontColor(C.lavenderDeep)
      }.width('100%').margin({ bottom: 14 })

      this.scoreRow('理论正确率', this.correctRate);
      this.scoreRow('实操完成度', this.practiceScore);

      Text('主观难度').fontSize(12).fontColor(C.muted).width('100%').margin({ top: 11, bottom: 8 })
      Row({ space: 8 }) {
        ForEach(DIFFICULTIES, (label: string, index: number) => {
          Button(label).fontSize(11).layoutWeight(1).height(40).type(ButtonType.Normal)
            .fontColor(this.subjectiveDifficulty === index ? C.white : C.textStrong)
            .backgroundColor(this.subjectiveDifficulty === index ? C.lavenderDeep : C.surface).borderRadius(13)
            .border({ width: 1, color: this.subjectiveDifficulty === index ? C.lavenderDeep : C.border })
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.subjectiveDifficulty = index; })
        }, (label: string) => label)
      }.width('100%')

      TextInput({ placeholder: '错误标签，可补充后用逗号分隔', text: this.errorTags })
        .width('100%').height(43).fontSize(12).fontColor(C.textStrong).placeholderColor(C.muted)
        .backgroundColor(C.surface).borderRadius(12).border({ width: 1, color: C.border })
        .padding({ left: 12, right: 12 }).margin({ top: 12 })
        .onChange((value: string) => { this.errorTags = value; })

      Row({ space: 10 }) {
        Button('取消').layoutWeight(1).height(44).backgroundColor(C.surfaceBlue).fontColor(C.textStrong).borderRadius(13)
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => { this.showFeedback = false; })
        Button(this.submitting ? '提交中…' : '提交反馈').layoutWeight(2).height(44).backgroundColor(C.skyDeep)
          .fontColor(C.white).fontWeight(FontWeight.Bold).borderRadius(13).enabled(!this.submitting)
          .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.submitFeedback())
      }.width('100%').margin({ top: 14 })
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(17)
      .border({ width: 1, color: C.border }).margin({ top: 18 })
  }

  @Builder
  scoreRow(label: string, value: number): void {
    Row() {
      Text(label).fontSize(12).fontColor(C.muted).layoutWeight(1)
      Text(`${value}%`).fontSize(14).fontWeight(FontWeight.Bold)
        .fontColor(value >= 60 ? C.mintDeep : C.danger)
    }.width('100%').padding({ top: 8, bottom: 8 })
  }
}
