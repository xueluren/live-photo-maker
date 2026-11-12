import SwiftUI
import AVFoundation

struct VideoToLiveView: View {
    @State private var videoURL: URL?
    @State private var duration = 0.0
    @State private var coverTime = 0.0
    @State private var coverImage: UIImage?
    @State private var showPicker = false
    @State private var busy = false
    @State private var status = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                if let coverImage {
                    Image(uiImage: coverImage)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 420)
                        .cornerRadius(12)
                } else {
                    ContentUnavailableView("还没有选视频",
                                           systemImage: "video",
                                           description: Text("选一段视频，挑一帧做封面，存成 Live Photo。"))
                }

                if videoURL != nil {
                    VStack {
                        Text("封面帧：\(String(format: "%.1f", coverTime)) 秒")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        Slider(value: $coverTime, in: 0...max(duration, 0.1), step: 0.1)
                            .onChange(of: coverTime) { _, _ in
                                Task { await refreshCover() }
                            }
                    }
                }

                Button {
                    showPicker = true
                } label: {
                    Label("选一段视频", systemImage: "video.badge.plus")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                Button {
                    Task { await generate() }
                } label: {
                    Label("存为 Live Photo", systemImage: "livephoto.play")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(videoURL == nil || busy)

                if busy { ProgressView() }

                if !status.isEmpty {
                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                Spacer()
            }
            .padding()
            .navigationTitle("视频转 Live")
            .sheet(isPresented: $showPicker) {
                VideoPickerView { url in
                    videoURL = url
                    status = ""
                    Task { await loadVideo(url) }
                }
            }
        }
    }

    private func loadVideo(_ url: URL) async {
        let asset = AVURLAsset(url: url)
        if let d = try? await asset.load(.duration) {
            duration = d.seconds
            coverTime = 0
        }
        await refreshCover()
    }

    private func refreshCover() async {
        guard let videoURL else { return }
        let asset = AVURLAsset(url: videoURL)
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.requestedTimeToleranceBefore = CMTime(seconds: 0.1, preferredTimescale: 600)
        gen.requestedTimeToleranceAfter = CMTime(seconds: 0.1, preferredTimescale: 600)
        let time = CMTime(seconds: coverTime, preferredTimescale: 600)
        if let cg = try? gen.copyCGImage(at: time, actualTime: nil) {
            coverImage = UIImage(cgImage: cg)
        }
    }

    private func generate() async {
        guard let videoURL else { return }
        busy = true
        status = ""
        do {
            let asset = AVURLAsset(url: videoURL)
            let gen = AVAssetImageGenerator(asset: asset)
            gen.appliesPreferredTrackTransform = true
            gen.requestedTimeToleranceBefore = CMTime(seconds: 0.1, preferredTimescale: 600)
            gen.requestedTimeToleranceAfter = CMTime(seconds: 0.1, preferredTimescale: 600)
            let cg = try gen.copyCGImage(at: CMTime(seconds: coverTime, preferredTimescale: 600),
                                          actualTime: nil)
            guard let data = UIImage(cgImage: cg).jpegData(compressionQuality: 0.95) else {
                throw LivePhotoSaverError.imageWriteFailed
            }
            let cover = FileManager.default.temporaryDirectory
                .appendingPathComponent("cover-\(UUID().uuidString).jpg")
            try data.write(to: cover)
            try await LivePhotoSaver.makeLivePhoto(plainJPEG: cover, video: videoURL)
            status = "已存到相册。在「照片」里打开它 → 分享 → 用作墙纸，就能设成动态锁屏。"
        } catch {
            status = error.localizedDescription
        }
        busy = false
    }
}
