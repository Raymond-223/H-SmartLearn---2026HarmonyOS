import { XComponentController } from '@ohos.arkui.XComponent';

interface GraphViewState {
  rotateX: number;
  rotateY: number;
  zoom: number;
}

export class ArkGraphics3DHelper {
  private static controller: XComponentController | null = null;
  private static viewState: GraphViewState = {
    rotateX: 0,
    rotateY: 0,
    zoom: 1
  };

  static init(controller: XComponentController): void {
    this.controller = controller;
    this.viewState = { rotateX: 0, rotateY: 0, zoom: 1 };
  }

  static handleGesture(deltaX: number, deltaY: number): void {
    this.viewState.rotateY = this.viewState.rotateY + deltaX * 0.3;
    this.viewState.rotateX = this.viewState.rotateX + deltaY * 0.2;
    const scaleDelta = (Math.abs(deltaX) + Math.abs(deltaY)) * 0.0005;
    this.viewState.zoom = Math.max(0.6, Math.min(2.2, this.viewState.zoom + scaleDelta));
  }

  static getViewState(): GraphViewState {
    return this.viewState;
  }
}
