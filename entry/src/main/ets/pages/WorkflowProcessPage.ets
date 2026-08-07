/** Auditable multi-agent workflow progress. */
import { ApiService, AgentTraceItem } from '../service/ApiService';
import { DataStore } from '../business/DataStore';
import { LearningCacheDatabase } from '../business/LearningCacheDatabase';
import { HarmonyNotificationService } from '../integration/HarmonyNotificationService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';
import { LogUtil } from '../utils/LogUtil';
import { WorkflowStatus, WorkflowStatusUtil } from '../service/WorkflowStatus';

const TAG: string = 'WorkflowProcessPage';

interface AgentDisplay {
  key: string;
  label: string;
  icon: string;
  description: string;
}

interface StepData {
  key: string;
  label: string;
  icon: string;
  description: string;
  status: string;
  summary: string;
  confidence: number;
}

const AGENTS: AgentDisplay[] = [
  { key: 'diagnosis_agent', label: '学情诊断 Agent', icon: '⌁', description: '解释确定性掌握度与知识缺口' },
  { key: 'planner_agent', label: '路径规划 Agent', icon: '◇', description: '按技能依赖生成合法学习顺序' },
  { key: 'retrieval_agent', label: '知识检索 Agent', icon: '⌕', description: '只检索已审核证据并锁定版本' },
  { key: 'generation_agent', label: '资源生成 Agent', icon: '✦', description: '生成讲义、实操指南和分阶测试' },
  { key: 'review_agent', label: '内容审核 Agent', icon: '✓', description: '检查结构、证据、答案和领域一致性' },
];


@Entry
@Component
struct WorkflowProcessPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private steps: StepData[] = [];
  @State private workflowStatus: WorkflowStatus = WorkflowStatus.QUEUED;
  @State private progress: number = 0;
  @State private errorMsg: string = '';
  @State private resourceId: string = '';
  @State private completed: boolean = false;
  @State private runtimeMode: string = 'REMOTE';
  @State private pulseScale: number = 1.0;
  @State private demoMode: boolean = false;
  @State private restarting: boolean = false;

  private api: ApiService = new ApiService();
  private workflowId: string = '';
  private learnerId: string = '';
  private demoProfile: string = '';
  private domainId: string = 'ros2_robotics';
  private pollTimer: number = -1;
  private failureCount: number = 0;
  private polling: boolean = false;
  private navigating: boolean = false;
  private notificationPublished: boolean = false;
  private pollingCancelled: boolean = false;

  aboutToAppear(): void {
    const params: Object = this.getUIContext().getRouter().getParams();
    this.demoMode = RouteParamUtil.boolean(params, 'demoMode');
    this.api = this.demoMode ? ApiService.createDemo() : new ApiService();
    this.runtimeMode = this.demoMode ? 'SPRING DEMO' : 'REMOTE API';
    this.workflowId = RouteParamUtil.string(params, 'workflowId');
    this.learnerId = RouteParamUtil.string(params, 'learnerId') || '';
    this.demoProfile = RouteParamUtil.string(params, 'demoProfile');
    this.domainId = RouteParamUtil.string(params, 'domainId', 'ros2_robotics');
    ContinuationSession.update('pages/WorkflowProcessPage', this.learnerId, this.workflowId, '');
    this.steps = AGENTS.map((agent: AgentDisplay): StepData => {
      return {
        key: agent.key,
        label: agent.label,
        icon: agent.icon,
        description: agent.description,
        status: 'pending',
        summary: '',
        confidence: -1,
      };
    });
    if (!this.workflowId) {
      this.errorMsg = '缺少 workflowId，无法追踪流程';
      return;
    }
    this.startPolling();
  }

  aboutToDisappear(): void {
    this.stopPolling();
  }

  startPolling(): void {
    this.stopPolling();
    this.pollingCancelled = false;
    this.errorMsg = '';
    this.scheduleNextPoll(0);
  }

  cancelPolling(): void {
    this.pollingCancelled = true;
    this.stopPolling();
    this.errorMsg = '';
  }

  scheduleNextPoll(delay: number): void {
    if (this.completed || this.pollingCancelled || WorkflowStatusUtil.isTerminal(this.workflowStatus)) return;
    this.pollTimer = setTimeout(async () => {
      await this.pollOnce();
      if (!this.completed && !this.pollingCancelled && !WorkflowStatusUtil.isTerminal(this.workflowStatus)) {
        this.scheduleNextPoll(WorkflowStatusUtil.nextPollDelay(this.workflowStatus, this.failureCount));
      }
    }, delay);
  }

  stopPolling(): void {
    if (this.pollTimer >= 0) {
      clearTimeout(this.pollTimer);
      this.pollTimer = -1;
    }
  }

  async pollOnce(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      const snapshot = await this.api.getWorkflowSnapshot(this.workflowId);
      const status = snapshot.status;
      this.workflowStatus = status.status;
      this.progress = Math.max(0, Math.min(100, status.progress || 0));
      this.resourceId = status.resource_id || this.resourceId;
      this.errorMsg = status.error_message || '';
      ContinuationSession.update('pages/WorkflowProcessPage', this.learnerId, this.workflowId, this.resourceId);
      try {
        await LearningCacheDatabase.saveWorkflowSnapshot({
          workflowId: this.workflowId,
          status: this.workflowStatus,
          progress: this.progress,
          resourceId: this.resourceId,
          updatedAt: Date.now(),
        });
      } catch (error) {
        LogUtil.warn(TAG, `Unable to save workflow snapshot: ${(error as Error).message}`);
      }

      const trace = snapshot.trace;
      const updated = [...this.steps];
      for (const run of trace.runs || []) {
        const index = updated.findIndex((step: StepData) => step.key === run.agent);
        if (index >= 0) {
          updated[index] = this.mergeRun(updated[index], run);
        }
      }
      if (status.current_agent) {
        const runningIndex = updated.findIndex((step: StepData) => step.key === status.current_agent);
        if (runningIndex >= 0 && updated[runningIndex].status === 'pending') {
          const runningStep: StepData = updated[runningIndex];
          updated[runningIndex] = {
            key: runningStep.key, label: runningStep.label, icon: runningStep.icon,
            description: runningStep.description, status: 'running',
            summary: runningStep.summary, confidence: runningStep.confidence,
          };
        }
      }
      this.steps = updated;
      this.failureCount = 0;

      if (this.workflowStatus === WorkflowStatus.PUBLISHED) {
        this.completed = true;
        this.stopPolling();
        if (!this.resourceId) {
          this.errorMsg = '工作流已完成，但未返回资源编号';
          return;
        }
        if (!this.demoMode) {
          await DataStore.saveLastWorkflowId(this.workflowId);
          await DataStore.saveLastResourceId(this.resourceId);
        }
        if (!this.notificationPublished) {
          this.notificationPublished = true;
          try {
            await HarmonyNotificationService.publishWorkflowCompleted('个性化讲义、实操指南与分阶测试已通过审核');
          } catch (error) {
            LogUtil.warn(TAG, `Unable to publish completion notification: ${(error as Error).message}`);
          }
        }
        // Keep the completed result visible. The learner explicitly opens the resource.
      } else if (this.workflowStatus === WorkflowStatus.FAILED) {
        this.stopPolling();
        this.errorMsg = this.errorMsg || '工作流执行失败，请重新发起诊断';
      }
    } catch (error) {
      this.failureCount++;
      try {
        const snapshot = await LearningCacheDatabase.getWorkflowSnapshot(this.workflowId);
        if (snapshot !== null) {
          this.workflowStatus = snapshot.status as WorkflowStatus;
          this.progress = snapshot.progress;
          this.resourceId = snapshot.resourceId;
          if (this.workflowStatus === WorkflowStatus.PUBLISHED && this.resourceId.length > 0) {
            this.completed = true;
            this.errorMsg = '当前离线，已恢复最近完成的资源快照';
          } else if (this.workflowStatus === WorkflowStatus.FAILED) {
            this.errorMsg = '当前离线，最近一次工作流执行失败，可重新执行或重新诊断';
          }
        }
      } catch (cacheError) {
        LogUtil.warn(TAG, `Unable to restore workflow snapshot: ${(cacheError as Error).message}`);
      }
      if (this.failureCount >= 3 && !this.completed && this.errorMsg.length === 0) {
        this.errorMsg = `暂时无法连接工作流服务，已展示最近快照：${(error as Error).message}`;
      }
    } finally {
      this.polling = false;
    }
  }

  mergeRun(step: StepData, run: AgentTraceItem): StepData {
    return {
      key: step.key,
      label: step.label,
      icon: step.icon,
      description: step.description,
      status: run.status,
      summary: run.summary || '',
      confidence: run.confidence ?? -1,
    };
  }

  openResource(): void {
    if (this.navigating || !this.resourceId) {
      return;
    }
    this.navigating = true;
    this.getUIContext().getRouter().replaceUrl({
      url: 'pages/ResourceViewPage',
      params: {
        workflowId: this.workflowId,
        learnerId: this.learnerId,
        resourceId: this.resourceId,
        demoMode: this.demoMode,
        demoProfile: this.demoProfile,
        domainId: this.domainId,
      },
    }).catch((_error: Error) => {
      this.navigating = false;
      this.errorMsg = '页面跳转失败，请再次点击打开资源';
    });
  }

  resetWorkflowView(): void {
    this.steps = AGENTS.map((agent: AgentDisplay): StepData => {
      return {
        key: agent.key, label: agent.label, icon: agent.icon, description: agent.description,
        status: 'pending', summary: '', confidence: -1,
      };
    });
    this.workflowStatus = WorkflowStatus.QUEUED;
    this.progress = 0;
    this.resourceId = '';
    this.completed = false;
    this.failureCount = 0;
    this.notificationPublished = false;
    this.errorMsg = '';
  }

  async restartWorkflow(): Promise<void> {
    if (this.restarting) return;
    this.restarting = true;
    try {
      const response = await this.api.retryWorkflow(this.workflowId);
      this.workflowId = response.workflow_id;
      if (!this.demoMode) await DataStore.saveLastWorkflowId(this.workflowId);
      this.resetWorkflowView();
      ContinuationSession.update('pages/WorkflowProcessPage', this.learnerId, this.workflowId, '');
      this.startPolling();
    } catch (error) {
      this.errorMsg = `重新执行失败：${(error as Error).message}`;
    } finally {
      this.restarting = false;
    }
  }

  rediagnose(): void {
    try {
      this.getUIContext().getRouter().replaceUrl({
        url: 'pages/QuizPage',
        params: { learnerId: this.learnerId, domainId: this.domainId, demoMode: this.demoMode,
          demoProfile: this.demoProfile },
      });
    } catch (error) {
      this.errorMsg = `返回诊断页失败：${(error as Error).message}`;
    }
  }

  getStatusLabel(): string {
    return WorkflowStatusUtil.label(this.workflowStatus);
  }

  getStepColor(status: string): string {
    if (status === 'success' || status === 'completed') return C.mintDeep;
    if (status === 'running') return C.sky;
    if (status === 'failed') return '#E36F86';
    return '#A7B5C3';
  }

  getStepBadge(status: string): string {
    if (status === 'success' || status === 'completed') return 'DONE';
    if (status === 'running') return 'RUN';
    if (status === 'failed') return 'ERR';
    return 'WAIT';
  }

  build(): void {
    Column() {
      Stack() {
        Rect().width('100%').height(248)
          .linearGradient({ angle: 135, colors: [['#F2FAFF', 0.0], ['#FFF3F7', 0.56], ['#F6F1FF', 1.0]] })
        Circle().width(220).height(220).fill('#79B8F3').opacity(0.25).position({ x: '58%', y: -105 })
          .scale({ x: this.pulseScale, y: this.pulseScale })
        Circle().width(120).height(120).fill('#F2A6B8').opacity(0.20).position({ x: '81%', y: 110 })
        Row().width(108).height(1).backgroundColor('#3340E7FF').rotate({ angle: -24 }).position({ x: '64%', y: 87 })
        Row().width(84).height(1).backgroundColor('#33956BFF').rotate({ angle: 38 }).position({ x: '72%', y: 151 })
        Circle().width(8).height(8).fill(C.sky).position({ x: '76%', y: 52 }).shadow({ radius: 12, color: C.sky })
        Circle().width(6).height(6).fill(C.mintDeep).position({ x: '88%', y: 145 }).shadow({ radius: 9, color: C.mintDeep })

        Column() {
          Row() {
            Text('ORCHESTRATOR / LIVE').fontSize(10).fontColor(C.sky).fontWeight(FontWeight.Bold)
            Blank()
            Text(this.runtimeMode).fontSize(8).fontWeight(FontWeight.Bold)
              .fontColor(this.runtimeMode === 'REMOTE API' ? C.mintDeep : C.lavenderDeep)
              .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor('#F6F1FF').borderRadius(11)
          }.width('100%')
          Row() {
            Column() {
              Text('多智能体').fontSize(28).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
              Text('协同决策网络').fontSize(28).fontWeight(FontWeight.Bold).fontColor(C.sky)
              Text('状态机控制 · 证据约束 · 全程审计').fontSize(10).fontColor(C.muted).margin({ top: 8 })
            }.layoutWeight(1)
            Stack() {
              Progress({ value: this.progress, total: 100, type: ProgressType.Ring })
                .width(88).height(88).color(C.sky).backgroundColor('#E6EEF5').style({ strokeWidth: 5 })
              Column({ space: 1 }) {
                Text(`${this.progress}`).fontSize(24).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
                Text('%').fontSize(8).fontColor(C.sky)
              }.alignItems(HorizontalAlign.Center)
            }.width(94).height(94).alignContent(Alignment.Center)
          }.width('100%').margin({ top: 25 })
        }.width('100%').padding({ left: 22, right: 22, top: 27, bottom: 22 })
      }.width('100%').height(248)

      Scroll() {
        Column() {
          Row() {
            Column({ space: 4 }) {
              Text('CURRENT STATE').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.sky)
              Text(this.getStatusLabel()).fontSize(16).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
            }.layoutWeight(1)
            if (this.completed) {
              Text('PUBLISHED').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.mintDeep)
                .padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor(C.surfaceMint).borderRadius(12)
            } else if (WorkflowStatusUtil.isTerminal(this.workflowStatus)) {
              Text('ACTION REQUIRED').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.danger)
                .padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor(C.surfaceSoft).borderRadius(12)
            } else if (this.pollingCancelled) {
              Text('PAUSED').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.warning)
                .padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor('#FFF7E7').borderRadius(12)
            } else {
              Row({ space: 6 }) {
                Circle().width(7).height(7).fill(C.skyDeep).shadow({ radius: 9, color: C.skyDeep })
                Text('RUNNING').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.skyDeep)
              }.padding({ left: 9, right: 9, top: 6, bottom: 6 }).backgroundColor(C.surfaceBlue).borderRadius(12)
            }
          }.width('100%')
          Row() {
            Row().width(`${Math.max(2, this.progress)}%`).height(5)
              .linearGradient({ angle: 90, colors: [[C.sky, 0.0], [C.lavenderDeep, 0.72], [C.mintDeep, 1.0]] })
              .borderRadius(3).shadow({ radius: 8, color: '#6639D9FF' })
          }.width('100%').height(5).backgroundColor('#E6EEF5').borderRadius(3).margin({ top: 13 })
          Text(`TRACE ID  ${this.workflowId}`).fontSize(8).fontColor('#7C8B9C').margin({ top: 9 }).width('100%')
          if (!this.completed && !WorkflowStatusUtil.isTerminal(this.workflowStatus)) {
            Button(this.pollingCancelled ? '继续追踪' : '停止等待').height(36).type(ButtonType.Capsule)
              .fontSize(10).fontColor(this.pollingCancelled ? C.skyDeep : C.muted)
              .backgroundColor(this.pollingCancelled ? C.surfaceBlue : C.surface)
              .border({ width: 1, color: C.border }).margin({ top: 12 })
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => {
                if (this.pollingCancelled) this.startPolling(); else this.cancelPolling();
              })
          }

          Row() {
            Text('AGENT EXECUTION TRACE').fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.sky)
            Blank()
            Text(`${this.steps.filter((item: StepData) => item.status === 'success').length}/${this.steps.length}`)
              .fontSize(10).fontWeight(FontWeight.Bold).fontColor(C.muted)
          }.width('100%').margin({ top: 24, bottom: 12 })

          ForEach(this.steps, (step: StepData, index: number) => {
            Column() {
              if (index > 0) {
                Stack() {
                  Row().width(2).height(18).backgroundColor('#C4D5E4')
                  if (step.status === 'running' || step.status === 'success') {
                    Row().width(2).height(12).backgroundColor(this.getStepColor(step.status)).shadow({ radius: 7,
                      color: this.getStepColor(step.status) })
                  }
                }.width(48).height(18).alignContent(Alignment.Center)
              }
              Stack() {
                Row() {
                  Stack() {
                    Circle().width(50).height(50).fill(step.status === 'running' ? '#EAF4FB' : '#F2FAFF')
                      .border({ width: step.status === 'running' ? 2 : 1, color: this.getStepColor(step.status) })
                      .shadow({ radius: step.status === 'running' ? 15 : 4,
                        color: step.status === 'running' ? this.getStepColor(step.status) : '#00000000' })
                    Text(step.icon).fontSize(21).fontColor(this.getStepColor(step.status))
                  }.width(52).height(52).alignContent(Alignment.Center)
                  Column({ space: 5 }) {
                    Row() {
                      Text(step.label).fontSize(14).fontWeight(FontWeight.Bold).fontColor(C.textStrong).layoutWeight(1)
                      Text(this.getStepBadge(step.status)).fontSize(8).fontWeight(FontWeight.Bold)
                        .fontColor(this.getStepColor(step.status)).padding({ left: 8, right: 8, top: 4, bottom: 4 })
                        .backgroundColor('#F7FAFC').borderRadius(9)
                    }.width('100%')
                    Text(step.summary || step.description).fontSize(10).fontColor(C.muted).lineHeight(16).maxLines(2)
                    if (step.confidence >= 0) {
                      Row() {
                        Text(`CONFIDENCE ${Math.round(step.confidence * 100)}%`).fontSize(8).fontColor(C.mintDeep)
                        Blank()
                        Row().width(`${Math.round(step.confidence * 54)}%`).height(2).backgroundColor(C.mintDeep).borderRadius(1)
                      }.width('100%')
                    }
                  }.layoutWeight(1).margin({ left: 12 })
                }.width('100%').padding(15)
                if (step.status === 'running') {
                  Rect().width(3).height('64%').backgroundColor(C.sky).borderRadius(2).position({ x: 0, y: '18%' })
                    .shadow({ radius: 10, color: C.sky })
                }
              }.width('100%').backgroundColor(step.status === 'running' ? '#EEF7FF' : C.surface)
                .borderRadius(18).border({ width: 1, color: step.status === 'running' ? '#A9CBE2' : '#E8E1EA' })
            }.width('100%')
          })

          if (this.errorMsg) {
            Column({ space: 9 }) {
              Row() {
                Text('!').fontSize(15).fontWeight(FontWeight.Bold).fontColor('#E36F86')
                Text('CONNECTION EVENT').fontSize(9).fontWeight(FontWeight.Bold).fontColor('#E36F86').margin({ left: 8 })
              }.width('100%')
              Text(this.errorMsg).fontSize(11).fontColor(C.muted).lineHeight(18)
              if (this.workflowStatus === WorkflowStatus.FAILED) {
                Row({ space: 8 }) {
                  Button(this.restarting ? '重新执行中…' : '重新执行工作流').layoutWeight(1).height(40)
                    .backgroundColor(C.sakuraDeep).fontColor(C.white).borderRadius(13)
                    .enabled(!this.restarting).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.restartWorkflow())
                  Button('重新诊断').layoutWeight(1).height(40).backgroundColor(C.surfaceBlue)
                    .fontColor(C.skyDeep).borderRadius(13).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.rediagnose())
                }.width('100%')
              } else {
                Button('重新连接').height(40).backgroundColor(C.surfaceSoft).fontColor(C.sakuraDeep).borderRadius(13)
                  .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.startPolling())
              }
            }.width('100%').padding(15).backgroundColor('#FFF0F3').borderRadius(16)
              .border({ width: 1, color: '#EDC3CE' }).margin({ top: 14 })
          }

          if (this.completed && this.resourceId) {
            Button('解锁个性化资源  →').width('100%').height(52)
              .linearGradient({ angle: 90, colors: [[C.sky, 0.0], ['#6F9DFF', 0.48], [C.lavenderDeep, 1.0]] })
              .fontColor('#031018').fontWeight(FontWeight.Bold).borderRadius(16).margin({ top: 18 })
              .shadow({ radius: 16, color: '#5539D9FF', offsetY: 6 }).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.openResource())
          }
        }.padding({ left: 18, right: 18, top: 17, bottom: 30 })
      }.layoutWeight(1)
    }.width('100%').height('100%').backgroundColor(C.background)
  }

}
