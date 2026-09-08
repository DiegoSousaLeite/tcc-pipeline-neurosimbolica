package handlers

import (
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"sync/atomic"

	"github.com/chromedp/cdproto/cdp"
	"github.com/chromedp/cdproto/fetch"
	"github.com/chromedp/cdproto/network"
	"github.com/chromedp/chromedp"
	"github.com/pinchtab/pinchtab/internal/bridge"
	"github.com/pinchtab/pinchtab/internal/web"
)

var resolveDownloadHostIPs = func(ctx context.Context, network, host string) ([]net.IP, error) {
	return net.DefaultResolver.LookupIP(ctx, network, host)
}

var blockedDownloadPrefixes = []netip.Prefix{
	netip.MustParsePrefix("100.64.0.0/10"), // Carrier-grade NAT/shared address space.
	netip.MustParsePrefix("198.18.0.0/15"), // Benchmark/testing networks.
}

type downloadURLGuard struct{}

func newDownloadURLGuard() *downloadURLGuard { return &downloadURLGuard{} }

func (g *downloadURLGuard) Validate(rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("invalid URL")
	}

	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return fmt.Errorf("only http/https schemes are allowed")
	}

	host := strings.TrimSuffix(strings.ToLower(parsed.Hostname()), ".")
	if host == "" || host == "localhost" || strings.HasSuffix(host, ".localhost") {
		return fmt.Errorf("internal or blocked host")
	}

	if ip := net.ParseIP(host); ip != nil {
		return validateDownloadIP(ip)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	ips, err := resolveDownloadHostIPs(ctx, "ip", host)
	if err != nil {
		return fmt.Errorf("could not resolve host")
	}
	for _, ip := range ips {
		if err := validateDownloadIP(ip); err != nil {
			return err
		}
	}
	return nil
}

func validateDownloadIP(ip net.IP) error {
	if ip == nil {
		return fmt.Errorf("private/internal IP blocked")
	}

	addr, ok := netip.AddrFromSlice(ip)
	if !ok {
		return fmt.Errorf("private/internal IP blocked")
	}
	addr = addr.Unmap()
	if addr.IsPrivate() || addr.IsLoopback() || addr.IsLinkLocalUnicast() || addr.IsLinkLocalMulticast() || addr.IsInterfaceLocalMulticast() || addr.IsMulticast() || addr.IsUnspecified() {
		return fmt.Errorf("private/internal IP blocked")
	}
	for _, prefix := range blockedDownloadPrefixes {
		if prefix.Contains(addr) {
			return fmt.Errorf("private/internal IP blocked")
		}
	}
	return nil
}

// validateDownloadURL blocks file://, internal hosts, private IPs, and cloud metadata.
// Only public http/https URLs are allowed.
func validateDownloadURL(rawURL string) error {
	return newDownloadURLGuard().Validate(rawURL)
}

type downloadRequestGuard struct {
	validator    *downloadURLGuard
	maxRedirects int
	redirects    atomic.Int32

	mu         sync.Mutex
	blockedErr error
}

func newDownloadRequestGuard(validator *downloadURLGuard, maxRedirects int) *downloadRequestGuard {
	return &downloadRequestGuard{
		validator:    validator,
		maxRedirects: maxRedirects,
	}
}

func (g *downloadRequestGuard) Validate(rawURL string, redirected bool) error {
	if err := g.validator.Validate(rawURL); err != nil {
		return fmt.Errorf("unsafe browser request: %w", err)
	}
	if redirected && g.maxRedirects >= 0 {
		count := int(g.redirects.Add(1))
		if count > g.maxRedirects {
			return fmt.Errorf("%w: got %d, max %d", bridge.ErrTooManyRedirects, count, g.maxRedirects)
		}
	}
	return nil
}

func (g *downloadRequestGuard) NoteBlocked(err error) {
	g.mu.Lock()
	if g.blockedErr == nil {
		g.blockedErr = err
	}
	g.mu.Unlock()
}

func (g *downloadRequestGuard) BlockedError() error {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.blockedErr
}

// HandleDownload fetches a URL using the browser's session (cookies, stealth)
// and returns the content. This preserves authentication and fingerprint.
//
// GET /download?url=<url>[&tabId=<id>][&output=file&path=/tmp/file][&raw=true]
func (h *Handlers) HandleDownload(w http.ResponseWriter, r *http.Request) {
	if !h.Config.AllowDownload {
		web.ErrorCode(w, 403, "download_disabled", web.DisabledEndpointMessage("download", "security.allowDownload"), false, map[string]any{
			"setting": "security.allowDownload",
		})
		return
	}
	dlURL := r.URL.Query().Get("url")
	if dlURL == "" {
		web.Error(w, 400, fmt.Errorf("url parameter required"))
		return
	}

	validator := newDownloadURLGuard()
	if err := validator.Validate(dlURL); err != nil {
		web.Error(w, 400, fmt.Errorf("unsafe URL: %w", err))
		return
	}

	output := r.URL.Query().Get("output")
	filePath := r.URL.Query().Get("path")
	raw := r.URL.Query().Get("raw") == "true"

	// Create a temporary tab for the download — avoids navigating the user's tab away.
	browserCtx := h.Bridge.BrowserContext()
	tabCtx, tabCancel := chromedp.NewContext(browserCtx)
	defer tabCancel()

	tCtx, tCancel := context.WithTimeout(tabCtx, 30*time.Second)
	defer tCancel()
	go web.CancelOnClientDone(r.Context(), tCancel)

	// Enable network tracking to capture response metadata.
	var requestID network.RequestID
	var responseMIME string
	var responseStatus int
	requestGuard := newDownloadRequestGuard(validator, h.Config.MaxRedirects)
	var mainFrameID cdp.FrameID
	done := make(chan struct{}, 1)

	// Intercept every browser-side request so redirects and follow-on navigations
	// cannot escape the public-only URL policy enforced for /download.
	if err := chromedp.Run(tCtx, chromedp.ActionFunc(func(ctx context.Context) error {
		return fetch.Enable().Do(ctx)
	})); err != nil {
		web.Error(w, 500, fmt.Errorf("fetch enable: %w", err))
		return
	}
	defer func() {
		_ = chromedp.Run(tCtx, chromedp.ActionFunc(func(ctx context.Context) error {
			return fetch.Disable().Do(ctx)
		}))
	}()

	chromedp.ListenTarget(tCtx, func(ev interface{}) {
		switch e := ev.(type) {
		case *fetch.EventRequestPaused:
			// Handle in goroutine to avoid deadlocking the event dispatcher.
			go func() {
				reqID := e.RequestID
				if err := requestGuard.Validate(e.Request.URL, e.RedirectedRequestID != ""); err != nil {
					requestGuard.NoteBlocked(err)
					select {
					case done <- struct{}{}:
					default:
					}
					_ = fetch.FailRequest(reqID, network.ErrorReasonBlockedByClient).Do(cdp.WithExecutor(tCtx, chromedp.FromContext(tCtx).Target))
					return
				}
				_ = fetch.ContinueRequest(reqID).Do(cdp.WithExecutor(tCtx, chromedp.FromContext(tCtx).Target))
			}()
		case *network.EventRequestWillBeSent:
			if e.Type != network.ResourceTypeDocument {
				return
			}
			if mainFrameID == "" {
				mainFrameID = e.FrameID
			}
			if e.FrameID == mainFrameID {
				requestID = e.RequestID
			}
		case *network.EventResponseReceived:
			if e.RequestID == requestID && requestID != "" {
				requestID = e.RequestID
				responseMIME = e.Response.MimeType
				responseStatus = int(e.Response.Status)
			}
		case *network.EventLoadingFinished:
			if e.RequestID == requestID && requestID != "" {
				select {
				case done <- struct{}{}:
				default:
				}
			}
		case *network.EventLoadingFailed:
			if e.RequestID == requestID && requestID != "" {
				select {
				case done <- struct{}{}:
				default:
				}
			}
		}
	})

	if err := chromedp.Run(tCtx, network.Enable()); err != nil {
		web.Error(w, 500, fmt.Errorf("network enable: %w", err))
		return
	}

	// Re-check scheme before navigation (validateDownloadURL already enforces this,
	// but inline check satisfies CodeQL SSRF analysis).
	if parsed, err := url.Parse(dlURL); err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") {
		web.Error(w, 400, fmt.Errorf("invalid download URL scheme"))
		return
	}

	// Navigate the temp tab to the URL — uses browser's cookie jar and stealth.
	if err := chromedp.Run(tCtx, chromedp.Navigate(dlURL)); err != nil {
		if blockedErr := requestGuard.BlockedError(); blockedErr != nil {
			if errors.Is(blockedErr, bridge.ErrTooManyRedirects) {
				web.Error(w, 422, fmt.Errorf("download: %w", blockedErr))
				return
			}
			web.Error(w, 400, blockedErr)
			return
		}
		web.Error(w, 502, fmt.Errorf("navigate to download URL: %w", err))
		return
	}

	// Wait for response.
	select {
	case <-done:
	case <-tCtx.Done():
		if blockedErr := requestGuard.BlockedError(); blockedErr != nil {
			if errors.Is(blockedErr, bridge.ErrTooManyRedirects) {
				web.Error(w, 422, fmt.Errorf("download: %w", blockedErr))
				return
			}
			web.Error(w, 400, blockedErr)
			return
		}
		web.Error(w, 504, fmt.Errorf("download timed out"))
		return
	}

	if blockedErr := requestGuard.BlockedError(); blockedErr != nil {
		if errors.Is(blockedErr, bridge.ErrTooManyRedirects) {
			web.Error(w, 422, fmt.Errorf("download: %w", blockedErr))
			return
		}
		web.Error(w, 400, blockedErr)
		return
	}

	if responseStatus >= 400 {
		web.Error(w, 502, fmt.Errorf("remote server returned HTTP %d", responseStatus))
		return
	}
	if requestID == "" {
		web.Error(w, 502, fmt.Errorf("download response was not captured"))
		return
	}

	// Get response body via CDP.
	var body []byte
	if err := chromedp.Run(tCtx,
		chromedp.ActionFunc(func(ctx context.Context) error {
			b, err := network.GetResponseBody(requestID).Do(ctx)
			if err != nil {
				return err
			}
			body = b
			return nil
		}),
	); err != nil {
		web.Error(w, 500, fmt.Errorf("get response body: %w", err))
		return
	}

	if responseMIME == "" {
		responseMIME = "application/octet-stream"
	}

	// Write to file.
	if output == "file" {
		if filePath == "" {
			web.Error(w, 400, fmt.Errorf("path required when output=file"))
			return
		}
		safe, pathErr := web.SafePath(h.Config.StateDir, filePath)
		if pathErr != nil {
			web.Error(w, 400, fmt.Errorf("invalid path: %w", pathErr))
			return
		}
		absBase, _ := filepath.Abs(h.Config.StateDir)
		absPath, pathErr := filepath.Abs(safe)
		if pathErr != nil || !strings.HasPrefix(absPath, absBase+string(filepath.Separator)) {
			web.Error(w, 400, fmt.Errorf("invalid output path"))
			return
		}
		filePath = absPath
		if err := os.MkdirAll(filepath.Dir(filePath), 0750); err != nil {
			web.Error(w, 500, fmt.Errorf("failed to create directory: %w", err))
			return
		}
		if err := os.WriteFile(filePath, body, 0600); err != nil {
			web.Error(w, 500, fmt.Errorf("failed to write file: %w", err))
			return
		}
		web.JSON(w, 200, map[string]any{
			"status":      "saved",
			"path":        filePath,
			"size":        len(body),
			"contentType": responseMIME,
		})
		return
	}

	// Raw bytes.
	if raw {
		w.Header().Set("Content-Type", responseMIME)
		w.Header().Set("Content-Length", fmt.Sprintf("%d", len(body)))
		w.WriteHeader(200)
		_, _ = w.Write(body)
		return
	}

	// Default: base64 JSON response.
	web.JSON(w, 200, map[string]any{
		"data":        base64.StdEncoding.EncodeToString(body),
		"contentType": responseMIME,
		"size":        len(body),
		"url":         dlURL,
	})
}

// HandleTabDownload fetches a URL using the browser session for a tab identified by path ID.
//
// @Endpoint GET /tabs/{id}/download
func (h *Handlers) HandleTabDownload(w http.ResponseWriter, r *http.Request) {
	tabID := r.PathValue("id")
	if tabID == "" {
		web.Error(w, 400, fmt.Errorf("tab id required"))
		return
	}
	if _, _, err := h.Bridge.TabContext(tabID); err != nil {
		web.Error(w, 404, err)
		return
	}

	q := r.URL.Query()
	q.Set("tabId", tabID)

	req := r.Clone(r.Context())
	u := *r.URL
	u.RawQuery = q.Encode()
	req.URL = &u

	h.HandleDownload(w, req)
}
