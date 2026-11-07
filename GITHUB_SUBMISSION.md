# 上传自己的 GitHub 仓库

## 使用安全发布副本

使用整理好的 `MemoryOS-GitHub` 目录。它包含已检查的当前代码和 evidence，但不携带原仓库旧 Git 历史。上游非 eval 示例曾包含疑似硬编码 API key；现已移除，未验证其有效性。仅提交删除记录无法清除历史里的值，因此原本地研究仓库不用于上传。原始上游和实际运行提交号仍在文档及证据中，原本地仓库保留完整研究历史。

提交范围包括：README、运行/评分说明、requirements-macos.txt、空值 .env.example、代码和离线检查、固定题单与独立评分参考、225 答案和 450 请求归档、统一快照、建库累计账本、哈希及独立验收。排除 `.env`、虚拟环境、模型权重、下载缓存和 1.4GB 本地 runs。

三个 ZIP 均是公开证据材料，不包含凭据；最大单文件约 29MiB。默认使用普通 Git，无须 Git LFS。提交已保留上游 LICENSE、作者和项目来源。本次是修改后的个人复现，不代表原作者发布的基准成绩。

## 第一步：离线复核

在终端进入安全发布副本（路径有空格时加引号），执行：

```sh
git status --short
git log -1 --oneline
python3 -B eval/verify_submission.py
python3 -B eval/checks/check_secrets.py --history
```

应显示 225 个有效答案、450 次请求、哈希与简化 F1 通过。此步骤不联网、不读 `.env`，也不调用模型。不需要重新安装 eval 全套依赖。

如果需要检查环境导入，先建立 Python 3.11 虚拟环境，安装 requirements-macos.txt，再执行 README 中的离线检查。依赖是原本机版本记录，未做全新安装验证。不要为上传重新运行付费实验。

## 第二步：创建自己的空仓库

在自己的 GitHub 账户中新建仓库，例如 `MemoryOS-Reproduction`，按课程要求选择公开或私有。保持空仓库，不勾选自动生成 README、LICENSE 或 .gitignore，以免首次推送冲突。使用 GitHub 提供的 HTTPS clone 地址；不要把访问令牌写入地址。

## 第三步：设置个人远端并推送

以下命令仅在 **MemoryOS-GitHub 安全发布副本** 中执行。把 YOUR_USERNAME 和 YOUR_REPOSITORY 替换成自己的用户名和仓库名：

```sh
git remote -v
git remote add personal https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u personal main
```

若 `personal` 已存在，先核对 `git remote -v`，确认后用 `git remote set-url personal ...` 更新到自己的仓库。认证由系统凭据管理器、浏览器或 SSH 处理；不要把密码、API key 或 GitHub token 粘贴到聊天和命令 URL。不要推向 BAI-LAB/MemoryOS，不使用 force 或 mirror。

如果使用压缩包而不是已初始化目录：先解压进入代码根目录，执行 `git init -b main`、`git add .`、`git commit -m "Publish completed MemoryOS reproduction with audited evidence"`，然后设置个人远端并推送。压缩包不包含 `.git`。

## 第四步：网页验收

打开自己的仓库，检查 README 表格及链接、evidence 下三份 ZIP、questions.json、scoring_only/references.json、scores.json 和 LICENSE 都存在；确认看不到 `.env`、模型权重或虚拟环境。仓库页面只应有安全发布的新历史，不应包含上游旧提交历史。

提交作业时附自己的仓库 URL，并说明：单对话 25 题、三容量各三次、DeepSeek 替换模型、共享运行修正、简化 F1，不可直接与论文完整基准比较。费用是按已核实历史价格的估算，不是账户实扣。

## 后续更新

继续从安全发布副本修改并执行 `git diff`、秘密扫描和离线核验后再提交。不从原始研究仓库 merge/rebase 旧历史到发布副本；若复制新代码，用文件方式复制并重新审查。原 runs 不应使用 `git add -f` 整体上传。
