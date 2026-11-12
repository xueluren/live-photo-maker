import SwiftUI
import GoogleMobileAds

/// Top banner ad (AdMob). The app is free; this banner is how it earns.
///
/// Currently wired to Google's official TEST ad unit, so nothing here can
/// earn (or violate policy) yet. Before release, replace:
///   - `adUnitID` below with the real banner ad unit ID (format …/…), and
///   - the `GADApplicationIdentifier` build setting in the project with the
///     real AdMob App ID (format …~…).
/// Never tap live ads in your own app — that's invalid traffic to AdMob.
struct AdBannerView: UIViewRepresentable {
    static let adUnitID = "ca-app-pub-3940256099942544/2934735716" // TEST banner

    func makeUIView(context: Context) -> GADBannerView {
        let banner = GADBannerView(adSize: GADAdSizeBanner)
        banner.adUnitID = Self.adUnitID
        banner.rootViewController = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow }?.rootViewController
        banner.load(GADRequest())
        return banner
    }

    func updateUIView(_ uiView: GADBannerView, context: Context) {}
}
