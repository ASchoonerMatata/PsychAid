import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var flaskProcess: Process!

    func applicationDidFinishLaunching(_ note: Notification) {
        startFlask()

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "PsychAid"
        window.center()

        let cfg = WKWebViewConfiguration()
        webView = WKWebView(frame: window.contentView!.bounds, configuration: cfg)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self

        let loading = "<html><body style='margin:0;background:#1a2d4f;display:flex;align-items:center;justify-content:center;height:100vh'><p style='color:white;font-family:-apple-system,sans-serif;font-size:18px;opacity:.8'>Starting PsychAid\u{2026}</p></body></html>"
        webView.loadHTMLString(loading, baseURL: nil)

        window.contentView!.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        pollFlask()
    }

    // Intercept PDF/DOCX responses — download instead of navigate
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let mime = navigationResponse.response.mimeType ?? ""
        let downloadTypes = ["application/pdf",
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             "application/octet-stream"]
        if downloadTypes.contains(mime) {
            if #available(macOS 11.3, *) {
                decisionHandler(.download)
            } else {
                // Fallback: open in default app via URL
                if let url = navigationResponse.response.url {
                    NSWorkspace.shared.open(url)
                }
                decisionHandler(.cancel)
            }
        } else {
            decisionHandler(.allow)
        }
    }

    @available(macOS 11.3, *)
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse,
                 didBecome download: WKDownload) {
        download.delegate = self
    }

    // Show Save panel when a download starts
    @available(macOS 11.3, *)
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedFilename
        panel.begin { result in
            completionHandler(result == .OK ? panel.url : nil)
        }
    }

    @available(macOS 11.3, *)
    func downloadDidFinish(_ download: WKDownload) {}

    @available(macOS 11.3, *)
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {}

    func startFlask() {
        guard let resources = Bundle.main.resourcePath else { return }
        let candidates = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        let python = candidates.first { FileManager.default.isExecutableFile(atPath: $0) } ?? "/usr/bin/python3"
        flaskProcess = Process()
        flaskProcess.executableURL = URL(fileURLWithPath: python)
        flaskProcess.arguments = ["\(resources)/app.py"]
        flaskProcess.currentDirectoryURL = URL(fileURLWithPath: resources)
        try? flaskProcess.run()
    }

    func pollFlask(attempt: Int = 0) {
        guard attempt < 60 else { return }
        let url = URL(string: "http://127.0.0.1:5050")!
        URLSession.shared.dataTask(with: url) { data, _, _ in
            DispatchQueue.main.async {
                if data != nil {
                    self.webView.load(URLRequest(url: url))
                } else {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        self.pollFlask(attempt: attempt + 1)
                    }
                }
            }
        }.resume()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        flaskProcess?.terminate(); return true
    }
    func applicationWillTerminate(_ note: Notification) {
        flaskProcess?.terminate()
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
