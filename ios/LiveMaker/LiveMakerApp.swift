import SwiftUI
import GoogleMobileAds
import AppTrackingTransparency

@main
struct LiveMakerApp: App {
    init() {
        GADMobileAds.sharedInstance().start(completionHandler: nil)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .onAppear {
                    // Ask once for ad-tracking permission (personalized ads).
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                        if ATTrackingManager.trackingAuthorizationStatus == .notDetermined {
                            ATTrackingManager.requestTrackingAuthorization { _ in }
                        }
                    }
                }
        }
    }
}
