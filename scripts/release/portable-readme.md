Wenyi Desktop - Windows Portable Edition
文译桌面端 - Windows 携带版

1. Extract / 解压
   Extract this folder anywhere writable on a local disk. Keep wenyi-desktop.exe,
   portable.marker and the sidecar folder together.
   将此文件夹解压到本地磁盘上可写的位置，保持 wenyi-desktop.exe、portable.marker
   与 sidecar 文件夹在一起。

2. Run / 启动
   Open wenyi-desktop.exe. No installer is used. Windows may show a SmartScreen
   warning for the unsigned build; verify the download source before continuing.
   直接运行 wenyi-desktop.exe，不需要安装器。未签名构建可能触发 SmartScreen 提醒，
   继续前请确认下载来源可信。

3. WebView2 / 运行库
   Microsoft Edge WebView2 Runtime is required. Windows 10/11 normally has it; if
   startup reports it missing, install the Evergreen Runtime from Microsoft.
   需要 Microsoft Edge WebView2 Runtime。Windows 10/11 通常已安装；若启动提示缺失，
   请从 Microsoft 安装 Evergreen Runtime。

4. Data / 数据
   Projects, settings, plugins, logs, WebView data and upgrade backups live under
   data\ beside the executable. Nothing is written to %LOCALAPPDATA%\Wenyi\Desktop.
   项目、设置、插件、日志、WebView 数据和升级备份都保存在 exe 同目录的 data\ 中，
   不会写入 %LOCALAPPDATA%\Wenyi\Desktop。

5. Backup and update / 备份与更新
   Quit Wenyi completely (including the tray), then copy the whole folder as a
   backup. To update, download the new portable ZIP, quit Wenyi, replace the
   program files and keep data\. Deleting the folder deletes the data too.
   请从托盘完全退出文译后复制整个文件夹作为备份。更新时下载新的携带版 ZIP，退出文译，
   替换程序文件并保留 data\。删除文件夹会同时删除数据。

6. Credentials / 凭据
   Saved API keys are encrypted in data\credentials.vault. Set a passphrase under
   Settings > General > Portable credentials. Windows DPAPI can unlock the vault
   automatically for the same user on the same computer; moving the folder to
   another computer or Windows user requires the passphrase. Losing the passphrase
   makes the saved keys unrecoverable. The vault is per folder, not per program.
   已保存的 API 密钥加密在 data\credentials.vault 中。请在“设置 > 通用 > 携带版
   凭据”中设置口令。同一台电脑的同一 Windows 用户可用 DPAPI 自动解锁；移动文件夹到
   另一台电脑或另一个 Windows 用户后需要输入口令。口令丢失后已保存的密钥无法恢复。
   凭据库属于该文件夹，不随其他 Wenyi 副本共享。

7. Migration / 迁移
   This edition does not migrate the installed edition's data automatically. It
   starts with an empty catalog; use Import existing project for old projects and
   re-enter settings and keys. Installed and portable editions can run together.
   携带版不会自动迁移安装版数据，首次启动使用空目录库；旧项目请使用“导入现有项目”，
   设置和密钥需要重新录入。安装版与携带版可以同时运行。
