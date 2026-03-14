# A/B Experiment Spec

## 实验目标
- 用可控实验方式验证 `W8` 发布链路是否优于 `control`。
- 支持灰度、白名单、人工覆盖与即时终止。

## 路由规则
- 统一使用 `src/release/ab_router.py` 做稳定分桶。
- 分桶键：`experiment_id + salt + subject_key`。
- 默认变体必须存在于配置中，且总流量配比必须等于 `100%`。
- 手工覆盖仅用于 QA、演练、事故定位。

## 指标口径
| 指标 | 说明 | 方向 |
|------|------|------|
| `success_rate` | 请求成功率 | 越高越好 |
| `latency.p95_ms` | P95 延迟 | 越低越好 |
| `cost.avg_per_request` | 单请求平均成本 | 越低越好 |
| `csat` | 用户满意度 | 越高越好 |

## 安全阈值
- `success_rate < 92%`：立即停止实验。
- `latency.p95_ms > 2500`：立即停止实验。
- `cost.avg_per_request` 高于基线 `20%`：冻结放量。

## 实验流程
1. 定义实验配置、责任人、观察窗口与结束条件。
2. 先开白名单验证，再进入 1% 灰度。
3. 每个窗口结束后比较 `control` 与 `treatment`。
4. 任何安全阈值命中时，立刻切回 `control`。

## 结果归档
- 记录实验版本、样本量、关键指标、终止原因、最终决策。
- 复盘结论进入 `docs/reports/w8-launch-review.md`。
