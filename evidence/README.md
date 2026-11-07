# 已完成实验的公开证据

本目录从原始只读快照及真实日志复制，不生成新的模型回答，不修改原证据内容。`manifest.json` 固定各文件 SHA-256。

| 文件 | 用途 |
|---|---|
| questions.json | 生成端固定 25 题，仅包含 ID 和题目 |
| selection-manifest.json | 原始索引、类别数、源数据与题单哈希 |
| build_input/ | 无损转换的完整历史对话和 215 页，只用于恢复建库输入 |
| scoring_only/references.json | 标准答案和 evidence，只供离线评分 |
| scores.json | 总体、分类、各轮及逐题简化 F1 |
| verification.json / status.json | 225 答案、450 请求、token、耗时及快照独立核验 |
| evaluation-config.json | 实际运行参数和预算设置；不含凭据 |
| algorithm-audit.json / input-budget-audit.json | 原算法及发送前预留的离线核查 |
| evaluation-raw.zip | 完整逐题结果、450 请求/响应账本、九份运行副本及评分辅助材料 |
| snapshot.zip | 统一 215 页记忆快照、完整性验收及输出上限修正/画像诊断 |
| build-ledger.zip / build-verification.json | 累计 1,052 次建库调用账本、预算/配置及验收 |

ZIP 是原始证据归档，避免大量长提示词和重复记忆文本铺满 Git 工作区；不包含嵌入权重或 `.env`。模型输出、公开数据集人物对话及画像内容是本次复现实验材料。API 请求/响应标识和时间用于核验，不能用于账户认证。

从仓库根目录执行 `python3 -B eval/verify_submission.py` 即可直接读取归档、核验哈希并按原仓库 F1 重新统计。仅用 Python 标准库，无须密钥、第三方依赖或网络，不会解压覆盖本地运行目录。

原实验运行提交号保留在配置与清单中。安全发布副本不携带上游旧 Git 对象，这些提交号是 provenance 标识，不保证能在发布副本中 checkout；原本地仓库完整历史继续保留。
