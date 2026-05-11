import { KnowledgeNode } from '../model/KnowledgeNode'
import { MasteryLevel } from '../model/MasteryLevel'
import { Question, QuestionOption } from '../model/Question'
import { LearningPathItem } from '../model/LearningPathItem'

export const cProgrammingKnowledgeNodes: KnowledgeNode[] = [
  new KnowledgeNode(
    'c_basic',
    'C语言基础',
    5,
    [],
    ['c_variable', 'c_datatype', 'c_operator', 'c_control', 'c_array', 'c_function', 'c_pointer']
  ),

  new KnowledgeNode(
    'c_variable',
    '变量与常量',
    4,
    ['c_basic'],
    ['c_datatype', 'c_operator']
  ),

  new KnowledgeNode(
    'c_datatype',
    '基本数据类型',
    5,
    ['c_variable'],
    ['c_operator']
  ),

  new KnowledgeNode(
    'c_operator',
    '运算符与表达式',
    4,
    ['c_variable', 'c_datatype'],
    ['c_control']
  ),

  new KnowledgeNode(
    'c_control',
    '程序控制结构',
    5,
    ['c_operator'],
    ['c_if', 'c_loop']
  ),

  new KnowledgeNode(
    'c_if',
    '条件语句',
    4,
    ['c_control'],
    []
  ),

  new KnowledgeNode(
    'c_loop',
    '循环语句',
    5,
    ['c_control'],
    ['c_array']
  ),

  new KnowledgeNode(
    'c_array',
    '数组',
    5,
    ['c_loop'],
    ['c_function', 'c_pointer']
  ),

  new KnowledgeNode(
    'c_function',
    '函数',
    5,
    ['c_array'],
    ['c_pointer']
  ),

  new KnowledgeNode(
    'c_pointer',
    '指针基础',
    5,
    ['c_array', 'c_function'],
    []
  )
]

export const cProgrammingQuestions: Question[] = [
  new Question(
    'q_c_001',
    'c_variable',
    'single_choice',
    1,
    '在C语言中，下面哪个写法是合法的变量定义？',
    [
      new QuestionOption('A', 'int 1num;'),
      new QuestionOption('B', 'int num;'),
      new QuestionOption('C', 'int for;'),
      new QuestionOption('D', 'int num-1;')
    ],
    'B',
    '变量名不能以数字开头，不能使用关键字，也不能包含减号。'
  ),

  new Question(
    'q_c_002',
    'c_datatype',
    'single_choice',
    1,
    '在C语言中，int 类型通常用于表示什么数据？',
    [
      new QuestionOption('A', '字符'),
      new QuestionOption('B', '整数'),
      new QuestionOption('C', '小数'),
      new QuestionOption('D', '字符串')
    ],
    'B',
    'int 是 integer 的缩写，通常用于表示整数。'
  ),

  new Question(
    'q_c_003',
    'c_operator',
    'single_choice',
    2,
    '表达式 5 / 2 在两个操作数都是 int 的情况下，结果通常是？',
    [
      new QuestionOption('A', '2'),
      new QuestionOption('B', '2.5'),
      new QuestionOption('C', '3'),
      new QuestionOption('D', '报错')
    ],
    'A',
    '两个整数相除会进行整数除法，小数部分被舍去。'
  ),

  new Question(
    'q_c_004',
    'c_if',
    'single_choice',
    1,
    'if 语句主要用于实现哪种程序结构？',
    [
      new QuestionOption('A', '顺序结构'),
      new QuestionOption('B', '选择结构'),
      new QuestionOption('C', '循环结构'),
      new QuestionOption('D', '函数结构')
    ],
    'B',
    'if 语句根据条件是否成立选择执行不同代码，属于选择结构。'
  ),

  new Question(
    'q_c_005',
    'c_loop',
    'single_choice',
    1,
    '下面哪种语句通常用于重复执行一段代码？',
    [
      new QuestionOption('A', 'if'),
      new QuestionOption('B', 'for'),
      new QuestionOption('C', 'return'),
      new QuestionOption('D', 'break')
    ],
    'B',
    'for 语句是 C 语言中常见的循环语句。'
  ),

  new Question(
    'q_c_006',
    'c_array',
    'single_choice',
    2,
    '定义 int a[5]; 后，数组 a 的合法下标范围是？',
    [
      new QuestionOption('A', '1 到 5'),
      new QuestionOption('B', '0 到 5'),
      new QuestionOption('C', '0 到 4'),
      new QuestionOption('D', '-1 到 4')
    ],
    'C',
    'C语言数组下标从 0 开始，所以长度为 5 的数组下标是 0 到 4。'
  ),

  new Question(
    'q_c_007',
    'c_function',
    'single_choice',
    2,
    'C语言中，函数的主要作用是什么？',
    [
      new QuestionOption('A', '保存数据'),
      new QuestionOption('B', '组织可复用代码'),
      new QuestionOption('C', '声明变量'),
      new QuestionOption('D', '结束程序')
    ],
    'B',
    '函数可以把一段功能代码封装起来，便于重复调用。'
  ),

  new Question(
    'q_c_008',
    'c_pointer',
    'single_choice',
    3,
    '在C语言中，指针变量主要保存的是？',
    [
      new QuestionOption('A', '变量的值'),
      new QuestionOption('B', '变量的地址'),
      new QuestionOption('C', '变量的类型'),
      new QuestionOption('D', '变量的名字')
    ],
    'B',
    '指针变量用于保存内存地址。'
  ),

  new Question(
    'q_c_009',
    'c_basic',
    'single_choice',
    1,
    '一个标准 C 程序通常从哪个函数开始执行？',
    [
      new QuestionOption('A', 'printf 函数'),
      new QuestionOption('B', 'scanf 函数'),
      new QuestionOption('C', 'main 函数'),
      new QuestionOption('D', 'include 函数')
    ],
    'C',
    'main 函数是 C 程序的入口，程序运行时通常从 main 函数开始执行。'
  ),

  new Question(
    'q_c_010',
    'c_basic',
    'single_choice',
    1,
    '语句 #include <stdio.h> 的主要作用是什么？',
    [
      new QuestionOption('A', '定义一个变量'),
      new QuestionOption('B', '引入标准输入输出相关声明'),
      new QuestionOption('C', '创建一个循环'),
      new QuestionOption('D', '结束程序运行')
    ],
    'B',
    'stdio.h 是标准输入输出头文件，使用 printf、scanf 等函数时通常需要包含它。'
  ),

  new Question(
    'q_c_011',
    'c_variable',
    'single_choice',
    2,
    '关于局部变量，下列说法正确的是？',
    [
      new QuestionOption('A', '局部变量可以在整个程序任意位置访问'),
      new QuestionOption('B', '局部变量一般只在定义它的代码块内有效'),
      new QuestionOption('C', '局部变量必须定义在 main 函数外部'),
      new QuestionOption('D', '局部变量不能参与运算')
    ],
    'B',
    '局部变量具有局部作用域，通常只能在定义它的函数或代码块内部使用。'
  ),

  new Question(
    'q_c_012',
    'c_datatype',
    'single_choice',
    2,
    '在C语言中，char 类型通常用于存储什么？',
    [
      new QuestionOption('A', '单个字符'),
      new QuestionOption('B', '一整篇文章'),
      new QuestionOption('C', '数组长度'),
      new QuestionOption('D', '函数地址')
    ],
    'A',
    'char 类型通常用于存储单个字符，例如 char ch = \'A\';。'
  ),

  new Question(
    'q_c_013',
    'c_operator',
    'single_choice',
    2,
    '表达式 a % b 中，% 运算符的含义是？',
    [
      new QuestionOption('A', '求商'),
      new QuestionOption('B', '求余数'),
      new QuestionOption('C', '求乘积'),
      new QuestionOption('D', '求地址')
    ],
    'B',
    '% 是取模运算符，用于计算整数除法后的余数。'
  ),

  new Question(
    'q_c_014',
    'c_control',
    'single_choice',
    1,
    '顺序结构、选择结构和循环结构主要描述的是程序的什么？',
    [
      new QuestionOption('A', '存储方式'),
      new QuestionOption('B', '执行流程'),
      new QuestionOption('C', '文件大小'),
      new QuestionOption('D', '编译速度')
    ],
    'B',
    '三种基本控制结构描述程序语句的执行流程，是程序设计的基础。'
  ),

  new Question(
    'q_c_015',
    'c_control',
    'single_choice',
    2,
    '下列哪组语句最能体现“选择结构”和“循环结构”？',
    [
      new QuestionOption('A', 'int 和 char'),
      new QuestionOption('B', 'if 和 for'),
      new QuestionOption('C', 'printf 和 scanf'),
      new QuestionOption('D', 'main 和 return')
    ],
    'B',
    'if 常用于选择结构，for 常用于循环结构。'
  ),

  new Question(
    'q_c_016',
    'c_if',
    'single_choice',
    2,
    '关于 if-else 语句，下列说法正确的是？',
    [
      new QuestionOption('A', 'if 条件成立时执行 else 后面的语句'),
      new QuestionOption('B', 'if 条件不成立时可能执行 else 后面的语句'),
      new QuestionOption('C', 'if-else 只能用于循环'),
      new QuestionOption('D', 'else 必须单独出现，不能和 if 配合')
    ],
    'B',
    'if 条件成立时执行 if 分支，不成立时可以执行 else 分支。'
  ),

  new Question(
    'q_c_017',
    'c_loop',
    'single_choice',
    2,
    '在循环语句中，break 的常见作用是什么？',
    [
      new QuestionOption('A', '立即结束当前循环'),
      new QuestionOption('B', '跳过变量定义'),
      new QuestionOption('C', '声明一个函数'),
      new QuestionOption('D', '输出一个整数')
    ],
    'A',
    'break 常用于跳出当前所在的循环或 switch 结构。'
  ),

  new Question(
    'q_c_018',
    'c_array',
    'single_choice',
    3,
    '对于 int a[3] = {1, 2, 3};，表达式 a[1] 的值是？',
    [
      new QuestionOption('A', '1'),
      new QuestionOption('B', '2'),
      new QuestionOption('C', '3'),
      new QuestionOption('D', '下标越界')
    ],
    'B',
    '数组下标从 0 开始，a[0] 是 1，a[1] 是 2。'
  ),

  new Question(
    'q_c_019',
    'c_function',
    'single_choice',
    3,
    '如果一个函数声明为 int add(int a, int b)，它的返回值类型是？',
    [
      new QuestionOption('A', 'void'),
      new QuestionOption('B', 'char'),
      new QuestionOption('C', 'int'),
      new QuestionOption('D', 'float')
    ],
    'C',
    '函数名前面的 int 表示该函数返回一个 int 类型的结果。'
  ),

  new Question(
    'q_c_020',
    'c_pointer',
    'single_choice',
    3,
    '在C语言中，&x 通常表示什么？',
    [
      new QuestionOption('A', '变量 x 的值'),
      new QuestionOption('B', '变量 x 的地址'),
      new QuestionOption('C', '变量 x 的类型'),
      new QuestionOption('D', '变量 x 的长度')
    ],
    'B',
    '& 是取地址运算符，&x 表示变量 x 在内存中的地址。'
  )
]

export function getInitialCProgrammingMasteryLevels(): MasteryLevel[] {
  let currentTime: number = new Date().getTime()
  let result: MasteryLevel[] = []

  for (let i = 0; i < cProgrammingKnowledgeNodes.length; i++) {
    result.push(new MasteryLevel(cProgrammingKnowledgeNodes[i].id, 0, currentTime))
  }

  return result
}

export function getCProgrammingQuestionsByNodeId(nodeId: string): Question[] {
  let result: Question[] = []

  for (let i = 0; i < cProgrammingQuestions.length; i++) {
    if (cProgrammingQuestions[i].nodeId === nodeId) {
      result.push(cProgrammingQuestions[i])
    }
  }

  return result
}

export function getCProgrammingNodeById(nodeId: string): KnowledgeNode | null {
  for (let i = 0; i < cProgrammingKnowledgeNodes.length; i++) {
    if (cProgrammingKnowledgeNodes[i].id === nodeId) {
      return cProgrammingKnowledgeNodes[i]
    }
  }

  return null
}

export function getDefaultCProgrammingLearningPath(): LearningPathItem[] {
  return [
    new LearningPathItem(
      'c_variable',
      '变量与常量',
      '这是学习 C 语言的基础，需要先理解变量如何存储数据。',
      1,
      0,
      4
    ),

    new LearningPathItem(
      'c_datatype',
      '基本数据类型',
      '理解 int、char、float 等类型，有助于后续学习表达式和数组。',
      2,
      0,
      5
    ),

    new LearningPathItem(
      'c_operator',
      '运算符与表达式',
      '掌握表达式计算规则后，才能更好理解条件判断和循环控制。',
      3,
      0,
      4
    ),

    new LearningPathItem(
      'c_control',
      '程序控制结构',
      '控制结构决定程序执行流程，是从基础语法过渡到程序设计的关键。',
      4,
      0,
      5
    ),

    new LearningPathItem(
      'c_array',
      '数组',
      '数组是批量存储数据的重要结构，也是理解指针前的重要基础。',
      5,
      0,
      5
    ),

    new LearningPathItem(
      'c_function',
      '函数',
      '函数用于组织代码结构，提高代码复用性。',
      6,
      0,
      5
    ),

    new LearningPathItem(
      'c_pointer',
      '指针基础',
      '指针是 C 语言的重点和难点，建议在掌握数组和函数后学习。',
      7,
      0,
      5
    )
  ]
}