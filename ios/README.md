# LiveMaker — your own intoLive, on your iPhone

A tiny local iOS app that does what intoLive does, without intoLive:
no ads, no paywall, no uploads. Everything happens on the phone.

两个功能：

1. **图片动起来** — 选一张静图，选动效（落雪 / 星光闪烁 / 缓慢推近 /
   落雪+推近），App 在本机逐帧渲染出视频（原图只是被叠加动效，
   不会被 AI 重绘），然后存成 Live Photo。
2. **视频转 Live** — 选一段视频，拖动挑一帧做封面，存成 Live Photo。

存好后在「照片」里打开 → 分享 → **用作墙纸**，即可设为动态锁屏。

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
