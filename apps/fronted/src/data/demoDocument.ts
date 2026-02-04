/**
 * Demo 文档数据 - 使用 test_document 文件夹中的真实文献
 * 标题: 小胶质细胞TRPV1在载脂蛋白E4相关帕金森病中的作用
 * DOI: 10.3969/j.issn.1674-8115.2026.02.001
 */
import type { DocumentData, Evidence } from '../types';
import { EvidenceType } from '../types';

// 原文内容 (中文)
export const originalContent = `# 论著·基础研究

## 小胶质细胞TRPV1在载脂蛋白E4相关帕金森病中的作用

吴可馨，鲁佳，吴星雨，虞志华

上海交通大学基础医学院药理学与化学生物学系，上海 201318

### [摘要]

**目的**：探讨小胶质细胞瞬时受体电位香草酸亚型1（transient receptor potential vanilloid 1，TRPV1）对载脂蛋白E4（apolipoprotein E4，ApoE4）相关帕金森病（Parkinson's disease，PD）病理进程的调控作用。

**方法**：繁育 APOE3/Trpv1flox/flox（E3/Trpv1f/f）、APOE4/Trpv1flox/flox（E4/Trpv1f/f）和小胶质细胞特异性 Trpv1 敲除的 Cx3cr1Cre（E4/Trpv1MGKO）小鼠，在上述小鼠黑质致密部（substantia nigra pars compacta，SNpc）注射人 A53T α-突触核蛋白（AAV-hα-syn）。同样方法在 E3/Trpv1f/f 小鼠的 SNpc 注射 AAV-GFP（green fluorescent protein）作为对照。注射 30 d 后，采用旷场实验、牵引力实验、爬杆实验、转棒实验和悬尾实验分析小鼠的运动协调能力和肌肉耐力；采用莫里斯水迷宫实验检测小鼠的空间学习与记忆能力。采用免疫荧光技术，使用酪氨酸羟化酶（tyrosine hydroxylase，TH）和磷酸化 Ser129 α-突触核蛋白 [p-α-syn（Ser129）] 抗体检测小鼠 SNpc 多巴胺能神经元存活和病理性 α-syn 沉积情况；使用离子钙结合接头分子 1（ionized calcium-binding adapter molecule 1，Iba1）和 p-α-syn（Ser129）抗体检测小鼠中脑小胶质细胞的吞噬功能；并采用 BODIPY 493/503 染色观察小胶质细胞、神经元和星形胶质细胞中脂滴积聚情况。

**结果**：牵引力测试结果显示，E4/Trpv1MGKO（AAV-hα-syn）小鼠与 E4/Trpv1f/f（AAV-hα-syn）小鼠相比握力无差异；但其在旷场中的平均速度和行进距离增加，爬杆实验的翻转所需时间（tturn）及下降时间（tLA）显著延长，转棒实验的停留潜伏期缩短，悬尾实验中表现出更强的张力障碍姿势，显示出 E4/Trpv1MGKO 小鼠运动功能障碍加重；莫里斯水迷宫实验中，E4/Trpv1MGKO 小鼠逃避潜伏期明显延长，在目标象限行进距离占比减少，显示小胶质细胞 TRPV1 缺失显著影响 ApoE4 相关 PD 小鼠的空间学习能力。免疫荧光检测显示，E4/Trpv1MGKO（AAV-hα-syn）小鼠 SNpc 多巴胺能神经元丧失加剧，p-α-syn 沉积增多。并且其中脑小胶质细胞吞噬能力增强，脂滴积累增加，但小胶质细胞 TRPV1 缺失并未加剧小鼠星形胶质细胞和神经元中的脂滴积累。

**结论**：小胶质细胞 TRPV1 缺失加速了 ApoE4 介导的 PD 病理进程，破坏了小胶质细胞的脂质代谢稳态。

**[关键词]** 瞬时受体电位香草酸亚型1；小胶质细胞；载脂蛋白E4；帕金森病
**[DOI]** 10.3969/j.issn.1674-8115.2026.02.001

---

### 背景介绍

载脂蛋白E（apolipoprotein E，ApoE）是一种由 299 个氨基酸组成的单链多肽糖蛋白，分子量为 34 kD。作为大脑中主要的脂质转运蛋白，ApoE 在神经元和神经胶质细胞之间进行脂质转移，对维持神经元的代谢完整性至关重要。

帕金森病（Parkinson's disease，PD）是一种常见的、与年龄相关的神经退行性疾病，其发病率随年龄增长呈现快速上升的趋势。

瞬时受体电位香草酸亚型 1（transient receptor potential vanilloid 1，TRPV1）也称为辣椒素受体，是一种具有 Ca2+ 通透性的配体门控非选择性阳离子通道，具有神经保护作用。

---

## 1 材料与方法

### 1.1 实验动物

本研究所用小鼠均为 C57BL/6 背景。Trpv1flox/flox 小鼠购自上海南方模式生物科技股份有限公司；Cx3cr1Cre 小鼠购自美国杰克逊实验室。

### 1.4 行为学实验

病毒注射 30 d 后，对小鼠进行标准化行为学测试以评估其运动协调、平衡及空间学习记忆能力。

- **旷场实验**：用于评估小鼠的自发活动。
- **牵引力实验**：用于评价小鼠肌肉力量和平衡能力。
- **爬杆实验**：用于评估小鼠的运动协调性和平衡性。
- **转棒实验**：用于进一步评估小鼠运动协调和平衡。
- **悬尾实验**：用于评估小鼠张力姿势。
- **莫里斯水迷宫实验**：用于评估小鼠空间学习记忆能力。

### 1.5 免疫荧光染色及图像分析

小鼠麻醉后用 0.9% 氯化钠灌流，左脑半球用 4% 多聚甲醛固定过夜。

---

## 2 结果

### 2.1 Trpv1 敲除加剧 ApoE4 相关 PD 小鼠的行为缺陷

与 AAV-GFP 对照组相比，注射 AAV-hα-syn 后，E3/Trpv1f/f 小鼠产生 PD 样运动缺陷，而 ApoE4 加重了这些行为损伤。

### 2.2 Trpv1 敲除损害 ApoE4 相关 PD 小鼠多巴胺能神经元

通过免疫荧光染色检测分析小鼠 SNpc，结果显示 E4/Trpv1MGKO 小鼠 TH 阳性多巴胺能神经元丧失进一步加重，p-α-syn 沉积增多。

### 2.3 Trpv1 敲除增强 ApoE4 相关 PD 小鼠小胶质细胞吞噬能力

结果显示 E4/Trpv1MGKO 小鼠的吞噬能力进一步增强。

### 2.4 Trpv1 敲除加剧 ApoE4 相关 PD 小鼠小胶质细胞脂滴堆积

BODIPY 免疫染色结果显示，在 E4/Trpv1MGKO 小鼠中，小胶质细胞中性脂质包裹体明显增大，脂滴堆积较 E4/Trpv1f/f 小鼠更为显著。

---

## 3 讨论

本研究构建了携带人 APOE3 或 APOE4 基因的 Trpv1f/f 小鼠，并通过将其与 Cx3cr1Cre 小鼠杂交获得了小胶质细胞特异性 Trpv1 敲除小鼠。

行为学测试表明，小胶质细胞 TRPV1 的缺失加剧了 ApoE4 诱导的 PD 小鼠运动和协调能力的损伤。

综上，本研究表明，小胶质细胞 TRPV1 的缺失通过破坏脂质代谢及加强小胶质细胞的吞噬功能，进一步加速 ApoE4 相关 PD 病理进程。
`;

// 翻译内容 (英文)
export const translatedContent = `# Thesis · Basic Research

## Role of microglia TRPV1 in apolipoprotein E4 associated Parkinson's disease

Wu Kexin, Lu Jia, Wu Xingyu, Yu Zhihua

Department of Pharmacology and Chemical Biology, School of Basic Medical Sciences, Shanghai Jiaotong University, Shanghai 201318, China

### [Abstract]

**Objective**: To investigate the regulation of microglia transient receptor potential vanilloid subtype 1 (TRPV1) on the pathological process of apolipoprotein E4 (ApoE4)-related Parkinson's disease (PD).

**Methods**: APOE3/Trpv1flox/flox (E3/Trpv1f/f), APOE4/Trpv1flox/flox (E4/Trpv1f/f) and microglia-specific Trpv1 knockout mice Cx3cr1Cre (E4/Trpv1MGKO) were bred and injected with human A53T α-synuclein (AAV-hα-syn) into the substantia nigra pars compacta (SNpc). After 30 days, motor function was evaluated using open field test, traction test, pole test, rotarod test, and tail suspension test, while spatial learning was assessed using Morris water maze test.

**Results**: E4/Trpv1MGKO mice exhibited increased mean velocity in open field tests, prolonged time in pole tests, shortened latency in rotarod, indicating aggravated motor dysfunction. Morris water maze showed impaired spatial learning. Immunofluorescence revealed aggravated dopaminergic neuron loss and increased p-α-syn deposition.

**Conclusion**: TRPV1 deficiency in microglia accelerates the pathological progression of ApoE4-associated PD and disrupts lipid metabolic homeostasis in microglia.

**[Key words]** TRPV1; microglia; apolipoprotein E4; Parkinson's disease
**[DOI]** 10.3969/j.issn.1674-8115.2026.02.001

---

### Background

Apolipoprotein E (ApoE) is a single-chain polypeptide glycoprotein composed of 299 amino acids with a molecular weight of 34 kD. As the major lipid transporter in the brain, ApoE carries out lipid transfer between neurons and glial cells.

Parkinson's disease (PD) is a common, age-related neurodegenerative disease.

Transient receptor potential vanilloid 1 (TRPV1) is a ligand-gated non-selective cation channel with Ca2+ permeability. It has neuroprotective effects.

---

## 1 Materials and methods

### 1.1 Experimental animals

Trpv1flox/flox mice were purchased from Shanghai Southern Model Biotechnology. Cx3cr1Cre mice were purchased from Jackson Laboratory.

### 1.4 Behavioral experiments

- **Open field test**: Assess spontaneous activity
- **Traction test**: Evaluate muscle strength and balance
- **Pole test**: Assess motor coordination
- **Rotarod test**: Evaluate motor coordination and balance
- **Tail suspension test**: Evaluate tension posture
- **Morris water maze**: Assess spatial learning and memory

---

## 2 Results

### 2.1 Trpv1 knockout intensified behavioral defects

Compared to controls, E4/Trpv1MGKO mice showed aggravated motor dysfunction.

### 2.2 Trpv1 knockout impairs dopaminergic neurons

E4/Trpv1MGKO mice showed further aggravation of dopaminergic neuron loss.

### 2.3 Trpv1 knockout enhances microglial phagocytosis

Phagocytic ability was further enhanced in knockout mice.

### 2.4 Trpv1 knockout intensified lipid droplet accumulation

Lipid droplet accumulation was more significant in knockout mice.

---

## 3 Discussion

This study showed that deletion of microglia TRPV1 exacerbated behavioral deficits in ApoE4-associated PD mice.
`;

// 证据列表
export const demoEvidences: Evidence[] = [
  {
    id: 'ev-1',
    type: EvidenceType.PS,
    keyword: '小胶质细胞 TRPV1',
    description: 'PS3: Strong experimental evidence showing TRPV1 deficiency in microglia accelerates PD pathology',
    positions: [{ id: 'pos-1-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.95,
  },
  {
    id: 'ev-2',
    type: EvidenceType.PM,
    keyword: 'ApoE4',
    description: 'PM1: APOE4 allele is a well-established genetic risk factor for PD progression',
    positions: [{ id: 'pos-2-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.88,
  },
  {
    id: 'ev-3',
    type: EvidenceType.PM,
    keyword: '脂滴堆积',
    description: 'PM2: Lipid droplet accumulation indicates disrupted lipid metabolic homeostasis',
    positions: [{ id: 'pos-3-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.85,
  },
  {
    id: 'ev-4',
    type: EvidenceType.PP,
    keyword: 'P < 0.05',
    description: 'PP5: Statistically significant results support pathogenic role',
    positions: [{ id: 'pos-4-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.78,
  },
  {
    id: 'ev-5',
    type: EvidenceType.PS,
    keyword: '多巴胺能神经元丧失',
    description: 'PS2: Direct evidence of dopaminergic neuron loss in SNpc',
    positions: [{ id: 'pos-5-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.92,
  },
  {
    id: 'ev-6',
    type: EvidenceType.PP,
    keyword: 'Cx3cr1Cre',
    description: 'PP4: Validated animal model with cell-type specific knockout',
    positions: [{ id: 'pos-6-1', startOffset: 0, endOffset: 0, paragraphIndex: 0 }],
    confidence: 0.82,
  },
];

// 完整文档数据
export const demoDocument: DocumentData = {
  id: 'demo-trpv1-pd',
  title: '小胶质细胞TRPV1在载脂蛋白E4相关帕金森病中的作用',
  originalMarkdown: originalContent,
  translatedMarkdown: translatedContent,
  evidences: demoEvidences,
  createdAt: '2026-01-30',
};

// PDF URL (本地)
export const demoPdfUrl = '/demo.pdf';
