# 启动与部署

## Docker

在仓库根目录执行 `docker compose up --build -d --wait --wait-timeout 180`，访问 `http://localhost:8080/?demo=1`。

前端由 Node 24 构建后交给 Nginx；API 为 Python 3.12 非 root 用户（1000:1000），镜像预建 `/state` 权限，新的命名卷继承权限。无需手动 chown 宿主机目录。API 无对外端口；Nginx 代理同源 `/api/` 与 `/healthz`。

```sh
docker compose ps
docker compose logs --tail 80 api web
python tools/smoke.py --base-url http://localhost:8080
docker compose down
```

`down` 保留命名卷；不要为了升级删除状态卷。更新源码后重新构建即可。备份时先 `docker compose stop api`，再备份本项目 state 命名卷及自备数据目录；恢复使用兼容版本，保留原备份。

## 端口和服务器

复制 `.env.example` 为 `.env`，修改 `GOUXU_PORT`。要在自己的服务器监听外部网卡，可设置 `GOUXU_BIND=0.0.0.0`，结合自己的 HTTPS 入口、身份验证和访问限制使用。不要把匿名演示会话机制当作生产账号权限体系，也不要直接开放未审核的私人日志。

Compose 默认项目名为 gouxu；同机已有实例时用 `docker compose -p gouxu-demo ...` 单独部署，并分配不同端口。本开源版不依赖原作者服务器、旧发布目录、预构建私有镜像、SSH 隧道或凭据。

## 可选真实快照

`./data/processed` 只读挂到 `/datasets`。全量构建输出应置于 `data/processed/full_lite/ksl-full-<revision前12位>-v1/`，API 启动时核对来源与各 Parquet 指纹再注册。原件留在 `data/raw/`，不会通过 Nginx `/data/` 暴露。具体见 [数据来源](03_DATA_SOURCES.md)。

首次依赖安装、镜像拉取及真实文件获取需要网络；已缓存的镜像和已处理快照可离线运行。全量处理需要额外磁盘与内存，不能把合成演示的资源用量当作全量性能成绩。
