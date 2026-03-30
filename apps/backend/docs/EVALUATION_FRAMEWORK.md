# 评估框架（EVALUATION_FRAMEWORK）

本文档定义 PS3/BS3 功能证据在本项目中的评估方法、评分逻辑与指标口径，用于对齐文档规范与代码实现。

## 3.1 文献证据评估方法

### 证据来源
1. 科学文献：多源数据库/API/爬取渠道获取的全文或摘要证据（v1.0）。
2. 基因变异信息：文献中出现的基因、变异（HGVS）。
3. 实验方法与结果：功能实验设计、对照、重复、统计结果。
4. 疾病关联：基因-变异-疾病关系与机制描述。

### 证据提取流程
1. 文本预处理：去噪、结构化、规范化。
2. 实体识别：识别基因、变异、蛋白、疾病、实验术语。
3. 关系抽取：抽取基因-变异-疾病-实验之间关系。
4. 实验信息抽取：抽取实验方法、结果、结论、统计信息。

## 3.2 评分系统

基于 ACMG/AMP 功能证据评估标准（PS3/BS3）执行四步法：

1. 步骤1：定义疾病机制
   - 是否清晰定义疾病相关机制。
2. 步骤2：评估实验方法适用性
   - 方法是否适用于该疾病机制；若否，不使用 PS3/BS3。
3. 步骤3：评估实验有效性
   - 3a：是否包含基本对照与重复。
   - 3b：若 3a 不充分，是否为已广泛接受/验证的方法。
   - 3c：若 3a 充分，是否使用已知致病/良性变异对照。
4. 步骤4：应用到个体变异解释
   - 4a：可计算 OddsPath 时按阈值分级。
   - 4b：不可计算 OddsPath 时按对照变异总数分级。

## 3.3 证据强度判断

### 分类
1. No PS3/BS3：方法不适用或实验有效性不达标。
2. Supporting：缺乏已知变异对照，或不可计算 OddsPath 且对照变异总数 `<= 10`。
3. Moderate：不可计算 OddsPath 且对照变异总数 `> 10`，或 OddsPath 落入中等区间。
4. Strong：OddsPath 落入强区间。
5. Very Strong：OddsPath 落入非常强区间。

### OddsPath 阈值
1. Very Strong：`odds_path < 0.0029` 或 `odds_path > 350`
2. Strong：`0.0029 <= odds_path < 0.053` 或 `18.7 < odds_path <= 350`
3. Moderate：`0.053 <= odds_path < 0.23` 或 `4.3 < odds_path <= 18.7`
4. Supporting：其余可用区间

> 说明：方向性映射遵循现有 PS3/BS3 标签体系（`PS3_*` / `BS3_*`），并以变异效应方向（pathogenic 或 benign）决定最终标签。

## 3.4 文档证据评估流程

1. 中间信息提取：从 LLM 输出提取步骤字段与证据条目。
2. 细粒度评估：按四步法逐项比对标准基准。
3. 最终评分：结合步骤结论与 OddsPath/对照变异数输出证据强度。

### 评估维度
1. 信息提取准确性
2. 信息完整性
3. 分类性能
4. 生成质量（幻觉/错误）
5. 可解释性
6. 一致性
7. 效率
8. 可扩展性
9. 临床实用性

## 3.5 评估指标

1. 标准总数（benchmark_total）
2. 模型输出总数（model_output_total）
3. 正确计数（correct_count）
4. 假断言（false_assertions）
5. 字段遗漏（field_omissions）
6. 准确率（accuracy）

### 指标计算口径
- `false_assertions = model_output_total - correct_count`
- `field_omissions = benchmark_total - correct_count`
- `accuracy = correct_count / benchmark_total`（当 `benchmark_total = 0` 时记为 `0.0`）

## 附录 A：PS3/BS3 快速阈值（合并自原速查表）

### OddsPath 阈值（致病方向，PS3）
1. `> 350`：Very Strong（`PS3_very_strong`）
2. `(18.7, 350]`：Strong（`PS3`）
3. `(4.3, 18.7]`：Moderate（`PS3_moderate`）
4. `(1.0, 4.3]`：Supporting（`PS3_supporting`）

### OddsPath 阈值（良性方向，BS3）
1. `[0.23, 1.0)`：Supporting（`BS3_supporting`）
2. `[0.053, 0.23)`：Moderate（`BS3_moderate`）
3. `[0.0029, 0.053)`：Strong（`BS3`）
4. `< 0.0029`：Very Strong（`BS3_very_strong`）
