import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            ImageToLiveView()
                .tabItem { Label("图片动起来", systemImage: "photo.on.rectangle.angled") }
            VideoToLiveView()
                .tabItem { Label("视频转 Live", systemImage: "livephoto") }
        }
    }
}
