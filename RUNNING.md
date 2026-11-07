# 运行、恢复与评分命令

所有命令在仓库根目录执行。当前任务只整理提交，不运行付费实验。下列流程将“复核现成结果”和“重新生成回答”分开；不要运行上游 main_loco_parse.py 全量入口。

## 1. 最小离线复核：无需依赖或密钥

Python 3.11：

```sh
python3 -B eval/verify_submission.py
python3 -B eval/checks/check_secrets.py --history
```

第一条直接读 evidence ZIP 并按仓库原简化 F1 复算。第二条适用于安全发布副本，应通过；原始研究仓库因继承上游旧凭据历史会报待审查，不能据删除当前行就上传原历史。扫描不读取 `.env` 内容，不显示匹配值；启发式扫描不能保证发现所有格式的秘密。

## 2. 恢复到原入口所需目录（仅全新副本）

```sh
python3 -B eval/restore_evidence.py
python3 -B eval/restore_evidence.py --restore
python3 -B eval/score_evaluation.py --run-dir runs/eval-results-conv26-v1
python3 -B eval/prepare_evaluation.py --output runs/eval-prepared-conv26-v1
```

恢复脚本先核验公开证据，再将题单/独立参考、只读快照、九份记忆副本和原始结果写入被忽略的 runs。任一目标已存在即拒绝，不覆盖原研究记录。评分只重新计算分数，不生成答案；新 scores.json 写在 runs 副本，不改变 evidence。准备评测脚本创建九份新状态副本，不联网、不下载模型、不发 API。这些命令只需标准库。

## 3. 本机完整 eval 环境

```sh
python3.11 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements-macos.txt
../.venv/bin/python -m pip check
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/offline_check.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_study_data.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_build_runtime.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_evaluation.py
```

requirements-macos.txt 记录实际 macOS arm64 / Python 3.11.9 环境的直接依赖；未验证空环境安装。安装需要网络。最后一组评测检查需要先按第 2 节恢复与准备；使用假 SDK/假嵌入/假 tokenizer，不需要下载资源，不是新实验。费用预留仍执行真实运算逻辑；正式 tokenizer 的真实计数核查另存于 evidence/input-budget-audit.json。检查输出里的“调用 GPT”是原函数在 mock 路径的日志，不代表真实请求。

## 4. 原运行入口与额外前提（本次不执行）

只恢复已完成快照即可继续研究检索，不需要再次付费建库。重新运行前还需本地模型资源：

```sh
# 会下载嵌入权重，不是 API 实验；当前提交整理不执行此命令
../.venv/bin/python -B eval/download_embedding.py
```

下载器已固定本次原权重 revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`，生成本机路径元数据 runs/embedding-download.json，不把原机器绝对路径当作可移植资源。

评测金额预留还需要官方离线 tokenizer，原来源与 ZIP SHA-256 记录在 evidence/evaluation-config.json，期望位置为 runs/deepseek-v4-tokenizer/official.zip 及 deepseek_v4_tokenizer/tokenizer.json、tokenizer_config.json。权重和 tokenizer 均不进 Git；下载后应按记录核验，不能悄悄改用其他分词器。

然后在本地新建 `.env`，按 `.env.example` 填写三个变量，已有文件不覆盖，不将密钥写入 shell 命令或日志。实际使用官方 deepseek-flash、thinking disabled。服务端模型和价格未来可能变化；重新付费前必须重新核实，历史定价不能视为未来价格承诺。

默认评测预览（不加载 API 配置、不创建客户端）：

```sh
../.venv/bin/python -B eval/run_evaluation.py \
  --prepared runs/eval-prepared-conv26-v1 \
  --run-dir runs/eval-new-study \
  --max-requests 450 --max-cost-cny 20
```

只有另行明确批准新付费范围后才添加 `--allow-paid`。当前实验授权已用完，不因命令存在而重新授权。执行器要求工作区干净、全新结果目录，失败不自动重试或用旧答案补齐。

若确需研究重新建库，离线准备与默认预览是：

```sh
../.venv/bin/python -B eval/prepare_study.py --output runs/new-build-preparation
../.venv/bin/python -B eval/build_study.py \
  --prepared runs/new-build-preparation \
  --model-metadata runs/embedding-download.json \
  --run-dir runs/new-build \
  --max-requests 1200 --max-cost-cny 10
```

新建库不是原始付费历史的复跑保证，不能替代所有组应共用的已发布快照。原建库的输出上限修正、停止与获准重发详情见 BUILD_GUIDE.md 和 snapshot.zip 的 provenance。
