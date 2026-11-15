// Draw the two 3000x3000 podcast covers into docs/.
//
//     swift podcast/make_covers.swift
//
// CoreText is used instead of Pillow because Arabic needs real shaping:
// macOS fonts ship no Arabic presentation-form glyphs, so pre-shaped strings
// render as empty boxes. The JPEGs are committed to git; this only runs when a
// cover is redesigned.

import CoreGraphics
import CoreText
import Foundation
import ImageIO
import UniformTypeIdentifiers

let size = 3000
let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let docs = root.appendingPathComponent("docs")
let fontDir = "/System/Library/Fonts/Supplemental/"

func color(_ hex: UInt32, _ alpha: CGFloat = 1) -> CGColor {
    CGColor(
        red: CGFloat((hex >> 16) & 0xFF) / 255,
        green: CGFloat((hex >> 8) & 0xFF) / 255,
        blue: CGFloat(hex & 0xFF) / 255,
        alpha: alpha
    )
}

let cream = color(0xEFE3C8)
let gold = color(0xC9A227)
let muted = color(0x9C8B70)

func makeContext() -> CGContext {
    let space = CGColorSpaceCreateDeviceRGB()
    guard
        let context = CGContext(
            data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
            space: space, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )
    else { fatalError("cannot create bitmap context") }
    return context
}

let rtl: CTParagraphStyle = {
    var direction = CTWritingDirection.rightToLeft
    var alignment = CTTextAlignment.center
    return withUnsafeBytes(of: &direction) { directionBytes in
        withUnsafeBytes(of: &alignment) { alignmentBytes in
            let settings = [
                CTParagraphStyleSetting(
                    spec: .baseWritingDirection,
                    valueSize: MemoryLayout<CTWritingDirection>.size,
                    value: directionBytes.baseAddress!),
                CTParagraphStyleSetting(
                    spec: .alignment,
                    valueSize: MemoryLayout<CTTextAlignment>.size,
                    value: alignmentBytes.baseAddress!),
            ]
            return CTParagraphStyleCreate(settings, settings.count)
        }
    }
}()

/// Draws a single line centred on (size/2, topY) in top-down coordinates.
@discardableResult
func drawLine(
    _ context: CGContext, _ text: String, font name: String, size fontSize: CGFloat,
    color: CGColor, topY: CGFloat, maxWidth: CGFloat = 2500, minimum: CGFloat = 36
) -> CGFloat {
    var current = fontSize
    var line: CTLine
    var bounds: CGRect
    repeat {
        let font = CTFontCreateWithName(name as CFString, current, nil)
        let attributed = NSAttributedString(
            string: text,
            attributes: [
                kCTFontAttributeName as NSAttributedString.Key: font,
                kCTForegroundColorAttributeName as NSAttributedString.Key: color,
                kCTParagraphStyleAttributeName as NSAttributedString.Key: rtl,
            ]
        )
        line = CTLineCreateWithAttributedString(attributed)
        bounds = CTLineGetBoundsWithOptions(line, [.useGlyphPathBounds])
        if bounds.width <= maxWidth { break }
        current -= 8
        if current <= minimum { break }
    } while true

    let baseline = CGFloat(size) - topY - (bounds.minY + bounds.height / 2)
    context.textPosition = CGPoint(x: (CGFloat(size) - bounds.width) / 2 - bounds.minX, y: baseline)
    CTLineDraw(line, context)
    return bounds.width
}

func drawOrnament(_ context: CGContext, topY: CGFloat, halfWidth: CGFloat = 420) {
    let y = CGFloat(size) - topY
    context.setStrokeColor(gold.copy(alpha: 0.75)!)
    context.setLineWidth(3)
    context.move(to: CGPoint(x: 1500 - halfWidth, y: y))
    context.addLine(to: CGPoint(x: 1500 - 70, y: y))
    context.move(to: CGPoint(x: 1500 + 70, y: y))
    context.addLine(to: CGPoint(x: 1500 + halfWidth, y: y))
    context.strokePath()

    context.setFillColor(gold.copy(alpha: 0.85)!)
    context.move(to: CGPoint(x: 1500, y: y + 24))
    context.addLine(to: CGPoint(x: 1524, y: y))
    context.addLine(to: CGPoint(x: 1500, y: y - 24))
    context.addLine(to: CGPoint(x: 1476, y: y))
    context.closePath()
    context.fillPath()
}

func drawFrame(_ context: CGContext) {
    context.setStrokeColor(gold.copy(alpha: 0.45)!)
    context.setLineWidth(4)
    context.stroke(CGRect(x: 120, y: 120, width: size - 240, height: size - 240))
    context.setStrokeColor(gold.copy(alpha: 0.22)!)
    context.setLineWidth(2)
    context.stroke(CGRect(x: 146, y: 146, width: size - 292, height: size - 292))
}

func makeCover(
    path: URL, kicker: String, name: String, line1: String, line2: String, tally: String,
    top: UInt32, bottom: UInt32, glowTint: UInt32,
    titleFont: String = "DiwanThuluth", titleSize: CGFloat = 470
) {
    let context = makeContext()
    let space = CGColorSpaceCreateDeviceRGB()

    let gradient = CGGradient(
        colorsSpace: space, colors: [color(top), color(bottom)] as CFArray, locations: [0, 1])!
    context.drawLinearGradient(
        gradient,
        start: CGPoint(x: 0, y: size),
        end: CGPoint(x: 0, y: 0),
        options: []
    )

    let halo = CGGradient(
        colorsSpace: space,
        colors: [color(glowTint, 0.38), color(glowTint, 0.0)] as CFArray,
        locations: [0, 1]
    )!
    context.drawRadialGradient(
        halo,
        startCenter: CGPoint(x: 1500, y: 1650), startRadius: 0,
        endCenter: CGPoint(x: 1500, y: 1650), endRadius: 1500,
        options: []
    )

    drawFrame(context)
    drawLine(context, kicker, font: "AlNile", size: 74, color: muted, topY: 400)
    drawLine(context, name, font: titleFont, size: titleSize, color: cream, topY: 1290, maxWidth: 2300)
    drawOrnament(context, topY: 1700)
    drawLine(context, line1, font: "AlNile", size: 96, color: gold, topY: 1880)
    if !line2.isEmpty {
        drawLine(context, line2, font: "AlNile", size: 74, color: muted, topY: 2025)
    }

    context.setStrokeColor(gold.copy(alpha: 0.35)!)
    context.setLineWidth(2)
    context.move(to: CGPoint(x: 1240, y: CGFloat(size) - 2470))
    context.addLine(to: CGPoint(x: 1760, y: CGFloat(size) - 2470))
    context.strokePath()
    drawLine(context, tally, font: "AlNile", size: 80, color: cream.copy(alpha: 0.92)!, topY: 2560)

    guard let image = context.makeImage() else { fatalError("cannot snapshot cover") }
    try? FileManager.default.createDirectory(
        at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
    guard
        let destination = CGImageDestinationCreateWithURL(
            path as CFURL, UTType.jpeg.identifier as CFString, 1, nil)
    else { fatalError("cannot write \(path.path)") }
    CGImageDestinationAddImage(
        destination, image, [kCGImageDestinationLossyCompressionQuality: 0.82] as CFDictionary)
    guard CGImageDestinationFinalize(destination) else {
        fatalError("cannot finalise \(path.path)")
    }
    let attributes = try? FileManager.default.attributesOfItem(atPath: path.path)
    let bytes = (attributes?[.size] as? Int) ?? 0
    let relative = path.path.replacingOccurrences(of: docs.path + "/", with: "")
    print("\(relative): \(String(format: "%.0f", Double(bytes) / 1024)) KiB")
}

makeCover(
    path: docs.appendingPathComponent("cover.jpg"),
    kicker: "أرشيف صوتي · ٢٠٢٦",
    name: "فواز الغسلان",
    line1: "الشعر النبطي · القصص · الأمثال",
    line2: "أرشيف الراوي",
    tally: "١٩٩ حلقة · ٣٤ ساعة",
    top: 0x0A0907, bottom: 0x2E2012, glowTint: 0x785822
)

makeCover(
    path: docs.appendingPathComponent("kasayet/cover.jpg"),
    kicker: "الأشرطة الأصلية · ٢٠٢٦",
    name: "الكاسيتات",
    line1: "الكاملة · فواز الغسلان",
    line2: "على ترتيب الشريط كما صدر",
    tally: "١٢ كاسيت · ١٤ ساعة ونصف",
    top: 0x060C0A, bottom: 0x142C22, glowTint: 0x1F5A44,
    titleFont: "AlNile-Bold", titleSize: 330
)
