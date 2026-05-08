import { ArkGraphics3DHelper } from '../integration/ArkGraphics3DHelper';
import { GraphManager } from '../business/GraphManager';
import { XComponentController, XComponentType } from '@ohos.arkui.XComponent';

@Entry
@Component
struct Graph3DPage {
  private xController: XComponentController = new XComponentController();
  private lastX: number = 0;
  private lastY: number = 0;
  private hasLastPoint: boolean = false;
  @State private renderNodeCount: number = 0;
  @State private hudText: string = 'rotateX: 0 | rotateY: 0 | zoom: 1.00';

  aboutToAppear(): void {
    ArkGraphics3DHelper.init(this.xController);
    GraphManager.init();
    GraphManager.refreshAll();
    this.renderNodeCount = GraphManager.getRenderNodes().length;
    this.updateHud();
  }

  private handleTouch(event: TouchEvent): void {
    if (!event || !event.touches || event.touches.length === 0) {
      return;
    }

    const point = event.touches[0];
    const x = point.x;
    const y = point.y;

    if (!this.hasLastPoint) {
      this.lastX = x;
      this.lastY = y;
      this.hasLastPoint = true;
      return;
    }

    const deltaX = x - this.lastX;
    const deltaY = y - this.lastY;
    this.lastX = x;
    this.lastY = y;

    ArkGraphics3DHelper.handleGesture(deltaX, deltaY);
    this.updateHud();
  }

  private updateHud(): void {
    const state = ArkGraphics3DHelper.getViewState();
    this.hudText = `rotateX: ${state.rotateX.toFixed(1)} | rotateY: ${state.rotateY.toFixed(1)} | zoom: ${state.zoom.toFixed(2)}`;
  }

  build() {
    Column({ space: 12 }) {
      Column({ space: 4 }) {
        Text('3D 知识图谱')
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .width('100%')
          .textAlign(TextAlign.Start)

        Text('双指缩放、单指拖拽可浏览知识节点')
          .fontSize(13)
          .fontColor('#C9D5F2')
          .width('100%')
          .textAlign(TextAlign.Start)
      }
      .width('100%')
      .padding({ left: 4, right: 4, top: 6, bottom: 6 })

      Column() {
        XComponent({
          id: 'knowledge-graph-xcomponent',
          type: XComponentType.SURFACE,
          controller: this.xController
        })
          .width('100%')
          .height('100%')
          .backgroundColor('#0B132B')
          .onTouch((event: TouchEvent) => {
            this.handleTouch(event);
          })

        Column({ space: 4 }) {
          Text(`节点数：${this.renderNodeCount}`)
            .fontSize(12)
            .fontColor('#E2E8F0')
          Text(this.hudText)
            .fontSize(11)
            .fontColor('#AFC3E8')
        }
        .padding({ left: 10, right: 10, top: 8, bottom: 8 })
        .borderRadius(10)
        .backgroundColor('#1E293BCC')
        .position({ x: 12, y: 12 })
      }
      .width('100%')
      .layoutWeight(1)
      .padding(4)
      .borderRadius(16)
      .backgroundColor('#1A2642')
    }
    .width('100%')
    .height('100%')
    .padding(16)
    .backgroundColor('#0F172A')
  }
}
