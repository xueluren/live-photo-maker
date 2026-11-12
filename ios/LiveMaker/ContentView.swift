import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 0) {
            // Free app, paid for by this top banner (AdMob).
            AdBannerView()
                .frame(height: 50)

            TabView {
                ImageToLiveView()
                    .tabItem { Label("图片动起来", systemImage: "photo.on.rectangle.angled") }
                VideoToLiveView()
                    .tabItem { Label("视频转 Live", systemImage: "livephoto") }
            }
        }
    }
}
