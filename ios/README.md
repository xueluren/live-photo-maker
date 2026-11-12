# LiveMaker — your own intoLive, on your iPhone

A tiny local iOS app that does what intoLive does, without intoLive:
free for users, no paywall, no uploads — the conversion happens on the
phone. It carries one AdMob banner at the top; ads are how it earns.

两个功能：

1. **图片动起来** — 选一张静图，选动效（落雪 / 星光闪烁 / 缓慢推近 /
   落雪+推近），App 在本机逐帧渲染出视频（原图只是被叠加动效，
   不会被 AI 重绘），然后存成 Live Photo。
2. **视频转 Live** — 选一段视频，拖动挑一帧做封面，存成 Live Photo。

存好后在「照片」里打开 → 分享 → **用作墙纸**，即可设为动态锁屏。

## 广告（免费模式的收入来源）

- 顶部横幅用 Google AdMob（SDK 11.0.0，Swift Package Manager 接入），
  代码在 `AdBannerView.swift`，启动时在 `LiveMakerApp` 里初始化，
  并按苹果要求弹一次广告跟踪授权（ATT）。
- **现在接的是 Google 官方测试 ID**（App ID 和横幅位 ID 都是
  `ca-app-pub-3940256099942544…`），只能验证显示、不产生收入。
- 上线前要换成真实 ID，需要 App 所有者本人：
  1. 在 admob.google.com 注册账号并添加这个 App，拿到 App ID（`~` 结尾）
     和横幅广告位 ID（`/` 结尾），分别替换工程里的
     `INFOPLIST_KEY_GADApplicationIdentifier` 和 `AdBannerView.adUnitID`；
  2. 补一份真实 Info.plist 加 `SKAdNetworkItems`（生成式 plist 放不下数组）；
  3. 注意：AdMob 的正式广告要过 readiness review，前提是 App 已上架
     受支持的商店（App Store）并在 AdMob 里关联——没上架的 App 只有
     受限投放，测试/侧载自用基本没有收入；
  4. 永远不要点自己 App 里的真实广告，那是无效流量，会封号。

## 它是怎么工作的

和 intoLive 同一个原理（Apple 官方 PhotoKit 路线，不是文件配对 hack）：

- 生成一个 UUID，用 ImageIO 写进封面 JPEG 的 MakerApple 字典键 `"17"`；
- 用 `AVAssetExportSession` 把同一个 UUID 写进 MOV 的
  `com.apple.quicktime.content.identifier`；
- 用 `PHAssetCreationRequest` 把 `.photo` + `.pairedVideo` 作为一个
  资源存进相册 — 系统就认它为 Live Photo。

## 安装到自己的 iPhone（免费）

和 Pencil Trip Planner 一样的方式：

1. Mac 上用 Xcode 打开 `LiveMaker.xcodeproj`；
2. 选中项目 → Signing & Capabilities → Team 选你自己的 Apple ID
   （Personal Team，免费账号即可；Bundle ID 冲突就改掉末尾）；
3. 数据线连 iPhone，选它为运行目标，按 **⌘R**；
4. iPhone 上：设置 → 通用 → VPN与设备管理 → 信任你的开发者证书；
5. 打开 App，第一次保存时允许相册权限。

免费账号签名的 App 每 **7 天**需要重新连 Mac ⌘R 续签一次。

## 已知限制（v1）

- 本项目在没有 Xcode 的环境里写成，未在真机编译验证过；第一次 ⌘R
  若有报错，把报错发回仓库 issue（或告诉作者），逐个修。
- 视频转 Live 时长不裁剪；很长的视频也能存，但锁屏只播前几秒。
- 图片动起来的渲染在本机逐帧进行，大图（>2560px）会先等比缩小，
  渲染需要几秒到十几秒，属正常。
- 竖拍照片如果带方向标记，v1 按原始像素方向处理，个别照片可能
  需要先在相册里转正。

## English summary

LiveMaker is a local, dependency-free SwiftUI app (iOS 17+). It animates a
still image on-device (snow / sparkles / slow zoom overlays, rendered with
AVAssetWriter) or takes an existing video, then saves a genuine Live Photo
via ImageIO + AVAssetExportSession + PHAssetCreationRequest using one
shared content-identifier UUID. Install it with Xcode and a free personal
team signature; no account, no server, no tracking.
