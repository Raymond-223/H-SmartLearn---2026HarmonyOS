import { MasteryLevel } from '../model/MasteryLevel';

export class ColorUtil {
  static masteryToColor(level: MasteryLevel): string {
    switch (level) {
      case MasteryLevel.HIGH:
        return '#22C55E';
      case MasteryLevel.MEDIUM:
        return '#F59E0B';
      case MasteryLevel.LOW:
      default:
        return '#EF4444';
    }
  }
}
