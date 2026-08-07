/** Auditable learner report. */
import { ApiService, SkillMasteryData, LearningPathData, LearnerReportData,
  DifficultyCurveData, ProgressHistoryData } from '../service/ApiService';
import { DataStore, NodeMastery } from '../business/DataStore';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';


@Entry
@Component
struct ReportPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private loading: boolean = true;
  @State private errorMsg: string = '';
  @State private overallMastery: number = 0;
  @State private skillMastery: SkillMasteryData[] = [];
  @State private knowledgeGaps: string[] = [];
  @State private strengths: string[] = [];
  @State private learningPath: LearningPathData[] = [];
  @State private difficultyCurve: DifficultyCurveData[] = [];
  @State private progressHistory: ProgressHistoryData[] = [];
  @State private demoMode: boolean = false;
  @State private domainId: string = 'ros2_robotics';
  @State private selectedSkillId: string = '';
  @State private startingSkillId: string = '';

  private api: ApiService = new ApiService();
  private learnerId: string = '';
  private demoProfile: string = '';

  aboutToAppear(): void {
    this.loadReport();
  }

  async loadReport(): Promise<void> {
    this.loading = true;
    this.errorMsg = '';
    try {
      const params: Object = this.getUIContext().getRouter().getParams();
      this.demoMode = RouteParamUtil.boolean(params, 'demoMode');
      this.api = this.demoMode ? ApiService.createDemo() : new ApiService();
      this.domainId = RouteParamUtil.string(params, 'domainId', await DataStore.getLastDomainId());
      this.demoProfile = RouteParamUtil.string(params, 'demoProfile') || await DataStore.getLastDemoProfile();
      this.learnerId = RouteParamUtil.string(params, 'learnerId') ||
        (this.demoMode ? 'learner_demo_guest' : await DataStore.getLearnerId() || '');
      ContinuationSession.update('pages/ReportPage', this.learnerId);
      if (!this.learnerId) {
        this.getUIContext().getRouter().replaceUrl({ url: 'pages/LearnerProfilePage' });
        return;
      }

      const report: LearnerReportData = await this.api.getLearnerReport(this.learnerId, this.domainId);
      this.domainId = report.domain || this.domainId;
      await DataStore.saveLastDomainId(this.domainId);
      this.overallMastery = report.overall_mastery || 0;
      this.skillMastery = report.skill_mastery || [];
      this.knowledgeGaps = report.knowledge_gaps || [];
      this.strengths = report.strengths || [];
      this.learningPath = report.learning_path || [];
      this.difficultyCurve = report.difficulty_curve || [];
      this.progressHistory = report.progress_history || [];

      const cache: NodeMastery[] = this.skillMastery.map((item: SkillMasteryData): NodeMastery => {
        return { nodeId: item.skill_id, mastery: item.score };
      });
      if (!this.demoMode) {
        await DataStore.saveMasteryList(cache);
      }
    } catch (error) {
      this.errorMsg = `报告加载失败：${(error as Error).message}`;
    } finally {
      this.loading = false;
    }
  }

  scoreColor(score: number): string {
    if (score >= 75) return C.mintDeep;
    if (score >= 50) return C.sky;
    return '#E36F86';
  }

  scoreLabel(score: number): string {
    if (score >= 80) return '已掌握';
    if (score >= 60) return '可进阶';
    if (score >= 40) return '需巩固';
    return '优先补强';
  }

  async startPathSkill(item: LearningPathData): Promise<void> {
    if (this.startingSkillId.length > 0) return;
    this.selectedSkillId = item.skill_id;
    this.startingSkillId = item.skill_id;
    this.errorMsg = '';
    try {
      const workflow = await this.api.createWorkflow({
        learner_id: this.learnerId,
        domain_id: this.domainId,
        target_goal: `学习并掌握${item.name}`,
        target_skill_id: item.skill_id,
      });
      if (!this.demoMode) await DataStore.saveLastWorkflowId(workflow.workflow_id);
      this.getUIContext().getRouter().pushUrl({
        url: 'pages/WorkflowProcessPage',
        params: { workflowId: workflow.workflow_id, learnerId: this.learnerId, domainId: this.domainId,
          demoMode: this.demoMode, demoProfile: this.demoProfile },
      });
    } catch (error) {
      this.errorMsg = `启动${item.name}学习失败：${(error as Error).message}`;
      this.startingSkillId = '';
    }
  }

  build(): void {
    Column() {
      Stack() {
        Rect().width('100%').height(222)
          .linearGradient({ angle: 135, colors: [['#F2FAFF', 0.0], ['#FFF3F7', 0.58], ['#F6F1FF', 1.0]] })
        Circle().width(220).height(220).fill('#79B8F3').opacity(0.24).position({ x: '59%', y: -112 })
        Circle().width(120).height(120).fill('#F2A6B8').opacity(0.20).position({ x: '82%', y: 92 })
        Row().width(108).height(1).backgroundColor('#3340E7FF').rotate({ angle: -24 }).position({ x: '66%', y: 85 })
        Circle().width(8).height(8).fill(C.sky).position({ x: '78%', y: 50 }).shadow({ radius: 12, color: C.sky })
        Column() {
          Row() {
            Text(this.demoMode ? 'SPRING DEMO / ANALYTICS' : 'REMOTE API / ANALYTICS').fontSize(9).fontColor(C.sky).fontWeight(FontWeight.Bold)
            Blank()
            Text('AUDITABLE').fontSize(8).fontWeight(FontWeight.Bold).fontColor(C.mintDeep)
              .padding({ left: 8, right: 8, top: 5, bottom: 5 }).backgroundColor('#EAF8F0').borderRadius(11)
          }.width('100%')
          Text('学情决策雷达').fontSize(29).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 25 })
          Text('准确率 × 用时 × 实操 × 历史表现，结果保留证据与决策链。')
            .fontSize(11).fontColor(C.muted).lineHeight(18).margin({ top: 7 })
        }.width('100%').padding({ left: 22, right: 22, top: 27, bottom: 22 })
      }.width('100%').height(222)

      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(46).height(46).color(C.sky)
          Text('正在计算学习画像').fontSize(14).fontColor(C.muted)
        }.width('100%').height('100%').justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.errorMsg) {
        Column({ space: 14 }) {
          Text('!').fontSize(48).fontColor('#E36F86')
          Text(this.errorMsg).fontSize(13).fontColor(C.muted).textAlign(TextAlign.Center)
          Button('重新加载').backgroundColor(C.sky).fontColor('#06121C').borderRadius(14).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.loadReport())
        }.width('100%').height('100%').padding(30).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else {
        this.buildReport();
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  buildReport(): void {
    Scroll() {
      Column() {
        Stack() {
          Row() {
            Stack() {
              Progress({ value: this.overallMastery, total: 100, type: ProgressType.Ring })
                .width(112).height(112).color(this.scoreColor(this.overallMastery))
                .backgroundColor('#E6EEF5').style({ strokeWidth: 7 })
              Column({ space: 2 }) {
                Text(`${Math.round(this.overallMastery)}`).fontSize(31).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
                Text('MASTERY').fontSize(7).fontWeight(FontWeight.Bold).fontColor(C.sky)
              }.alignItems(HorizontalAlign.Center)
            }.width(118).height(118).alignContent(Alignment.Center)
            Column({ space: 8 }) {
              Text('总体掌握度').fontSize(10).fontColor(C.muted)
              Text(this.scoreLabel(this.overallMastery)).fontSize(18).fontWeight(FontWeight.Bold)
                .fontColor(this.scoreColor(this.overallMastery))
              Text(`${this.skillMastery.length} 个技能完成可审计诊断`).fontSize(10).fontColor(C.muted)
              Row({ space: 7 }) {
                Text(`${this.knowledgeGaps.length} GAPS`).fontSize(8).fontColor('#E36F86')
                Text(`${this.strengths.length} STRENGTHS`).fontSize(8).fontColor(C.mintDeep)
              }
            }.layoutWeight(1).margin({ left: 17 })
          }.width('100%').padding(18)
          Rect().width(3).height('64%').backgroundColor(C.sky).borderRadius(2).position({ x: 0, y: '18%' })
            .shadow({ radius: 10, color: C.sky })
        }.width('100%').backgroundColor(C.surface).borderRadius(20)
          .border({ width: 1, color: '#E8E1EA' }).shadow({ radius: 18, color: '#2600D9FF', offsetY: 8 })

        this.title('技能掌握矩阵', 'MASTERY');
        if (this.skillMastery.length === 0) {
          this.emptyCard('尚未产生测评数据，完成诊断后会显示掌握度。');
        } else {
          Column({ space: 10 }) {
            ForEach(this.skillMastery, (skill: SkillMasteryData) => {
              Column() {
                Row() {
                  Column({ space: 3 }) {
                    Text(skill.name || skill.skill_id).fontSize(14).fontWeight(FontWeight.Medium).fontColor(C.textStrong)
                    Text(`置信度 ${Math.round((skill.confidence || 0) * 100)}%`).fontSize(9).fontColor(C.muted)
                  }.layoutWeight(1)
                  Text(`${Math.round(skill.score)}%`).fontSize(16).fontWeight(FontWeight.Bold).fontColor(this.scoreColor(skill.score))
                }.width('100%')
                Row() {
                  Row().width(`${Math.max(2, skill.score)}%`).height(6).backgroundColor(this.scoreColor(skill.score)).borderRadius(3)
                }.width('100%').height(6).backgroundColor('#E6EEF5').borderRadius(3).margin({ top: 10 })
              }
              .width('100%').padding(14).backgroundColor(C.surface).borderRadius(15).border({ width: 1, color: '#E8E1EA' })
            })
          }.width('100%')
        }

        Row({ space: 10 }) {
          this.summaryCard(`${this.knowledgeGaps.length}`, '知识缺口', '#E36F86');
          this.summaryCard(`${this.strengths.length}`, '优势技能', C.mintDeep);
          this.summaryCard(`${this.learningPath.length}`, '路径节点', C.lavenderDeep);
        }.width('100%').margin({ top: 18 })

        this.title('难度分层表现', 'DIFFICULTY');
        Row({ space: 9 }) {
          ForEach(this.difficultyCurve, (item: DifficultyCurveData) => {
            Column({ space: 5 }) {
              Text(`${Math.round(item.score)}%`).fontSize(20).fontWeight(FontWeight.Bold)
                .fontColor(this.scoreColor(item.score))
              Text(item.label).fontSize(11).fontColor(C.textStrong)
              Text(`${item.skill_count || 0} 项技能`).fontSize(8).fontColor(C.muted)
            }.layoutWeight(1).padding({ top: 14, bottom: 14 }).backgroundColor(C.surface)
              .borderRadius(14).border({ width: 1, color: C.border })
          })
        }.width('100%')

        this.title('最近学习进展', 'HISTORY');
        if (this.progressHistory.length === 0) {
          this.emptyCard('完成诊断或资源反馈后，这里会形成可追踪的学习时间线。');
        } else {
          Column({ space: 8 }) {
            ForEach(this.progressHistory.slice(Math.max(0, this.progressHistory.length - 6)).reverse(),
              (item: ProgressHistoryData) => {
                Row() {
                  Text(item.event_type === 'assessment' ? '诊' : '学').fontSize(10).fontWeight(FontWeight.Bold)
                    .fontColor(C.white).width(28).height(28).textAlign(TextAlign.Center)
                    .backgroundColor(item.event_type === 'assessment' ? C.skyDeep : C.mintDeep).borderRadius(9)
                  Column({ space: 3 }) {
                    Text(item.label).fontSize(12).fontWeight(FontWeight.Medium).fontColor(C.textStrong)
                    Text(item.timestamp.replace('T', ' ').substring(0, 16)).fontSize(8).fontColor(C.muted)
                  }.layoutWeight(1).margin({ left: 10 }).alignItems(HorizontalAlign.Start)
                  Text(`${Math.round(item.score)}%`).fontSize(14).fontWeight(FontWeight.Bold)
                    .fontColor(this.scoreColor(item.score))
                }.width('100%').padding(12).backgroundColor(C.surface).borderRadius(13)
                  .border({ width: 1, color: C.border })
              })
          }.width('100%')
        }

        this.title('知识缺口', 'GAPS');
        if (this.knowledgeGaps.length === 0) {
          this.emptyCard('当前测评范围内没有明显缺口。');
        } else {
          Column({ space: 9 }) {
            ForEach(this.knowledgeGaps, (gap: string, index: number) => {
              Row() {
                Text(`${index + 1}`).fontSize(10).fontWeight(FontWeight.Bold).fontColor('#1B0710')
                  .width(25).height(25).textAlign(TextAlign.Center).backgroundColor('#E36F86').borderRadius(8)
                Text(gap).fontSize(13).fontColor(C.textStrong).margin({ left: 10 }).layoutWeight(1)
                Text('待补强').fontSize(9).fontColor('#D97995')
              }.width('100%').padding(13).backgroundColor('#FFF0F3').borderRadius(14).border({ width: 1, color: '#E7C2CC' })
            })
          }
        }

        this.title('推荐学习路径', 'PATH');
        Column() {
          ForEach(this.learningPath, (item: LearningPathData, index: number) => {
            Column() {
              if (index > 0) {
                Row().width(2).height(13).backgroundColor('#C4D5E4').margin({ left: 19 })
              }
              Button() {
                Row() {
                  Text(`${item.order}`).fontSize(11).fontWeight(FontWeight.Bold).fontColor(C.white)
                    .width(38).height(38).textAlign(TextAlign.Center)
                    .backgroundColor(index === this.learningPath.length - 1 ? C.lavenderDeep : C.skyDeep).borderRadius(12)
                  Column({ space: 4 }) {
                    Text(item.name).fontSize(14).fontWeight(FontWeight.Medium).fontColor(C.textStrong)
                    Text(`${item.estimated_minutes || 60} 分钟 · 当前 ${Math.round(item.mastery || 0)}%`)
                      .fontSize(10).fontColor(C.muted)
                  }.layoutWeight(1).margin({ left: 11 }).alignItems(HorizontalAlign.Start)
                  Text(this.startingSkillId === item.skill_id ? '启动中…' : '开始 →').fontSize(10)
                    .fontColor(this.selectedSkillId === item.skill_id ? C.lavenderDeep : C.skyDeep)
                }.width('100%').padding(13)
              }.width('100%').type(ButtonType.Normal).height(68)
                .backgroundColor(this.selectedSkillId === item.skill_id ? C.surfaceLavender : C.surface)
                .borderRadius(15).border({ width: 1.5,
                  color: this.selectedSkillId === item.skill_id ? C.lavenderDeep : C.border })
                .enabled(this.startingSkillId.length === 0).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.startPathSkill(item))
            }.width('100%')
          })
        }.width('100%')

        Row({ space: 10 }) {
          Button('技能图谱').layoutWeight(1).height(47).backgroundColor('#EEF7FF').fontColor(C.textStrong).borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/SkillGraphPage', params: { demoMode: this.demoMode, domainId: this.domainId, learnerId: this.learnerId, demoProfile: this.demoProfile } }));
          Button('重新诊断').layoutWeight(1).height(47).backgroundColor(C.sky).fontColor('#06121C')
            .fontWeight(FontWeight.Bold).borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().replaceUrl({
              url: 'pages/QuizPage', params: { learnerId: this.learnerId, domainId: this.domainId, demoMode: this.demoMode, demoProfile: this.demoProfile },
            }));
        }.width('100%').margin({ top: 20, bottom: 28 })
      }.padding({ left: 18, right: 18, top: 17 })
    }.layoutWeight(1)
  }

  @Builder
  title(title: string, kicker: string): void {
    Column({ space: 3 }) {
      Text(kicker).fontSize(9).fontWeight(FontWeight.Bold).fontColor(C.sky)
      Text(title).fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
    }.width('100%').margin({ top: 22, bottom: 11 })
  }

  @Builder
  summaryCard(value: string, label: string, accent: string): void {
    Column({ space: 4 }) {
      Text(value).fontSize(21).fontWeight(FontWeight.Bold).fontColor(accent)
      Text(label).fontSize(9).fontColor(C.muted)
    }.layoutWeight(1).padding({ top: 14, bottom: 14 }).backgroundColor(C.surface)
    .borderRadius(14).border({ width: 1, color: '#E8E1EA' })
  }

  @Builder
  emptyCard(message: string): void {
    Text(message).fontSize(12).fontColor(C.muted).lineHeight(19).width('100%').textAlign(TextAlign.Center)
      .padding(18).backgroundColor(C.surface).borderRadius(15).border({ width: 1, color: '#E8E1EA' })
  }
}
