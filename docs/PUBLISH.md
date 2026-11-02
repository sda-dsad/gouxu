# 发布到 GitHub

只发布本 `gouxu` 目录的内容。不要上传外层课程项目、服务器运行目录或真实数据。

1. 在 GitHub 创建自己的空仓库，例如 `gouxu`；本包已有 README、MIT 和忽略规则，无需让 GitHub 再生成。
2. 在本目录打开终端，执行：

```sh
git init -b main
git add .
git diff --cached --stat
git commit -m "Initial open-source release"
```

3. 复制 GitHub 新仓库页面提供的远程地址，添加并推送：

```sh
git remote add origin https://github.com/YOUR_ACCOUNT/gouxu.git
git push -u origin main
```

将 `YOUR_ACCOUNT` 替换为自己的账号，使用自己的 GitHub 登录方式。也可通过 GitHub Desktop 添加此目录再发布。建议仓库描述：`电商搜索反馈可视化工作台 · Vue 3 / Three.js / FastAPI / DuckDB`；Topics 可选 `data-visualization`、`vue`、`threejs`、`fastapi`、`ecommerce`。

推送后在 Actions 查看 tests 和 docker 两项工作流结果。CI 不需要项目密钥，不自动部署到任何服务器。MIT 的版权署名目前为 `Gouxu contributors`；可按实际权利人补充自己的署名。

发布包文件清单为 `SOURCE_MANIFEST.json`，可用 `python tools/verify_release.py` 核对初始文件完整性。开发修改后与初始清单不一致属于正常变化，新的 Release 应重新生成清单。
