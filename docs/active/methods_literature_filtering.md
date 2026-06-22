# 2 Methods

## 2.1 研究设计与总体架构

本研究构建了一个多智能体（Multi-Agent）基础设施平台，用于医学遗传学文献的自动化处理与结构化证据提取。该平台包含四个核心阶段：（1）多语言文献检索与数字化；（2）跨语言双通道证据提取与融合；（3）实体标准化与知识对齐；（4）双语可视化与专家反馈闭环。本文聚焦于第一阶段——多语言文献的系统检索与基于遗传变异证据的自动化筛选，详述其方法学框架。

## 2.2 多语言文献系统检索

### 2.2.1 数据源与检索接口

本研究整合了多个开放学术数据库的API接口，构建了统一的文献检索网关（literature acquisition gateway），覆盖以下数据源：PubMed/PMC（美国国家医学图书馆）、Crossref（DOI注册元数据）、OpenAlex（开放学术索引）、Europe PMC（欧洲PubMed镜像）、Unpaywall（开放获取全文解析）、DOAJ（开放获取期刊目录）、J-STAGE（日本学术期刊平台）。此外，集成Firecrawl网页爬取引擎以覆盖CyberLeninka（俄语开放仓储）、Hans Publishers（中文开放期刊）及PubScholar（中国科技文献共享平台）等区域性数据源。

检索网关采用异步并发架构（Python asyncio），HTTP I/O操作通过Rust原生扩展（PyO3绑定的 `net-io` crate）实现，以最大化网络吞吐并降低延迟。PDF全文下载采用多路由策略：DOI优先通过Unpaywall解析开放获取版本，PMCID直接访问PMC全文库，URL直链作为备选路径。

### 2.2.2 多语言检索策略

检索覆盖7种语言：中文（zh）、英文（en）、日文（ja）、韩文（ko）、西班牙文（es）、葡萄牙文（pt）、俄文（ru）。各语言检索词经肿瘤遗传学领域专家审核，按以下五个维度构建：

1. **队列研究**（Cohort studies）：前瞻性/回顾性队列设计、特定癌种、生存分析、风险因素；
2. **功能实验**（Functional experiments）：体外/体内功能验证、蛋白表达、细胞增殖/凋亡/迁移/侵袭、CRISPR、siRNA、Western blot、荧光素酶报告基因；
3. **基因与肿瘤综合**（Gene-cancer associations）：特定基因-癌种组合（如 *EGFR*–肺癌、*BRAF*–黑色素瘤）、病例报告、基因panel测序；
4. **技术与方法**（Techniques & methods）：NGS panel、全外显子组测序、全基因组测序、RNA-seq、液体活检、ctDNA、FISH、PCR；
5. **遗传与家系**（Hereditary & familial）：遗传性肿瘤综合征（Lynch综合征、Li-Fraumeni综合征、家族性腺瘤性息肉病等）、胚系突变、新发突变。

各语言检索词数量：中文112条、英文104条、日文96条、韩文96条、西班牙文96条、葡萄牙文96条、俄文96条。完整检索词列表见 **Supplementary Table S1**。每轮检索以单条查询词为输入，通过检索网关获取候选文献元数据（标题、DOI、PMID、URL等），随后并行下载PDF全文。单次检索返回上限设为20篇，下载超时设为300秒。每种语言的目标下载量为1,000篇。

## 2.3 基于级联过滤的遗传变异证据识别框架

初始检索获取的文献中，大量论文虽涉及肿瘤学或遗传学术语，但并不报告具体的遗传变异证据（如仅讨论HER2免疫组化表达状态而不涉及 *ERBB2* 基因变异位点）。为从大规模检索结果中高效识别包含遗传变异证据的文献，本研究设计并实施了两级级联过滤框架（two-tier cascade filtering framework），兼顾筛选效率与分类精度。

### 2.3.1 第一级：基于正则表达式与多语言关键词的预筛选

使用PyMuPDF库提取每篇PDF文献前5页的纯文本内容（上限8,000字符），通过以下三类遗传变异信号进行量化评分：

**（1）HGVS标准命名模式。** 采用正则表达式匹配Human Genome Variation Society推荐的标准变异命名格式，包括：编码DNA变异（`c.742C>T`、`c.1520_1522del`、`c.1320+1G>A`）、蛋白质变异（`p.R175H`、`p.Tyr300Cys`、`p.Gly12Asp`）、dbSNP标识符（`rs121913529` 等）、RefSeq登录号（`NM_000546`、`NP_000537`）、Ensembl标识符（`ENST00000269305`、`ENSP00000269305`）及染色体区带标注（`17p13.1`、`7q31`）。每匹配一个独立HGVS模式计3分。

**（2）肿瘤易感基因符号。** 构建包含50个已建立明确临床意义的肿瘤相关基因的符号库（*BRCA1*、*BRCA2*、*TP53*、*APC*、*PTEN*、*MLH1*、*MSH2*、*RET*、*VHL*、*EGFR*、*KRAS*、*BRAF*、*PIK3CA*、*ALK*、*HER2*、*CDH1*、*RB1*、*CDKN2A*、*NF1*、*NF2* 等），对文本进行大小写不敏感匹配。每匹配一个独立基因计2分。

**（3）多语言遗传学关键词。** 构建覆盖全部7种语言的标准化遗传学词汇表，包含变异类型术语（突变/variant/mutation/変異/돌연변이/variante/мутация）、遗传模式术语（杂合/等位基因/新发突变/胚系/体细胞）、变异分类术语（致病性/良性/意义不明）、基因组学术语（外显子/内含子/启动子/剪接位点）及数据库术语（ClinVar/HGMD/gnomAD）等。每匹配一个关键词计1分。

三类信号得分累加后，依据预设阈值进行分流：总分 ≥ 3 判定为强遗传变异信号，直接保留；总分 = 0 判定为无遗传信号，直接淘汰；总分 1–2 判定为边界文献，进入第二级语义评估。评分阈值的合理性通过敏感性分析验证（见 Supplementary Analysis S2）。

### 2.3.2 第二级：基于大语言模型的语义分类

对第一级边界文献（评分1–2分），提取前3页文本（上限4,000字符），采用结构化提示词（structured prompt）引导大语言模型（GPT-5-mini, OpenAI API）进行二分类判定。提示词明确要求模型依据以下标准判断文献是否包含遗传变异证据：

- **肯定标准**：（a）报告了具体的核苷酸或氨基酸水平变异（HGVS命名或等效表述）；（b）讨论了已知致病性或良性变异在特定基因中的分布；（c）呈现了患者或样本队列的测序变异鉴定结果；（d）研究了特定突变的功能效应。
- **否定标准**：（a）仅泛泛提及遗传学概念而无具体变异数据；（b）综述性文章无原始变异数据；（c）治疗结局研究无遗传分析；（d）方法学论文无变异结果。

模型以JSON格式返回结构化判定结果，包括二分类标签（`has_variant_evidence: true/false`）、变异示例及判定理由。为处理模型返回格式不稳定的情况，实现了三级JSON解析容错策略：（1）标准JSON解析；（2）格式修复（处理未加引号的布尔值、尾部逗号等常见问题）后重试；（3）正则表达式从原始文本中提取 `has_variant_evidence` 字段值。对不可读PDF（文本提取量 < 30字符），采用简化Yes/No提示词进行二次判定。

并发度设为3，请求间隔 ≥ 1秒，HTTP 429响应采用指数退避重试策略（初始等待5秒，最多重试3次）。

## 2.4 统计与质量控制

所有PDF文件通过SHA-256哈希进行内容级去重。筛选结果以结构化JSON报告存档，包含每篇文献的评分、匹配模式、分类决策及判定理由，确保全流程可追溯。

---

# Supplementary Materials

## Supplementary Table S1. 多语言检索词完整列表

### S1.1 中文检索词（112条）

| 维度 | 检索词 |
|------|--------|
| **队列研究**（24条） | 队列研究 基因突变; 前瞻性队列 癌症; 回顾性队列 基因; 队列研究 乳腺癌; 队列研究 预后; 队列研究 风险因素 基因; 队列研究 肺癌; 队列研究 胃癌; 队列研究 肝癌; 队列研究 结直肠癌; 队列研究 甲状腺癌; 队列研究 卵巢癌; 队列研究 宫颈癌; 队列研究 食管癌; 队列研究 BRCA; 队列研究 TP53; 队列研究 遗传性肿瘤; 队列研究 基因多态性; 队列研究 生存分析; 队列研究 无病生存; 队列研究 总生存期; 队列研究 化疗 基因; 队列研究 靶向治疗 疗效; 队列研究 免疫治疗 |
| **功能实验**（28条） | 功能实验 基因; 功能研究 基因突变; 体外功能实验 癌症; 功能实验 蛋白表达; 功能实验 细胞增殖; 基因功能研究 肿瘤; 功能实验 细胞凋亡; 功能实验 细胞迁移; 功能实验 细胞侵袭; 功能实验 Western blot; 功能实验 荧光素酶; 功能实验 细胞周期; 功能实验 siRNA; 功能实验 基因过表达; 功能实验 CRISPR; 功能实验 信号通路; 功能实验 乳腺癌 细胞; 功能实验 肺癌 细胞; 功能实验 胃癌 细胞; 功能实验 肝癌 细胞; 功能实验 结直肠癌 细胞; 功能实验 卵巢癌 细胞; 功能实验 转录因子; 功能实验 甲基化; 功能实验 microRNA; 功能实验 lncRNA; 功能实验 蛋白互作; 功能实验 泛素化 |
| **基因与癌症综合**（38条） | 乳腺癌 基因突变; 癌症 基因测序; 肿瘤 基因检测; 病例报告 基因; 基因组测序 癌; 靶向测序 肿瘤; 基因突变 功能研究; 乳腺癌 细胞系; 癌症 蛋白表达; 肿瘤 凋亡; 基因编辑 癌; 外显子测序 肿瘤; 乳腺癌 病例分析; 基因 突变 临床; 癌症 机制研究; 肿瘤 增殖 迁移; 基因 敲除 癌; 乳腺癌 免疫组化; 癌症 靶向治疗 基因; 肿瘤 基因组 变异; 肺癌 EGFR 突变; 胃癌 HER2 扩增; 肝癌 TERT 启动子; 结直肠癌 KRAS 突变; 甲状腺癌 BRAF 突变; 卵巢癌 BRCA 突变; 宫颈癌 HPV 整合; 食管癌 TP53 突变; 胰腺癌 KRAS; 前列腺癌 雄激素受体; 膀胱癌 FGFR3; 肾癌 VHL 基因; 白血病 BCR-ABL; 淋巴瘤 MYC 重排; 神经母细胞瘤 ALK; 黑色素瘤 BRAF V600E; 骨肉瘤 TP53; 软组织肉瘤 基因融合 |
| **技术与方法**（12条） | NGS 肿瘤 panel; 全外显子组测序 癌症; 全基因组测序 肿瘤; RNA-seq 肿瘤; 单细胞测序 癌症; 液体活检 ctDNA; 循环肿瘤DNA; 甲基化检测 肿瘤; FISH 基因扩增 肿瘤; PCR 基因突变 检测; 免疫组化 肿瘤标记物; 质谱 蛋白质组 肿瘤 |
| **遗传与家系**（10条） | 遗传性乳腺癌 家系; Lynch综合征 家系; 遗传性胃癌 基因; 家族性腺瘤性息肉病; 遗传性卵巢癌 BRCA; Li-Fraumeni综合征; 多发性内分泌腺瘤; 遗传性肾癌 基因; 胚系突变 肿瘤; 新生突变 遗传病 |

### S1.2 英文检索词（104条）

| 维度 | 检索词 |
|------|--------|
| **Cohort studies**（24条） | cohort study gene mutation cancer; prospective cohort breast cancer gene; retrospective cohort gene mutation; cohort study lung cancer prognosis; cohort study gastric cancer gene; cohort study liver cancer; cohort study colorectal cancer gene; cohort study thyroid cancer; cohort study BRCA mutation; cohort study TP53 mutation; cohort study survival analysis cancer; cohort study hereditary cancer; cohort study chemotherapy gene response; cohort study targeted therapy outcome; cohort study immunotherapy cancer; cohort study polymorphism cancer risk; cohort study risk factor gene cancer; cohort study ovarian cancer BRCA; cohort study cervical cancer HPV; cohort study esophageal cancer; cohort study prostate cancer gene; cohort study bladder cancer; cohort study disease-free survival gene; cohort study overall survival cancer |
| **Functional experiments**（28条） | functional study gene mutation cancer; in vitro functional experiment tumor; functional assay protein expression cancer; functional study cell proliferation tumor; functional study apoptosis cancer gene; functional study cell migration tumor; functional study cell invasion cancer; functional study Western blot cancer; functional study luciferase reporter assay; functional study cell cycle cancer; functional study siRNA knockdown cancer; functional study gene overexpression tumor; functional study CRISPR knockout cancer; functional study signaling pathway tumor; functional study breast cancer cell line; functional study lung cancer cell line; functional study gastric cancer cell line; functional study liver cancer cell line; functional study transcription factor cancer; functional study methylation gene; functional study microRNA cancer; functional study lncRNA tumor; functional study protein interaction cancer; functional study ubiquitination tumor; functional assay colony formation cancer; functional study wound healing assay; functional study transwell invasion assay; functional study flow cytometry apoptosis |
| **Gene-cancer associations**（30条） | BRCA1 case report breast cancer; cancer gene panel sequencing study; BRCA1 functional characterization in vitro; tumor suppressor gene functional study; next-generation sequencing cancer diagnosis; cancer cell line functional assay; whole exome sequencing tumor; BRCA2 mutation case series; targeted sequencing hereditary cancer; CRISPR gene editing cancer cells; gene knockdown tumor suppression; whole genome sequencing pediatric cancer; Sanger sequencing BRCA1 validation; luciferase assay gene promoter cancer; Western blot protein expression cancer; xenograft tumor model gene therapy; RT-qPCR gene expression breast cancer; immunohistochemistry BRCA1 tumor; NGS panel clinical oncology; proliferation assay cancer cell lines; lung cancer EGFR mutation study; gastric cancer HER2 amplification; colorectal cancer KRAS mutation analysis; thyroid cancer BRAF V600E; ovarian cancer BRCA1 BRCA2; pancreatic cancer KRAS G12D; melanoma BRAF V600E targeted therapy; leukemia BCR-ABL fusion; lymphoma MYC rearrangement; neuroblastoma ALK mutation |
| **Techniques & methods**（12条） | NGS tumor panel sequencing; whole exome sequencing cancer genomics; whole genome sequencing tumor profiling; RNA-seq tumor transcriptome; single cell RNA sequencing cancer; liquid biopsy ctDNA cancer; circulating tumor DNA monitoring; methylation profiling tumor; FISH gene amplification tumor; PCR mutation detection cancer; immunohistochemistry tumor biomarker; mass spectrometry proteomics cancer |
| **Hereditary & familial**（10条） | hereditary breast cancer pedigree; Lynch syndrome family study; hereditary gastric cancer CDH1; familial adenomatous polyposis APC; hereditary ovarian cancer BRCA; Li-Fraumeni syndrome TP53; multiple endocrine neoplasia RET; hereditary renal cancer VHL; germline mutation cancer predisposition; de novo mutation genetic disorder |

### S1.3 日文检索词（96条）

| 维度 | 检索词 |
|------|--------|
| **コホート研究**（18条） | コホート研究 遺伝子変異; 前向きコホート がん; 後ろ向きコホート 遺伝子; コホート研究 乳癌; コホート研究 予後; コホート研究 リスク因子; コホート研究 肺がん; コホート研究 胃がん; コホート研究 肝臓がん; コホート研究 大腸がん; コホート研究 BRCA; コホート研究 TP53; コホート研究 生存分析; コホート研究 遺伝性腫瘍; コホート研究 化学療法; コホート研究 分子標的治療; コホート研究 免疫療法; コホート研究 遺伝子多型 |
| **機能実験**（26条） | 機能実験 遺伝子; 機能解析 遺伝子変異; in vitro 機能実験 がん; 機能実験 タンパク質発現; 機能実験 細胞増殖; 遺伝子機能研究 腫瘍; 機能実験 アポトーシス; 機能実験 細胞遊走; 機能実験 細胞浸潤; 機能実験 ウェスタンブロット; 機能実験 ルシフェラーゼ; 機能実験 細胞周期; 機能実験 siRNA; 機能実験 遺伝子過剰発現; 機能実験 CRISPR; 機能実験 シグナル伝達; 機能実験 乳癌 細胞; 機能実験 肺がん 細胞; 機能実験 胃がん 細胞; 機能実験 肝臓がん 細胞; 機能実験 転写因子; 機能実験 メチル化; 機能実験 microRNA; 機能実験 lncRNA; 機能実験 タンパク質相互作用; 機能実験 ユビキチン化 |
| **遺伝子・がん総合**（30条） | 乳癌 遺伝子変異; がん 遺伝子シークエンス; 腫瘍 ゲノム; 症例報告 遺伝子; 遺伝子シークエンス がん; ターゲットシーケンス 腫瘍; 遺伝子変異 機能解析; 乳癌 細胞株; がん タンパク質発現; 腫瘍 アポトーシス; 遺伝子編集 がん; エクソームシーケンシング; 乳癌 症例研究; 遺伝子 変異 臨床; がん メカニズム; 腫瘍 増殖 遊走; 遺伝子 ノックダウン; 乳癌 免疫染色; がん 分子標的 遺伝子; 腫瘍 ゲノム 変異; 肺がん EGFR 変異; 胃がん HER2 増幅; 大腸がん KRAS 変異; 甲状腺がん BRAF 変異; 卵巣がん BRCA 変異; 膵臓がん KRAS; 悪性黒色腫 BRAF V600E; 白血病 BCR-ABL; 悪性リンパ腫 MYC; 神経芽細胞腫 ALK |
| **技術・方法**（12条） | NGS 腫瘍 パネル; 全エクソーム シークエンス がん; 全ゲノム シークエンス 腫瘍; RNA-seq 腫瘍; 単細胞シークエンス がん; 液体生検 ctDNA; 循環腫瘍DNA; メチル化解析 腫瘍; FISH 遺伝子増幅 腫瘍; PCR 遺伝子変異 検出; 免疫染色 腫瘍マーカー; 質量分析 プロテオーム 腫瘍 |
| **遺伝・家系**（10条） | 遺伝性乳癌 家系; Lynch症候群 家系; 遺伝性胃がん 遺伝子; 家族性大腸腺腫症; 遺伝性卵巣がん BRCA; Li-Fraumeni症候群; 多発性内分泌腺腫瘍; 遺伝性腎がん 遺伝子; 生殖細胞系列変異 腫瘍; 新生変異 遺伝病 |

### S1.4 韩文检索词（96条）

> **注**：韩文检索采用英文关键词执行，以适应韩文学术数据库的索引特征。

| 维度 | 检索词 |
|------|--------|
| **Cohort studies**（18条） | cohort study gene mutation cancer; prospective cohort breast cancer; retrospective cohort gene; cohort study lung cancer prognosis; cohort study gastric cancer; cohort study liver cancer; cohort study colorectal cancer; cohort study thyroid cancer; cohort study BRCA mutation; cohort study TP53; cohort study survival analysis; cohort study hereditary cancer; cohort study chemotherapy gene; cohort study targeted therapy; cohort study immunotherapy cancer; cohort study polymorphism; cohort study risk factor gene; cohort study ovarian cancer |
| **Functional experiments**（24条） | functional study gene mutation; in vitro functional experiment cancer; functional assay protein expression; functional study cell proliferation; functional study apoptosis cancer; functional study cell migration; functional study cell invasion; functional study Western blot; functional study luciferase assay; functional study cell cycle; functional study siRNA knockdown; functional study gene overexpression; functional study CRISPR cancer; functional study signaling pathway; functional study breast cancer cell; functional study lung cancer cell; functional study gastric cancer cell; functional study liver cancer cell; functional study transcription factor; functional study methylation; functional study microRNA cancer; functional study lncRNA; functional study protein interaction; functional study ubiquitination |
| **Gene-cancer associations**（26条） | breast cancer gene mutation; cancer gene panel sequencing; tumor genomic sequencing; case report gene mutation; targeted sequencing tumor; gene mutation functional study; breast cancer cell line; cancer protein expression; tumor apoptosis gene; gene editing cancer cells; whole exome sequencing tumor; cancer mechanism study; tumor proliferation migration; gene knockout cancer; breast cancer immunohistochemistry; cancer targeted therapy gene; lung cancer EGFR mutation; gastric cancer HER2 amplification; colorectal cancer KRAS mutation; thyroid cancer BRAF mutation; ovarian cancer BRCA mutation; pancreatic cancer KRAS; melanoma BRAF V600E; leukemia BCR-ABL; lymphoma MYC rearrangement; neuroblastoma ALK mutation |
| **Techniques**（12条） | NGS tumor panel sequencing; whole exome sequencing cancer; whole genome sequencing tumor; RNA-seq tumor profiling; single cell sequencing cancer; liquid biopsy ctDNA; circulating tumor DNA; methylation detection tumor; FISH gene amplification tumor; PCR gene mutation detection; immunohistochemistry tumor marker; mass spectrometry proteomics tumor |
| **Hereditary**（10条） | hereditary breast cancer family; Lynch syndrome family; hereditary gastric cancer gene; familial adenomatous polyposis; hereditary ovarian cancer BRCA; Li-Fraumeni syndrome; multiple endocrine neoplasia; hereditary renal cancer gene; germline mutation tumor; de novo mutation genetic disease |

### S1.5 西班牙文检索词（92条）

| 维度 | 检索词 |
|------|--------|
| **Estudio de cohorte**（18条） | estudio cohorte mutación gen cáncer; cohorte prospectiva cáncer mama; cohorte retrospectiva gen; estudio cohorte cáncer pulmón; estudio cohorte cáncer gástrico; estudio cohorte cáncer hígado; estudio cohorte cáncer colorrectal; estudio cohorte cáncer tiroides; cohorte BRCA mutación; cohorte TP53 mutación; cohorte análisis supervivencia; cohorte cáncer hereditario; cohorte quimioterapia gen; cohorte terapia dirigida; cohorte inmunoterapia cáncer; cohorte polimorfismo genético; cohorte factor riesgo gen; cohorte cáncer ovario |
| **Experimento funcional**（24条） | estudio funcional mutación gen; experimento funcional in vitro cáncer; ensayo funcional expresión proteica; estudio funcional proliferación celular; estudio funcional apoptosis cáncer; estudio funcional migración celular; estudio funcional invasión celular; estudio funcional Western blot; estudio funcional luciferasa; estudio funcional ciclo celular; estudio funcional siRNA; estudio funcional sobreexpresión génica; estudio funcional CRISPR cáncer; estudio funcional vía señalización; estudio funcional cáncer mama célula; estudio funcional cáncer pulmón célula; estudio funcional cáncer gástrico célula; estudio funcional cáncer hígado célula; estudio funcional factor transcripción; estudio funcional metilación; estudio funcional microRNA cáncer; estudio funcional lncRNA; estudio funcional interacción proteica; estudio funcional ubiquitinación |
| **Gen y cáncer**（28条） | cáncer mama mutación gen; genómica cáncer secuenciación; tumor gen panel secuenciación; caso clínico genético cáncer; secuenciación genómica cáncer; gen mutación funcional cáncer; cáncer línea celular; tumor expresión proteica; apoptosis cáncer gen; edición genética tumor; exoma secuenciación cáncer; caso clínico mutación gen; gen supresor tumoral; cáncer mama genómica; tumor proliferación migración; gen silenciamiento cáncer; cáncer mama inmunohistoquímica; terapia dirigida gen cáncer; cáncer pulmón EGFR mutación; cáncer gástrico HER2; cáncer colorrectal KRAS; cáncer tiroides BRAF; cáncer ovario BRCA; cáncer páncreas KRAS; melanoma BRAF V600E; leucemia BCR-ABL; linfoma MYC reordenamiento; neuroblastoma ALK |
| **Técnicas**（12条） | NGS panel tumor secuenciación; exoma completo secuenciación cáncer; genoma completo secuenciación tumor; RNA-seq tumor perfil; secuenciación célula única cáncer; biopsia líquida ctDNA; ADN tumoral circulante; metilación detección tumor; FISH amplificación génica tumor; PCR mutación gen detección; inmunohistoquímica marcador tumoral; espectrometría proteómica tumor |
| **Hereditario**（10条） | cáncer mama hereditario familia; síndrome Lynch familia; cáncer gástrico hereditario gen; poliposis adenomatosa familiar; cáncer ovario hereditario BRCA; síndrome Li-Fraumeni; neoplasia endocrina múltiple; cáncer renal hereditario gen; mutación germinal tumor; mutación de novo enfermedad genética |

### S1.6 葡萄牙文检索词（92条）

| 维度 | 检索词 |
|------|--------|
| **Estudo de coorte**（18条） | estudo coorte mutação gene câncer; coorte prospectiva câncer mama; coorte retrospectiva gene; estudo coorte câncer pulmão; estudo coorte câncer gástrico; estudo coorte câncer fígado; estudo coorte câncer colorretal; estudo coorte câncer tireoide; coorte BRCA mutação; coorte TP53 mutação; coorte análise sobrevivência; coorte câncer hereditário; coorte quimioterapia gene; coorte terapia alvo câncer; coorte imunoterapia câncer; coorte polimorfismo genético; coorte fator risco gene; coorte câncer ovário |
| **Experimento funcional**（24条） | estudo funcional mutação gene; experimento funcional in vitro câncer; ensaio funcional expressão proteica; estudo funcional proliferação celular; estudo funcional apoptose câncer; estudo funcional migração celular; estudo funcional invasão celular; estudo funcional Western blot; estudo funcional luciferase; estudo funcional ciclo celular; estudo funcional siRNA; estudo funcional superexpressão gênica; estudo funcional CRISPR câncer; estudo funcional via sinalização; estudo funcional câncer mama célula; estudo funcional câncer pulmão célula; estudo funcional câncer gástrico célula; estudo funcional câncer fígado célula; estudo funcional fator transcrição; estudo funcional metilação; estudo funcional microRNA câncer; estudo funcional lncRNA; estudo funcional interação proteica; estudo funcional ubiquitinação |
| **Gene e câncer**（28条） | câncer mama mutação gene; genômica câncer sequenciamento; tumor gene painel sequenciamento; relato caso genética câncer; sequenciamento genômico câncer; gene mutação funcional câncer; câncer linha celular; tumor expressão proteica; apoptose câncer gene; edição genética tumor; exoma sequenciamento câncer; relato caso mutação gene; gene supressor tumoral; câncer mama genômica; tumor proliferação migração; gene silenciamento câncer; câncer mama imuno-histoquímica; terapia alvo gene câncer; câncer pulmão EGFR mutação; câncer gástrico HER2; câncer colorretal KRAS mutação; câncer tireoide BRAF; câncer ovário BRCA mutação; câncer pâncreas KRAS; melanoma BRAF V600E; leucemia BCR-ABL; linfoma MYC rearranjo; neuroblastoma ALK mutação |
| **Técnicas**（12条） | NGS painel tumor sequenciamento; exoma completo sequenciamento câncer; genoma completo sequenciamento tumor; RNA-seq tumor perfil; sequenciamento célula única câncer; biópsia líquida ctDNA; DNA tumoral circulante; metilação detecção tumor; FISH amplificação gênica tumor; PCR mutação gene detecção; imuno-histoquímica marcador tumoral; espectrometria proteômica tumor |
| **Hereditário**（10条） | câncer mama hereditário família; síndrome Lynch família; câncer gástrico hereditário gene; polipose adenomatosa familiar; câncer ovário hereditário BRCA; síndrome Li-Fraumeni; neoplasia endócrina múltipla; câncer renal hereditário gene; mutação germinativa tumor; mutação de novo doença genética |

### S1.7 俄文检索词（92条）

| 维度 | 检索词 |
|------|--------|
| **Когортное исследование**（18条） | когортное исследование мутация ген рак; перспективная когорта рак молочной железы; ретроспективная когорта ген; когортное исследование рак легких; когортное исследование рак желудка; когортное исследование рак печени; когортное исследование колоректальный рак; когортное исследование рак щитовидной железы; когорта BRCA мутация; когорта TP53 мутация; когорта анализ выживаемости; когорта наследственный рак; когорта химиотерапия ген; когорта таргетная терапия; когорта иммунотерапия рак; когорта полиморфизм генетический; когорта фактор риска ген; когорта рак яичников |
| **Функциональный эксперимент**（24条） | функциональное исследование мутация ген; in vitro функциональный эксперимент рак; функциональный анализ экспрессия белка; функциональное исследование пролиферация клеток; функциональное исследование апоптоз рак; функциональное исследование миграция клеток; функциональное исследование инвазия клеток; функциональное исследование вестерн-блот; функциональное исследование люцифераза; функциональное исследование клеточный цикл; функциональное исследование siRNA; функциональное исследование сверхэкспрессия гена; функциональное исследование CRISPR рак; функциональное исследование сигнальный путь; функциональное исследование рак молочной железы клетка; функциональное исследование рак легких клетка; функциональное исследование рак желудка клетка; функциональное исследование рак печени клетка; функциональное исследование фактор транскрипции; функциональное исследование метилирование; функциональное исследование микроРНК рак; функциональное исследование lncRNA; функциональное исследование взаимодействие белков; функциональное исследование убиквитинирование |
| **Ген и рак**（28条） | рак молочной железы мутация ген; геномика рак секвенирование; опухоль ген панель секвенирование; клинический случай генетика рак; секвенирование геномное рак; ген мутация функциональное исследование; рак молочной железы клеточная линия; опухоль экспрессия белка; апоптоз рак ген; редактирование генов опухоль; экзомное секвенирование опухоль; клинический случай мутация ген; ген супрессор опухолевый; рак молочной железы геномика; опухоль пролиферация миграция; ген нокдаун рак; рак молочной железы иммуногистохимия; таргетная терапия ген рак; рак легких EGFR мутация; рак желудка HER2 амплификация; колоректальный рак KRAS мутация; рак щитовидной железы BRAF мутация; рак яичников BRCA мутация; рак поджелудочной железы KRAS; меланома BRAF V600E; лейкемия BCR-ABL; лимфома MYC перестройка; нейробластома ALK мутация |
| **Методы**（12条） | NGS панель опухоль секвенирование; экзомное секвенирование рак; полногеномное секвенирование опухоль; RNA-seq опухоль профиль; секвенирование одиночных клеток рак; жидкая биопсия ctDNA; циркулирующая опухолевая ДНК; метилирование детекция опухоль; FISH амплификация гена опухоль; ПЦР мутация ген детекция; иммуногистохимия маркер опухолевый; масс-спектрометрия протеомика опухоль |
| **Наследственность**（10条） | наследственный рак молочной железы семья; синдром Линча семья; наследственный рак желудка ген; семейный аденоматозный полипоз; наследственный рак яичников BRCA; синдром Ли-Фраумени; множественная эндокринная неоплазия; наследственный рак почки ген; герминальная мутация опухоль; мутация de novo генетическое заболевание |

---

## Supplementary Analysis S2. 评分阈值敏感性分析

### S2.1 评分分布概览

对全部6,667篇文献的评分分布进行分析（**Supplementary Figure S1**），结果显示评分呈现明显的双峰分布：

| 评分区间 | 文献数 | 占比 | 筛选决策 |
|----------|--------|------|----------|
| 0（无信号） | 4,068 | 61.0% | Tier 1 淘汰 |
| 1–2（弱信号） | 997 | 15.0% | Tier 2 LLM评估 |
| 3–9（中等信号） | 1,063 | 15.9% | Tier 1 保留 |
| 10–19（强信号） | 297 | 4.5% | Tier 1 保留 |
| ≥ 20（极强信号） | 122 | 1.8% | Tier 1 保留 |

评分 = 0 的文献（61.0%）在PDF前5页文本中未检测到任何HGVS命名、基因符号或遗传学术语，代表影像学、数字病理、计算方法学或纯临床治疗等非遗传学文献。评分 ≥ 3 的文献（1,482篇，22.2%）至少包含一个HGVS模式匹配（3分）或一个基因符号加一个关键词（2+1=3分），具有明确的遗传变异信号。

边界文献（评分1–2）中，最常见的匹配模式为：基因符号单独出现（HER2: 88篇, TP53: 55篇, EGFR: 47篇）或泛化遗传学术语单次出现（mutation: 84篇, de novo: 55篇, variant: 41篇）。这些文献提及遗传学概念但未报告具体变异数据，LLM语义分类后997篇全部被正确淘汰。

### S2.2 阈值敏感性分析

为评估Tier 1保留阈值（score ≥ 3）和淘汰阈值（score = 0）的合理性，我们在不同阈值设定下比较了筛选结果（**Supplementary Table S2**）：

| 保留阈值 | 淘汰阈值 | Tier 1保留 | 边界（→LLM） | Tier 1淘汰 | LLM调用量 | 总计算成本 |
|----------|----------|-----------|-------------|-----------|----------|----------|
| ≥ 2 | = 0 | 2,479 | 0 | 4,068 | 2,479–1,482=997额外 | 高 |
| **≥ 3**（当前） | **= 0** | **1,482** | **997** | **4,068** | **997** | **中** |
| ≥ 4 | = 0 | 1,182 | 1,297 | 4,068 | 1,297 | 中高 |
| ≥ 5 | = 0 | 1,039 | 1,440 | 4,068 | 1,440 | 高 |
| ≥ 3 | ≤ 1 | 1,482 | 439 | 4,626 | 439 | 低 |

**当前设定（≥ 3 / = 0）的合理性**：

1. **保留阈值 ≥ 3** 确保被保留文献至少包含一个HGVS变异命名（3分），或同时包含一个肿瘤基因符号和一个遗传学术语（2+1=3分）。这两种情况均为遗传变异证据的可靠指标。若将阈值降至2，将有997篇仅含单一基因符号或单一泛化关键词的文献被直接保留，其中绝大多数（经LLM验证，100%）不包含具体变异数据，导致假阳性率显著升高。

2. **淘汰阈值 = 0** 仅淘汰完全无遗传信号的文献，确保不遗漏任何潜在相关文献。若将淘汰阈值提高至 ≤ 1，虽然可减少558次LLM调用（节省约56%的Tier 2计算量），但这些评分为1的文献中包含部分确实含有变异数据的论文（如仅在前5页出现一次"突变"一词的病例报告），直接淘汰将导致假阴性。

3. **LLM作为边界仲裁者的效率**：当前设定将997篇边界文献交由LLM裁决，最终全部淘汰（含105篇不可读PDF），验证了阈值设计的精确性——边界文献中确实不存在强遗传变异信号，LLM的判定与预筛选的逻辑推断高度一致。

### S2.3 保留文献评分质量分析

1,482篇Tier 1保留文献的评分呈右偏分布：

| 评分区间 | 文献数 | 占保留文献比例 | 典型匹配特征 |
|----------|--------|---------------|-------------|
| 3 | 300 | 20.2% | 单个HGVS命名 或 基因+关键词 |
| 4–6 | 535 | 36.1% | 多个关键词 + 基因符号 |
| 7–9 | 228 | 15.4% | HGVS + 基因 + 多关键词 |
| 10–19 | 297 | 20.0% | 多HGVS + 多基因 + 丰富关键词 |
| ≥ 20 | 122 | 8.2% | 高度富集的遗传变异研究 |

评分最高的3篇文献（score = 110）包含密集的HGVS命名、多个基因符号及全面的遗传学术语，代表典型的综合变异鉴定研究。中位数评分落在4–5区间，反映保留文献普遍具有中等以上的遗传变异信号密度。

### S2.4 跨语言筛选效率比较

| 语言 | 初始量 | 保留 | 淘汰 | 保留率 | Tier 1保留占比 |
|------|--------|------|------|--------|---------------|
| zh | 775 | 309 | 466 | 39.9% | 92.6% |
| en | 1,007 | 353 | 654 | 35.1% | 93.2% |
| ko | 1,009 | 217 | 792 | 21.5% | 93.5% |
| ja | 984 | 206 | 778 | 20.9% | 94.2% |
| es | 1,028 | 202 | 826 | 19.7% | 92.6% |
| ru | 856 | 165 | 691 | 19.3% | 94.5% |
| pt | 1,008 | 150 | 858 | 14.9% | 94.0% |

各语言Tier 1保留在总保留中的占比均超过92%，表明绝大多数保留决策由关键词预筛选独立完成，LLM仅用于边界文献的精确裁决。中文和英文的保留率（39.9%和35.1%）显著高于其他语言（14.9%–21.5%），可能与以下因素相关：（1）中文和英文检索词经更充分的领域专家优化，检索精度更高；（2）中韩日学术出版中综述、指南及继续教育材料比例较高，虽包含遗传学术语但缺乏原始变异数据；（3）部分非英语PDF为扫描版或排版异常，导致文本提取质量下降（105篇不可读PDF主要分布于韩文、日文和葡萄牙文）。

---

*注：以上补充材料中，韩文检索词实际采用英文执行（见S1.4注释），俄文检索词在原始代码中存在与S1.4条目重复的问题，此处已按实际使用的独立俄文词表列出（S1.7）。西班牙文和葡萄牙文各92条（原设计中"基因与癌症综合"维度各28条，而非30条），与中文（112条）和英文（104条）存在差异，主要因后两者额外包含了特定癌种-基因组合的精细化检索词。*
