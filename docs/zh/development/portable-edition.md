# Windows 携带版

本 fork 在上游安装包之外发布 **Windows x64 携带版**。这是 fork 的长期变体，上游同步时
必须保留。安装版、NSIS 安装器、默认数据根和更新路径均不变。

携带版只由
[`.github/workflows/desktop-portable.yml`](../../../.github/workflows/desktop-portable.yml)
构建，仓库不提供本地携带版构建命令。

## 包与数据布局

发布资产为 `wenyi-desktop-<version>-windows-x64-portable.zip`，解压到本地磁盘上任意
可写位置：

```text
Wenyi-Desktop-<version>-windows-x64-portable/
  wenyi-desktop.exe
  portable.marker
  sidecar/wenyi-engine/wenyi-engine.exe
  README.txt
  LICENSE
```

首次启动在 exe 同目录创建 `data/`，其中包含目录库、项目、日志、锁、WebView 数据、
插件运行时和手动备份。携带版不读写 `%LOCALAPPDATA%\Wenyi\Desktop`。

`data/` 有意位于程序目录内。`apps/desktop/src/paths.rs` 在携带模式下只放行一种重叠：
规范化后的数据根必须等于 `<install>/data`。其他安装目录与数据目录的重叠继续拒绝，
包括 `<install>` 本身、其他子目录，以及与安装目录重叠的 `--data-dir`。显式
`--data-dir` 始终优先于携带版默认值。

## 模式识别

`apps/desktop/src/portable.rs` 负责标记名、数据目录名和携带版应用身份。exe 同目录存在
普通文件 `portable.marker` 时进入携带模式。Rust 父进程向引擎传递 `--portable`；引擎
不会根据自身 sidecar 路径猜测模式。

携带版使用 Toast/任务栏身份 `org.wenyi.desktop.portable`，安装版继续使用
`org.wenyi.desktop`。两个版本可以同时运行，不会互相覆盖 HKCU 注册。

## 更新

携带版使用现有的手动更新模式。**设置 → 关于**可以检查本 fork 的 GitHub Releases，
显示新版本和发行说明，但不会启动 NSIS 安装器。`desktop_update_install` 也会防御性
拒绝携带版。

更新方式：下载新的携带版 ZIP，退出文译，替换程序文件并保留 `data/`。该 ZIP 不进入
签名更新清单。

## 携带版凭据

已保存的模型和 MinerU 密钥加密在 `data/credentials.vault` 中，随文件夹移动，且不会以
明文写入 JSON、SQLite 或日志。

- 随机 32 字节数据密钥使用 AES-256-GCM 加密凭据载荷。
- 数据密钥由口令经 scrypt 派生的密钥包裹（`N=2^15`、`r=8`、`p=1`、16 字节 salt）。
- `data/credentials.dpapi` 可以用 Windows DPAPI 为当前用户缓存数据密钥。它只是便利
  手段：复制到另一台电脑或另一个 Windows 用户后仍保持锁定，需要输入口令。
- **锁定**会清空内存并删除 DPAPI 包裹，下次启动必须输入口令；**解锁**会重新武装。
- 在新电脑或新用户上成功输入口令后，会写入新的 DPAPI 包裹。
- 口令丢失后已保存的密钥无法恢复。删除凭据库可以重置，但不能恢复密钥。

界面位于 **设置 → 通用 → 携带版凭据**。模型和 MinerU 凭据字段在凭据库缺失或锁定时
显示提示。没有可用凭据库时保存仍为 session-only，并在界面上保持可见，不会静默持久化。

多个 Windows 用户共享同一携带文件夹时不承诺自动解锁。DPAPI 包裹属于写入它的用户；
其他用户必须输入口令，最后一次成功写入的包裹会替换之前的包裹。

## 构建与发布

工作流由已发布的 GitHub Release 或手动触发，只在 `windows-latest` 构建：

1. 解析 Git 版本，并把 `WENYI_UPDATE_REPO` 设为工作流所在仓库。
2. 构建原生锁库、安装前端依赖，执行 `pnpm desktop:build --no-bundle`。
3. 校验 GUI PE 子系统，然后运行 `scripts/release/package_portable.py`。
4. 解压 ZIP，运行 `wenyi-desktop.exe --version`，要求标记和 sidecar 引擎存在；
   ZIP 内不得包含 `data/`。
5. 手动运行上传 workflow artifact；发布时追加 ZIP 和
   `wenyi-desktop-portable-SHA256SUMS.txt`。

手动 `workflow_dispatch` 且 `publish=false` 只产出 artifact；`publish=true` 要求稳定
tag 且 Release 已发布。工作流不调用 `desktop_updates.py`，也不生成更新清单。

打包脚本为 `scripts/release/package_portable.py`；打包进 ZIP 的双语 README 源文件为
`scripts/release/portable-readme.md`。仓库忽略 `*.txt`，所以源文件保留 `.md` 名称，
ZIP 内条目仍是 `README.txt`。

## 验证

验证下载的产物，而不是本地构建：

- 解压到较短的本地可写路径，运行 `wenyi-desktop.exe --version`；
- 确认 `portable.marker` 和 `sidecar/wenyi-engine/wenyi-engine.exe` 存在；
- 在无系统 Python、无外部服务的环境启动，创建项目并确认使用 `data/`；
- 设置口令、保存密钥、重启确认自动解锁，再复制文件夹并确认副本需要口令；
- 确认“检查更新”会显示发行版但不出现安装按钮；
- 测试缺少 WebView2 的提示和未签名 SmartScreen 提醒。

静态工作流契约位于 `packages/core/tests/test_release_packaging.py`。GitHub Actions
语法和真实 Windows 构建只能通过手动运行工作流验证。

## 上游同步保留清单

合并上游改动时，必须保留：

- `portable.marker` 识别、`<exe>/data` 和单一路径布局例外；
- `--portable` 引擎参数和 `org.wenyi.desktop.portable` 身份；
- 仅手动更新与携带版安装拒绝；
- `PortableVault`、DPAPI 包裹和 `CredentialStore` 的 `portable` 存储标签；
- 携带版凭据路由和生成的 schema 条目；
- 设置面板、凭据提示和中英文文案；
- `scripts/release/package_portable.py`、README 源文件和测试；
- `.github/workflows/desktop-portable.yml` 及其契约测试；
- 本页、英文对应页和 `AGENTS.md` 入口。

冲突高发文件：`apps/desktop/src/{paths,main,process,updates}.rs`、
`apps/desktop/src/notifications/{mod,windows}.rs`、
`apps/desktop/backend/wenyi_desktop/{local_credentials,main,desktop}.py`、
`apps/desktop/frontend/src/{platform,DesktopCredential,MinerUCredential,i18n}.tsx`
以及生成的 `packages/shared-schema/src/desktop.d.ts`。上游合并后重新运行携带版单测、
打包测试和 `pnpm check:schema`。

## 限制

- 仅 Windows x64；不提供 Linux/macOS 携带包。
- 引擎是 PyInstaller onedir，因此产物是文件夹而不是单文件 exe。
- 需要 Microsoft Edge WebView2 Runtime；携带包不安装它。
- exe 未做系统代码签名，预期会出现 SmartScreen 提醒。
- Toast 注册会写入一个当前用户级 HKCU 身份，不写入凭据或书籍正文。
- 不自动迁移安装版数据根；旧项目使用“导入现有项目”，设置和密钥需要重新录入。
