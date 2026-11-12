import SwiftUI

struct ImageToLiveView: View {
    @State private var image: UIImage?
    @State private var showPicker = false
    @State private var effect: AnimationEffect = .snow
    @State private var busy = false
    @State private var progress = 0.0
    @State private var status = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                if let image {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 420)
                        .cornerRadius(12)
                } else {
                    ContentUnavailableView("还没有选图",
                                           systemImage: "photo",
                                           description: Text("选一张静图，给它加上动效，存成 Live Photo。"))
                }

                Picker("动效", selection: $effect) {
                    ForEach(AnimationEffect.allCases) { e in
                        Text(e.rawValue).tag(e)
                    }
                }
                .pickerStyle(.segmented)
                .disabled(image == nil || busy)

                if busy {
                    ProgressView(value: progress)
                    Text("渲染中… \(Int(progress * 100))%")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Button {
                    showPicker = true
                } label: {
                    Label("选一张图", systemImage: "photo.on.rectangle.angled")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                Button {
                    Task { await generate() }
                } label: {
                    Label("动起来，存为 Live Photo", systemImage: "livephoto.play")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(image == nil || busy)

                if !status.isEmpty {
                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                Spacer()
            }
            .padding()
            .navigationTitle("图片动起来")
            .sheet(isPresented: $showPicker) {
                ImagePickerView { picked in
                    image = picked
                    status = ""
                }
            }
        }
    }

    private func generate() async {
        guard let image else { return }
        busy = true
        progress = 0
        status = ""
        do {
            let video = try await ImageAnimator.renderVideo(
                image: image, effect: effect) { p in
                    DispatchQueue.main.async { progress = p }
                }
            guard let data = image.jpegData(compressionQuality: 0.95) else {
                throw LivePhotoSaverError.imageWriteFailed
            }
            let cover = FileManager.default.temporaryDirectory
                .appendingPathComponent("cover-\(UUID().uuidString).jpg")
            try data.write(to: cover)
            try await LivePhotoSaver.makeLivePhoto(plainJPEG: cover, video: video)
            status = "已存到相册。在「照片」里打开它 → 分享 → 用作墙纸，就能设成动态锁屏。"
        } catch {
            status = error.localizedDescription
        }
        busy = false
    }
}
