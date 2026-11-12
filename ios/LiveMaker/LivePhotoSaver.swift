import Foundation
import AVFoundation
import Photos
import ImageIO
import UniformTypeIdentifiers

enum LivePhotoSaverError: LocalizedError {
    case notAuthorized
    case imageWriteFailed
    case exportFailed
    case saveFailed(String)

    var errorDescription: String? {
        switch self {
        case .notAuthorized: return "没有相册写入权限，请在系统设置里允许。"
        case .imageWriteFailed: return "封面图写入失败。"
        case .exportFailed: return "视频导出失败。"
        case .saveFailed(let msg): return "保存 Live Photo 失败：\(msg)"
        }
    }
}

/// Turns a plain JPEG + a video into a real Live Photo in the photo library,
/// the same way intoLive does — but locally, with no third-party service:
/// one shared UUID is written into the JPEG (MakerApple "17", via ImageIO)
/// and into the MOV (com.apple.quicktime.content.identifier, via an
/// AVAssetExportSession), then both are saved as one PHAsset.
enum LivePhotoSaver {
    static let contentIdentifierKey = "com.apple.quicktime.content.identifier"

    static func requestAddAuthorization() async -> Bool {
        let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        return status == .authorized || status == .limited
    }

    /// Full pipeline. `plainJPEG` is a JPEG file without pairing metadata;
    /// `video` is any video AVFoundation can export (mov/mp4, silent is fine).
    static func makeLivePhoto(plainJPEG: URL, video: URL) async throws {
        guard await requestAddAuthorization() else { throw LivePhotoSaverError.notAuthorized }
        let assetID = UUID().uuidString.uppercased()
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("livemaker-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tmp) }

        let pairedJPEG = tmp.appendingPathComponent("photo.jpg")
        guard writeJPEGWithAssetID(source: plainJPEG, assetID: assetID, destination: pairedJPEG) else {
            throw LivePhotoSaverError.imageWriteFailed
        }
        let pairedMOV = tmp.appendingPathComponent("video.mov")
        guard await exportMOVWithAssetID(source: video, assetID: assetID, destination: pairedMOV) else {
            throw LivePhotoSaverError.exportFailed
        }
        do {
            try await PHPhotoLibrary.shared().performChanges {
                let request = PHAssetCreationRequest.forAsset()
                let options = PHAssetResourceCreationOptions()
                request.addResource(with: .photo, fileURL: pairedJPEG, options: options)
                request.addResource(with: .pairedVideo, fileURL: pairedMOV, options: options)
            }
        } catch {
            throw LivePhotoSaverError.saveFailed(error.localizedDescription)
        }
    }

    /// Writes MakerApple["17"] = assetID into a copy of the JPEG.
    /// ImageIO may re-encode the still; quality stays at the source's level
    /// for typical wallpaper-sized images.
    static func writeJPEGWithAssetID(source: URL, assetID: String, destination: URL) -> Bool {
        guard let src = CGImageSourceCreateWithURL(source as CFURL, nil),
              var props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [AnyHashable: Any],
              let dest = CGImageDestinationCreateWithURL(
                destination as CFURL, UTType.jpeg.identifier as CFString, 1, nil)
        else { return false }
        props[kCGImagePropertyMakerAppleDictionary] = ["17": assetID]
        CGImageDestinationAddImageFromSource(dest, src, 0, props as CFDictionary)
        return CGImageDestinationFinalize(dest)
    }

    /// Exports the video to .mov (passthrough, no re-encode) carrying the
    /// QuickTime content identifier in its movie metadata.
    static func exportMOVWithAssetID(source: URL, assetID: String, destination: URL) async -> Bool {
        let asset = AVURLAsset(url: source)
        guard let session = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetPassthrough)
        else { return false }
        try? FileManager.default.removeItem(at: destination)
        session.outputURL = destination
        session.outputFileType = .mov
        let item = AVMutableMetadataItem()
        item.key = contentIdentifierKey as NSString
        item.keySpace = .quickTimeMetadata
        item.value = assetID as NSString
        item.dataType = "com.apple.metadata.datatype.UTF-8"
        session.metadata = [item]
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            session.exportAsynchronously { cont.resume() }
        }
        return session.status == .completed
    }
}
