import UIKit
import AVFoundation

enum AnimationEffect: String, CaseIterable, Identifiable {
    case snow = "落雪"
    case sparkles = "星光闪烁"
    case zoom = "缓慢推近"
    case snowZoom = "落雪 + 推近"
    var id: String { rawValue }
}

struct SeededRNG: RandomNumberGenerator {
    var state: UInt64
    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state >> 11
    }
}

/// Renders a short video from a still image by drawing the image frame by
/// frame (the image itself is never redrawn by AI — effects are composited
/// over it, so resolution and detail are preserved).
enum ImageAnimator {
    enum AnimatorError: LocalizedError {
        case badImage, writerFailed
        var errorDescription: String? {
            switch self {
            case .badImage: return "图片读取失败。"
            case .writerFailed: return "动画渲染失败。"
            }
        }
    }

    private struct Flake {
        var x, y, r, swayAmp, phase, alpha: Double
        var wraps, swayCycles: Int
    }
    private struct Sparkle {
        var x, y, r, phase, maxAlpha: Double
        var cycles: Int
    }

    static func renderVideo(image: UIImage, effect: AnimationEffect,
                            duration: Double = 5, fps: Int32 = 30,
                            progress: @escaping (Double) -> Void) async throws -> URL {
        guard let cg = image.cgImage else { throw AnimatorError.badImage }
        var w = cg.width, h = cg.height
        let maxDim = 2560
        if max(w, h) > maxDim {
            let s = Double(maxDim) / Double(max(w, h))
            w = Int((Double(w) * s) / 2) * 2
            h = Int((Double(h) * s) / 2) * 2
        }
        let size = CGSize(width: w, height: h)
        let base = UIImage(cgImage: cg)

        var rng = SeededRNG(state: 42)
        let margin = 48.0
        let travel = Double(h) + 2 * margin
        var flakes: [Flake] = []
        if effect == .snow || effect == .snowZoom {
            let layers: [(Int, ClosedRange<Double>, Int, ClosedRange<Double>)] = [
                (200, 1.4...3.0, 1, 150...210),
                (140, 3.0...6.0, 2, 180...235),
                (55, 6.0...12.0, 3, 205...255),
            ]
            for (count, radii, wraps, alphas) in layers {
                for _ in 0..<count {
                    flakes.append(Flake(
                        x: Double.random(in: 0..<Double(w), using: &rng),
                        y: Double.random(in: 0..<travel, using: &rng),
                        r: Double.random(in: radii, using: &rng),
                        swayAmp: Double.random(in: 8...30, using: &rng),
                        phase: Double.random(in: 0..<(2 * .pi), using: &rng),
                        alpha: Double.random(in: alphas, using: &rng),
                        wraps: wraps,
                        swayCycles: [1, 2, 3].randomElement(using: &rng)!))
                }
            }
        }
        var sparkles: [Sparkle] = []
        if effect == .sparkles {
            for _ in 0..<36 {
                sparkles.append(Sparkle(
                    x: Double.random(in: 20..<Double(w - 20), using: &rng),
                    y: Double.random(in: 20..<Double(h - 20), using: &rng),
                    r: Double.random(in: 8...30, using: &rng),
                    phase: Double.random(in: 0..<(2 * .pi), using: &rng),
                    maxAlpha: Double.random(in: 120...230, using: &rng),
                    cycles: [2, 3, 4].randomElement(using: &rng)!))
            }
        }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("anim-\(UUID().uuidString).mov")
        let writer = try AVAssetWriter(outputURL: url, fileType: .mov)
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: w, AVVideoHeightKey: h,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: w * h * 4,
                AVVideoMaxKeyFrameIntervalKey: fps,
            ],
        ]
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = false
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(
            assetWriterInput: input,
            sourcePixelBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB
            ])
        guard writer.canAdd(input) else { throw AnimatorError.writerFailed }
        writer.add(input)
        writer.startWriting()
        writer.startSession(atSourceTime: .zero)

        let total = Int(duration * Double(fps))
        let renderer = UIGraphicsImageRenderer(size: size)
        for frame in 0..<total {
            while !input.isReadyForMoreMediaData {
                try await Task.sleep(nanoseconds: 10_000_000)
            }
            let t = Double(frame) / Double(total)
            let img = renderer.image { ctx in
                let c = ctx.cgContext
                if effect == .zoom || effect == .snowZoom {
                    let s = 1.0 + 0.08 * t
                    base.draw(in: CGRect(x: (size.width - size.width * s) / 2,
                                         y: (size.height - size.height * s) / 2,
                                         width: size.width * s, height: size.height * s))
                } else {
                    base.draw(in: CGRect(origin: .zero, size: size))
                }
                for f in flakes {
                    let y = (f.y + Double(f.wraps) * travel * t).truncatingRemainder(dividingBy: travel) - margin
                    let x = f.x + sin(2 * .pi * Double(f.swayCycles) * t + f.phase) * f.swayAmp
                    c.setFillColor(UIColor(white: 1, alpha: CGFloat(f.alpha / 255)).cgColor)
                    c.fillEllipse(in: CGRect(x: x - f.r, y: y - f.r, width: 2 * f.r, height: 2 * f.r))
                }
                for sp in sparkles {
                    let s = 0.5 + 0.5 * sin(2 * .pi * Double(sp.cycles) * t + sp.phase)
                    let a = sp.maxAlpha * s * s / 255
                    if a < 0.03 { continue }
                    let r = sp.r * (0.7 + 0.45 * s)
                    c.setFillColor(UIColor(white: 1, alpha: CGFloat(a)).cgColor)
                    var path = CGMutablePath()
                    for k in 0..<8 {
                        let ang = -CGFloat.pi / 2 + CGFloat(k) * .pi / 4
                        let rad = k % 2 == 0 ? r : r * 0.16
                        let p = CGPoint(x: sp.x + rad * cos(ang), y: sp.y + rad * sin(ang))
                        if k == 0 { path.move(to: p) } else { path.addLine(to: p) }
                    }
                    path.closeSubpath()
                    c.addPath(path)
                    c.fillPath()
                }
            }
            autoreleasepool {
                if let frameCG = img.cgImage, let pb = pixelBuffer(from: frameCG, width: w, height: h) {
                    adaptor.append(pb, withPresentationTime: CMTime(value: Int64(frame), timescale: fps))
                }
            }
            progress(Double(frame + 1) / Double(total))
        }
        input.markAsFinished()
        await writer.finishWriting()
        guard writer.status == .completed else { throw AnimatorError.writerFailed }
        return url
    }

    private static func pixelBuffer(from cg: CGImage, width: Int, height: Int) -> CVPixelBuffer? {
        var pb: CVPixelBuffer?
        let attrs: [String: Any] = [
            kCVPixelBufferCGImageCompatibilityKey as String: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
        ]
        CVPixelBufferCreate(kCFAllocatorDefault, width, height,
                            kCVPixelFormatType_32ARGB, attrs as CFDictionary, &pb)
        guard let pb else { return nil }
        CVPixelBufferLockBaseAddress(pb, [])
        defer { CVPixelBufferUnlockBaseAddress(pb, []) }
        guard let ctx = CGContext(
            data: CVPixelBufferGetBaseAddress(pb), width: width, height: height,
            bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(pb),
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue) else { return nil }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
        return pb
    }
}
