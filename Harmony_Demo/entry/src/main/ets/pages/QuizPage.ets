import { AiInference } from '../business/AiInference';
import router from '@ohos.router';

interface QuizOption {
  label: string;
  value: string;
}

interface QuizQuestion {
  id: string;
  title: string;
  options: QuizOption[];
}

@Entry
@Component
struct QuizPage {
  @State private selectedValue: string = '';
  private question: QuizQuestion = {
    id: 'q_001',
    title: '以下哪一项最符合“万物互联”的核心价值？',
    options: [
      { label: 'A. 仅提升单机性能', value: 'A' },
      { label: 'B. 设备、数据、服务协同', value: 'B' },
      { label: 'C. 只关注 UI 动画效果', value: 'C' },
      { label: 'D. 降低网络连接能力', value: 'D' }
    ]
  };

  private async onSubmit(): Promise<void> {
    if (!this.selectedValue) {
      return;
    }

    await AiInference.processAnswer(this.question.id, this.selectedValue);
    router.pushUrl({ url: 'pages/Graph3DPage' });
  }

  build() {
    Column() {
      Column({ space: 8 }) {
        Text('鸿蒙智学')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1A1A1A')
          .width('100%')
          .textAlign(TextAlign.Start)

        Text('智能答题评估')
          .fontSize(14)
          .fontColor('#666666')
          .width('100%')
          .textAlign(TextAlign.Start)
      }
      .width('100%')
      .margin({ bottom: 16 })

      Column({ space: 14 }) {
        Text(this.question.title)
          .fontSize(20)
          .fontWeight(FontWeight.Medium)
          .width('100%')
          .textAlign(TextAlign.Start)

        Column({ space: 10 }) {
          ForEach(this.question.options, (item: QuizOption) => {
            Row() {
              Radio({
                value: item.value,
                group: 'quiz-options'
              })
                .checked(this.selectedValue === item.value)
                .onChange((isChecked: boolean) => {
                  if (isChecked) {
                    this.selectedValue = item.value;
                  }
                })

              Text(item.label)
                .fontSize(16)
                .margin({ left: 8 })
            }
            .width('100%')
            .padding(14)
            .borderRadius(12)
            .backgroundColor(this.selectedValue === item.value ? '#EAF3FF' : '#FFFFFF')
            .border({
              width: 1,
              color: this.selectedValue === item.value ? '#4A90E2' : '#E9ECF1'
            })
          }, (item: QuizOption) => item.value)
        }
        .width('100%')
      }
      .width('100%')
      .padding(16)
      .borderRadius(16)
      .backgroundColor('#F8FAFF')

      Blank()
        .layoutWeight(1)

      Button('提交并查看图谱')
        .width('100%')
        .height(48)
        .enabled(!!this.selectedValue)
        .fontSize(17)
        .fontWeight(FontWeight.Medium)
        .backgroundColor(!!this.selectedValue ? '#3B82F6' : '#AFC3E8')
        .onClick(() => {
          this.onSubmit();
        })
    }
    .width('100%')
    .height('100%')
    .padding({ left: 20, right: 20, top: 24, bottom: 20 })
    .backgroundColor('#F2F4F7')
    .justifyContent(FlexAlign.Start)
    .alignItems(HorizontalAlign.Start)
  }
}
