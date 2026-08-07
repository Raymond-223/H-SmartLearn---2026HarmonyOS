import { describe, it, expect } from '@ohos/hypium';
import { SelectionStateUtil } from '../main/ets/utils/SelectionStateUtil';

export default function localUnitTest() {
  describe('SelectionStateUtil', () => {
    it('records answers without mutating previous state', 0, () => {
      const original: string[] = SelectionStateUtil.empty(3);
      const updated: string[] = SelectionStateUtil.replace(original, 1, 'B');
      expect(original[1]).assertEqual('');
      expect(updated[1]).assertEqual('B');
      expect(SelectionStateUtil.answeredCount(updated)).assertEqual(1);
      expect(SelectionStateUtil.allAnswered(updated, 3)).assertFalse();
      expect(SelectionStateUtil.firstUnanswered(updated)).assertEqual(0);
    });

    it('unlocks submit only after every question is answered', 0, () => {
      let answers: string[] = SelectionStateUtil.empty(3);
      answers = SelectionStateUtil.replace(answers, 0, 'A');
      answers = SelectionStateUtil.replace(answers, 1, 'B');
      answers = SelectionStateUtil.replace(answers, 2, 'C');
      expect(SelectionStateUtil.answeredCount(answers)).assertEqual(3);
      expect(SelectionStateUtil.allAnswered(answers, 3)).assertTrue();
      expect(SelectionStateUtil.firstUnanswered(answers)).assertEqual(-1);
    });
  });
}
