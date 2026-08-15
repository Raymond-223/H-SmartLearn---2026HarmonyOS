/** Competition metric cockpit backed by the server regression suite. */
import { ApiService, BenchmarkSummaryResponse } from '../service/ApiService';
import { ContinuationSession } from '../integration/ContinuationSession';
import { SpringColors as C } from '../theme/SpringTheme';


@Entry
@Component
struct BenchmarkPage {
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
  @State private summary: BenchmarkSummaryResponse | null = null;

  private api: ApiService = new ApiService();

  aboutToAppear(): void {
    ContinuationSession.update('pages/BenchmarkPage');
    this.loadSummary();
  }

  async loadSummary(refresh: boolean = false): Promise<void> {
    this.loading = true;
    this.errorMsg = '';
    try {
      this.summary = await this.api.getBenchmarkSummary(refresh);
    } catch (error) {
      this.errorMsg = `指标加载失败：${(error as Error).message}`;
    } finally {
      this.loading = false;
    }
  }

  metricColor(passed: boolean): string {
    return passed ? C.mintDeep : C.danger;
  }

  build(): void {
    Column() {
      Stack() {
        Circle().width(190).height(190).fill('#79B8F3').opacity(0.5).position({ x: '62%', y: -95 })
        Circle().width(90).height(90).fill('#B4A1E6').opacity(0.42).position({ x: '80%', y: 68 })
        Column() {
          Row() {
            Text('COMPETITION LAB').fontSize(10).fontColor(C.sky).fontWeight(FontWeight.Bold)
            Blank()
            Text('XH-202630').fontSize(9).fontColor(C.lavenderDeep)
          }.width('100%')
          Text('竞赛指标舱').fontSize(27).fontWeight(FontWeight.Bold).fontColor(C.textStrong).margin({ top: 13 })
          Text('将幻觉控制、难度适配、知识覆盖和测试规模变成可重复验证的工程指标。')
            .fontSize(12).fontColor(C.muted).lineHeight(19).margin({ top: 5 })
        }.width('100%').padding({ left: 21, right: 21, top: 25, bottom: 23 })
      }.width('100%').backgroundColor('#F2FAFF')

      if (this.loading) {
        Column({ space: 14 }) {
          LoadingProgress().width(46).height(46).color(C.sky)
          Text('正在运行60组技能与画像回归').fontSize(14).fontColor(C.muted)
          Button('返回').height(42).type(ButtonType.Capsule).backgroundColor(C.surfaceBlue).fontColor(C.skyDeep)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.getUIContext().getRouter().back())
        }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.errorMsg) {
        Column({ space: 14 }) {
          Text('!').fontSize(44).fontColor(C.danger)
          Text(this.errorMsg).fontSize(13).fontColor(C.muted).textAlign(TextAlign.Center)
          Button('重新加载').backgroundColor(C.sky).fontColor('#06121C').borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.loadSummary())
          Button('返回').backgroundColor(C.surfaceBlue).fontColor(C.skyDeep).borderRadius(14)
            .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle })
            .onClick(() => this.getUIContext().getRouter().back())
        }.width('100%').layoutWeight(1).padding(30).justifyContent(FlexAlign.Center).alignItems(HorizontalAlign.Center)
      } else if (this.summary !== null) {
        Scroll() {
          Column() {
            Column() {
              Row() {
              Column({ space: 4 }) {
                Text(this.summary.status === 'pass' ? 'ENGINEERING READY' : 'NEEDS ATTENTION')
                  .fontSize(10).fontWeight(FontWeight.Bold)
                  .fontColor(this.summary.status === 'pass' ? C.mintDeep : C.danger)
                Text(`${this.summary.case_count} 组回归用例`).fontSize(24).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
              }.layoutWeight(1)
              Text(`${this.summary.profile_count} 类画像`).fontSize(11).fontColor(C.sky)
                .padding({ left: 10, right: 10, top: 6, bottom: 6 }).backgroundColor('#EEF7FF').borderRadius(12)
            }.width('100%')
          }.width('100%').padding(18).backgroundColor(C.surface).borderRadius(18)
            .border({ width: 1, color: '#D6E4EF' }).shadow({ radius: 16, color: '#2600D9FF', offsetY: 8 })

          Text('核心评分指标').fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
            .width('100%').margin({ top: 22, bottom: 11 })

          this.metricCard('幻觉率', `${this.summary.metrics.hallucination_rate}%`, '< 5%',
            this.summary.checks.hallucination, '基于证据引用和不支持结论标记');
          this.metricCard('难度适配准确率', `${this.summary.metrics.difficulty_match_accuracy}%`, '≥ 95%',
            this.summary.checks.difficulty_match, '画像、掌握度与资源等级联合校验');
          this.metricCard('核心知识覆盖率', `${this.summary.metrics.core_knowledge_coverage}%`, '≥ 95%',
            this.summary.checks.core_coverage, '目标技能讲义、实操、测试和引用完整性');
          this.metricCard('审核通过率', `${this.summary.metrics.review_pass_rate || 0}%`, '≥ 95%',
            this.summary.checks.review_pass === true, '逐用例执行规则、答案、领域和技能一致性审核');

          Text('测试资产').fontSize(17).fontWeight(FontWeight.Bold).fontColor(C.textStrong)
            .width('100%').margin({ top: 22, bottom: 11 })
          GridRow({ columns: { sm: 4, md: 8, lg: 12 }, gutter: 10 }) {
            GridCol({ span: { sm: 2, md: 4, lg: 4 } }) {
              this.assetCard(`${this.summary.case_count}`, '测试用例', this.summary.checks.case_count);
            }
            GridCol({ span: { sm: 2, md: 4, lg: 4 } }) {
              this.assetCard(`${this.summary.profile_count}`, '差异画像', this.summary.checks.profile_count);
            }
            GridCol({ span: { sm: 4, md: 8, lg: 4 } }) {
              this.assetCard(`${this.summary.domains.length}`, '领域知识包', this.summary.domains.length >= 2);
            }
          }.width('100%')

          Column({ space: 8 }) {
            Text('数据声明').fontSize(12).fontWeight(FontWeight.Bold).fontColor(C.lavenderDeep)
            Text(this.summary.disclaimer)
              .fontSize(11).fontColor(C.muted).lineHeight(18)
          }.width('100%').padding(15).backgroundColor('#F6F1FF').borderRadius(15)
            .border({ width: 1, color: '#D5CBEF' }).margin({ top: 18 })

          Row({ space: 10 }) {
            Button('返回总览').layoutWeight(1).height(47).backgroundColor('#EEF7FF').fontColor(C.textStrong).borderRadius(14)
              .stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.getUIContext().getRouter().back());
            Button('刷新指标').layoutWeight(1).height(47).backgroundColor(C.sky).fontColor('#06121C')
              .fontWeight(FontWeight.Bold).borderRadius(14).stateStyles({ pressed: this.buttonPressedStyle, focused: this.buttonFocusedStyle, disabled: this.buttonDisabledStyle }).onClick(() => this.loadSummary(true));
          }.width('100%').margin({ top: 20, bottom: 28 })
          }.width('100%')
        }.layoutWeight(1).padding({ left: 18, right: 18, top: 17 })
      }
    }.width('100%').height('100%').backgroundColor(C.background)
  }

  @Builder
  metricCard(title: string, value: string, target: string, passed: boolean, note: string): void {
    Column() {
      Row() {
        Column({ space: 4 }) {
          Text(title).fontSize(13).fontColor(C.muted)
          Text(value).fontSize(28).fontWeight(FontWeight.Bold).fontColor(this.metricColor(passed))
        }.layoutWeight(1)
        Text(passed ? 'PASS' : 'CHECK').fontSize(9).fontWeight(FontWeight.Bold).fontColor(this.metricColor(passed))
          .padding({ left: 8, right: 8, top: 4, bottom: 4 }).backgroundColor('#EEF7FF').borderRadius(8)
      }.width('100%')
      Row() {
        Text(`目标 ${target}`).fontSize(10).fontColor(C.sky)
        Blank()
        Text(note).fontSize(9).fontColor(C.muted)
      }.width('100%').margin({ top: 10 })
    }.width('100%').padding(16).backgroundColor(C.surface).borderRadius(16)
      .border({ width: 1, color: passed ? '#B8DDCC' : '#E7BDC8' }).margin({ bottom: 10 })
  }

  @Builder
  assetCard(value: string, label: string, passed: boolean): void {
    Column({ space: 5 }) {
      Text(value).fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.metricColor(passed))
      Text(label).fontSize(10).fontColor(C.muted)
    }.width('100%').padding({ top: 15, bottom: 15 }).backgroundColor(C.surface)
      .borderRadius(14).border({ width: 1, color: '#E8E1EA' })
  }
}
