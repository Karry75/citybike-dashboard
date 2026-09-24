# citybike 城市换电运营看板

城市共享单车 / 换电柜运营数据看板的前端 + 数据抽取构建管线源码。覆盖用户、网点、设备、电池、财务、销售、套餐、优惠券、运维、风险预警等 10+ 业务模块，以及 4 块运营指挥大屏。

> 本仓库是**源码与离线 Demo**，不含任何业务数据与数据库凭据（见下方「安全说明」）。看板真实数据由阿里云 ADB（sharing-citybike-pro）抽取构建，已部署在 CloudStudio 公网，可在线访问。

## 仓库内容

| 路径 | 说明 |
|------|------|
| `scripts/` | Python 抽取 / 打包 / 构建管线（约 160+ 脚本，含 GEngine 列式包构建、各模块 extract_*、server.py 实时接口） |
| `html/` | 前端模板 `template.html`（ECharts 驾驶舱），及 `site_view.html` / `user_view.html` 子视图 |
| `html/assets/` | 前端静态资源（JS / CSS / 字体 / 图表库） |
| `citybike_offline.html` | **离线 Demo 单文件**（4.5MB，数据已内联），克隆后双击即可打开看板，无需后端 |
| `config/backup_config.example.json` | 数据库凭据结构示例（真实凭据请放 `config/backup_config.json`，已被 .gitignore 排除） |
| `requirements.txt` | Python 依赖 |

## 在线 Demo（CloudStudio 部署）

- 主部署（桌面全量版）：https://24fa48f3c8934e3caa044dc94a02559a.sh4.agentos-app.net
- 公网轻量版（手机/微信分享）：https://9ef21e3c09704152b131d3b411f909f4.bj10.agentos-app.net
- 公网全量版（桌面）：https://e24a38f6d0d84dc58809dc4d0de69b6f.bj10.agentos-app.net
- 换电订单明细 EXO 面板：https://ed14642625ff44d19e57bbbe26dc962a.bj9.agentos-app.net
- 局域网（需同网段）：http://192.168.0.102:8097/  （账号 `138****5daa` / `admin888`）

## 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备数据库凭据（参考示例，勿提交真实文件）
cp config/backup_config.example.json config/backup_config.json
# 编辑 config/backup_config.json 填入你的 ADB host / user / password

# 3. 跑抽取 + 构建（示例，具体脚本见 scripts/）
python scripts/extract_dashboard.py
python scripts/build_static_from_template.py

# 4. 启动实时视图（可选）
CB_PORT=8097 python scripts/server.py
```

> 说明：`scripts/` 中少量探查脚本原本内联了数据库密码，已在本仓库中替换为占位符 `<DB_PASSWORD_FROM_CONFIG>`，运行时请改为从 `config/backup_config.json` 或环境变量读取。

## 构建链要点

- **GEngine v2 列式包格式**：`{name}.dict.json.gz`（外置字典）+ `{name}.{0..K-1}.json.gz`（行体）；编码列走字典下标，其余列原值。
- 前端 `template.html` 通过 `E.load()` 懒加载按月切片的数据包，支持「近 90 天默认 + 加载更早 + 导出」。
- 部署走 CloudStudio 静态托管；受单文件 ≤50MB、部署目录 ≤95MB、上传网关 ~70MB 限制，大数据包需按月切片 + 预算裁剪。

## 安全说明

- ❌ **不入库**：`data/`（7.8GB 业务数据）、`config/backup_config.json`（数据库密码）、`server_users.json`、`users_db.json`、`.workbuddy/`、所有 `*.gz` 图片与压缩包。
- ✅ 源码中若有内联密码，已脱敏为占位符。
- Demo 登录 `admin888` 仅用于本地 / 内网演示，公网部署请改用强密码或移除登录入口。

## License

[MIT](LICENSE) © 2026 Karry
