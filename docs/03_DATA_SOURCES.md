# 数据来源与可选真实数据

默认随代码提供的是自建 synthetic fixture（336 请求、28 商品）。真实数据是独立、可选的输入，未随开源仓库分发。

## 固定来源

- 作者项目：[benchen4395/KuaiSearch](https://github.com/benchen4395/KuaiSearch)
- 数据：[Hugging Face KuaiSearch](https://huggingface.co/datasets/benchen4395/KuaiSearch)
- 已记录的论文版本：[arXiv v4](https://arxiv.org/html/2602.11518v4)，Appendix C/G。
- 唯一来源锁：[source.lock.json](../contracts/source.lock.json)，revision `16f555af360f6a86209f60eb1f12462f9e25be2c`。

只取 `recall_lite/train.jsonl` 与 `items_lite/train.jsonl`，合计约 3.05 GB。不取全仓、rank、users，不安装训练框架。哈希验证只证明文件完整性，语义仍需后续审计。

Lite 保留 2025 历史窗口内连续一个月；不能称两个月或实时数据。具体绝对月份未明确，时间为相对索引。数据集页面 MIT 标签与论文 v4 Appendix G 的 CC BY 4.0 声明差异仍待核。本项目 MIT 许可证不替上游数据清除该差异，也不授权真实数据再分发；下载确认参数只表示已阅读提示。

## 下载与构建

先安装 API 依赖；下载器另使用工具依赖：

```sh
python -m pip install -r requirements-tools.lock.txt
python tools/download_data.py --plan
```

核对实际用途与上游条件后，才主动执行：

```sh
python tools/download_data.py --download --accept-source-license --ack-license-discrepancy
```

手工获取也可放进 `data/raw/<revision>/` 相应子目录，然后运行 `python tools/download_data.py --verify-local`。

```sh
python tools/build_full_lite.py --raw-root data/raw --lock contracts/source.lock.json --output data/processed/full_lite --reports reports/full-lite --memory 384MB
```

构建器全扫描、保留完整请求列表并校验唯一键，输出独立快照；不会覆盖已存在输出。失败时保留 staging 和日志供检查，不能删错误记录或改变预期哈希冒充通过。重启自己的 API 以注册成功快照。Windows 原生注册全量快照可能受目录符号链接权限影响，使用 Docker 路径即可，不修改系统安全策略。

预留至少约 12 GB 工作空间是初始预算，实际需按环境评估。`source.lock.json` 中本地取得状态描述原始来源锁记录，当前机器是否取得由实际哈希校验判断。发布仓库不附真实字段原文、用户/会话标识、衍生 Parquet、导出或状态库。
