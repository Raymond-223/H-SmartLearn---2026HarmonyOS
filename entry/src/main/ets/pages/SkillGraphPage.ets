/** 2D skill path visualization. */
import { SkillGraphService, SkillNode } from '../service/SkillGraphService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';
import { RouteParamUtil } from '../utils/RouteParamUtil';
import { ApiService } from '../service/ApiService';
import { DataStore } from '../business/DataStore';

interface PathNode {
  id: string;
  name: string;
  difficulty: number;
  estimatedMinutes: number;
  mastery: number;
}


@Entry
@Component
struct SkillGraphPage {
  @Styles buttonPressedStyle(): void {
    .opacity(0.72)
  }

  @Styles buttonFocusedStyle(): void {
    .opacity(0.9)
  }

  @Styles buttonDisabledStyle(): void {
    .opacity(0.45)
  }

  @State private pathNodes: PathNode[] = [];
  @State private selectedId: string = '';
  @State private loading: boolean = true;
  @State private offlineMode: boolean = false;
  @State private domainId: string = 'ros2_robotics';
  @State private errorMsg: string = '';
  @State private startingSkillId: string = '';

  private api: ApiService = new ApiService();
  private learnerId: string = '';

  aboutToAppear(): void {
    this.initialize();
  }

  async initialize(): Promise<void> {
    try {
      const params: Object = this.getUIContext().getRouter().getParams();
      this.domainId = RouteParamUtil.string(params, 'domainId', await DataStore.getLastDomainId());
      this.learnerId = RouteParamUtil.string(params, 'learnerId') || await DataStore.getLearnerId() || '';
      this.api = new ApiService();
      await DataStore.saveLastDomainId(this.domainId);
      ContinuationSession.update('pages/SkillGraphPage', this.learnerId);
      await this.loadGraph();
    } catch (error) {
      this.loading = false;
      this.errorMsg = `技能图谱初始化失败：${(error as Error).message}`;
    }
  }

  async loadGraph(): Promise<void> {
    this.loading = true;
    this.errorMsg = '';
    try {
      await SkillGraphService.loadGraph(this.domainId, true);
      const nodes: SkillNode[] = SkillGraphService.getNodes();
      const order: string[] = SkillGraphService.getLearningPath();
      const result: PathNode[] = [];
      for (const id of order) {
        const node: SkillNode | undefined = nodes.find((item: SkillNode) => item.id === id);
        if (node) {
          result.push({
            id: node.id,
            name: node.name,
            difficulty: node.difficulty,
            estimatedMinutes: node.estimatedMinutes,
            mastery: node.mastery || 0,
          });
        }
      }
      this.pathNodes = result;
    } catch (error) {
      this.pathNodes = [];
      this.errorMsg = `技能图谱加载失败：${(error as Error).message}`;
    } finally {
      this.loading = false;
    }
  }

  masteryColor(value: number): string {
    if (value >= 75) return C.mintDeep;
    if (value >= 50) return C.sky;
    if (value > 0) return '#E99A6C';
    return '#A7B5C3';
  }

  masteryLabel(value: number): string {
    if (value >= 75) return '已掌握';
    if (value >= 50) return '学习中';
    if (value > 0) return '需巩固';
    return '未测评';
  }

  difficultyStars(value: number): string {
    let text: string = '';
    for (let index = 0; index < value; index++) {
      text += '★';
    }
    return text;
  }

  prerequisiteNames(id: string): string {
    const names = SkillGraphService.getPrerequisites(id).map((item: SkillNode) => item.name);
    return names.length > 0 ? names.join('、') : '无';
  }

  dependentNames(id: string): string {
    const names = SkillGraphService.getDependents(id).map((item: SkillNode) => item.name);
    return names.length > 0 ? names.join('、') : '暂无';
  }

  async startSkill(node: PathNode): Promise<void> {
    if (this.startingSkillId.length > 0) return;
    this.errorMsg = '';
    try {
      if (!this.learnerId) {
        this.getUIContext().getRouter().pushUrl({
          url: 'pages/LearnerProfilePage',
          params: { domainId: this.domainId },
        });
        return;
      }
      this.startingSkillId = node.id;
      const workflow = await this.api.createWorkflow({
        learner_id: this.learnerId,
        domain_id: this.domainId,
        target_goal: `学习并掌握${node.name}`,
        target_skill_id: node.id,
      });
      await DataStore.saveLastWorkflowId(workflow.workflow_id);
      this.getUIContext().getRouter().pushUrl({
        url: 'pages/WorkflowProcessPage',
        params: { workflowId: workflow.workflow_id, learnerId: this.learnerId, domainId: this.domainId },
      });
    } catch (error) {
      this.errorMsg = `启动${node.name}学习失败：${(error as Error).message}`;
      this.startingSkillId = '';
    }
  }

  build() {
    Column() {
      Stack() {
        Circle().width(190).height(190).fill('#79B8F3').opacity(0.48).position({ x: '62%', y: -95 })
        Circle().width(92).height(92).fill('#B4A1E6').opacity(0.4).position({ x: '80%', y: 68 })
        Column() {
          Text('SKILL GRAPH / API').fontSize(10).fontColor(C.sky).fontWeight(FontWeight.Bold)
          Text('技能路径图').fontSize(27).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 13 })
          Text('依赖关系由规则算法排序，颜色来自服务端掌握度。').fontSize(12).fontColor(C.muted).margin({ top: 5 })
        }.width('100%').padding({ left: 21, right: 21, top: 25, bottom: 23 })
      }.width('100%').backgroundColor('#F2FAFF')

      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(46).height(46).color(C.sky)
          Text('正在构建技能拓扑').fontSize(14).fontColor(C.muted)
        }.width('100%').height('100%').justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.errorMsg) {
        Column({ space: 14 }) {
          Text('!').fontSize(48).fontColor('#E36F86')
          Text(this.errorMsg).fontSize(12).fontColor(C.muted).lineHeight(18).textAlign(TextAlign.Center)
          Button('重新加载').height(46).backgroundColor(C.sky).fontColor('#FFFFFFFF').borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.loadGraph())
        }.width('100%').layoutWeight(1).padding(28).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else {
        Scroll() {
          Column() {
            Row({ space: 9 }) {
              this.legend(C.mintDeep, '已掌握');
              this.legend(C.sky, '学习中');
              this.legend('#E99A6C', '需巩固');
              this.legend('#A7B5C3', '未测评');
            }
            .width('100%').padding(12).backgroundColor(C.surface).borderRadius(14).border({ width: 1, color: '#E8E1EA' })

            Text('推荐拓扑顺序').fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
              .width('100%').margin({ top: 20, bottom: 11 })

            ForEach(this.pathNodes, (node: PathNode, index: number) => {
              Column() {
                if (index > 0) {
                  Column() {
                    Row().width(2).height(14).backgroundColor('#C4D5E4')
                    Text('↓').fontSize(13).fontColor('#8C9AAA').margin({ top: -3 })
                  }.width('100%').alignItems(HorizontalAlign.Center)
                }

                Row() {
                  Column({ space: 3 }) {
                    Text(`${index + 1}`).fontSize(14).fontWeight(FontWeight.Bold).fontColor('#06121C')
                    Text('STEP').fontSize(7).fontColor('#16344A')
                  }
                  .width(48).height(48).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
                  .backgroundColor(index === this.pathNodes.length - 1 ? C.lavenderDeep : C.sky).borderRadius(14)

                  Column({ space: 5 }) {
                    Text(node.name).fontSize(15).fontWeight(FontWeight.Medium).fontColor(C.textStrong)
                    Row({ space: 8 }) {
                      Text(this.difficultyStars(node.difficulty)).fontSize(9).fontColor('#E99A6C')
                      Text(`${node.estimatedMinutes} 分钟`).fontSize(9).fontColor(C.muted)
                    }
                  }.layoutWeight(1).margin({ left: 12 })

                  Column({ space: 3 }) {
                    Text(`${Math.round(node.mastery)}%`).fontSize(14).fontWeight(FontWeight.Bold).fontColor(this.masteryColor(node.mastery))
                    Text(this.masteryLabel(node.mastery)).fontSize(8).fontColor(C.muted)
                  }.alignItems(HorizontalAlign.End)
                }
                .width('100%').padding(14).backgroundColor(this.selectedId === node.id ? '#EEF7FF' : C.surface)
                .borderRadius(16).border({ width: this.selectedId === node.id ? 1.5 : 1,
                  color: this.selectedId === node.id ? C.sky : '#E8E1EA' })
                .zIndex(this.selectedId === node.id ? 2 : 1)
                .focusable(true).onClick(() => { this.selectedId = this.selectedId === node.id ? '' : node.id; })

                if (this.selectedId === node.id) {
                  Column({ space: 8 }) {
                    Row() {
                      Text('前置依赖').fontSize(10).fontColor(C.sky).width(70)
                      Text(this.prerequisiteNames(node.id)).fontSize(11).fontColor(C.muted).layoutWeight(1)
                    }.width('100%')
                    Row() {
                      Text('后续技能').fontSize(10).fontColor(C.lavenderDeep).width(70)
                      Text(this.dependentNames(node.id)).fontSize(11).fontColor(C.muted).layoutWeight(1)
                    }.width('100%')
                    Row() {
                      Text('掌握状态').fontSize(10).fontColor(C.mintDeep).width(70)
                      Text(`${this.masteryLabel(node.mastery)} · ${Math.round(node.mastery)}%`).fontSize(11)
                        .fontColor(this.masteryColor(node.mastery)).layoutWeight(1)
                    }.width('100%')
                    Button(this.startingSkillId === node.id ? '正在创建学习资源…' : '学习此技能')
                      .width('100%').height(42).type(ButtonType.Capsule).fontWeight(FontWeight.Bold)
                      .backgroundColor(C.lavenderDeep).fontColor(C.white)
                      .enabled(this.startingSkillId.length === 0).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.startSkill(node))
                  }
                  .width('100%').padding(13).backgroundColor('#F7FAFC').borderRadius(13)
                  .border({ width: 1, color: '#D7E5F0' }).margin({ top: 6 })
                }
              }.width('100%')
            })
          }.padding({ left: 18, right: 18, top: 16, bottom: 30 })
        }.layoutWeight(1)
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  legend(color: string, label: string): void {
    Row({ space: 5 }) {
      Circle().width(7).height(7).fill(color)
      Text(label).fontSize(8).fontColor(C.muted)
    }.layoutWeight(1)
  }
}
