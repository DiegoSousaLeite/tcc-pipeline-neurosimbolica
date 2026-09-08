package util

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	logUtil "github.com/lin-snow/ech0/internal/util/log"
	"go.uber.org/zap"
)

// TrimURL 去除 URL 前后的空格和斜杠
func TrimURL(url string) string {
	if url == "" {
		return ""
	}

	// 去除连接地址前后的空格和斜杠
	url = strings.TrimSpace(url)
	url = strings.TrimPrefix(url, "/")
	url = strings.TrimSuffix(url, "/")
	return url
}

// ExtractDomain 从 URL 中提取域名
func ExtractDomain(url string) string {
	// 去除协议部分
	if strings.HasPrefix(url, "http://") {
		url = strings.TrimPrefix(url, "http://")
	} else if strings.HasPrefix(url, "https://") {
		url = strings.TrimPrefix(url, "https://")
	}

	// 提取域名部分 (到第一个斜杠为止)
	slashIndex := strings.Index(url, "/")
	if slashIndex != -1 {
		url = url[:slashIndex]
	}

	return url
}

// Header 自定义请求头结构体
type Header struct {
	Header  string
	Content string
}

const (
	defaultSafeResponseBodyLimitBytes int64 = 1 << 20 // 1 MiB
	maxSafeRedirects                        = 3
)

var blockedCIDRs = mustParseCIDRs(
	[]string{
		"0.0.0.0/8",
		"10.0.0.0/8",
		"100.64.0.0/10",
		"127.0.0.0/8",
		"169.254.0.0/16",
		"172.16.0.0/12",
		"192.168.0.0/16",
		"198.18.0.0/15",
		"224.0.0.0/4",
		"240.0.0.0/4",
		"::/128",
		"::1/128",
		"fe80::/10",
		"fc00::/7",
		"ff00::/8",
	},
)

func mustParseCIDRs(cidrs []string) []*net.IPNet {
	result := make([]*net.IPNet, 0, len(cidrs))
	for _, cidr := range cidrs {
		_, ipNet, err := net.ParseCIDR(cidr)
		if err != nil {
			panic(fmt.Sprintf("invalid cidr %s: %v", cidr, err))
		}
		result = append(result, ipNet)
	}
	return result
}

func isPrivateOrReservedIP(ip net.IP) bool {
	if ip == nil {
		return true
	}
	for _, ipNet := range blockedCIDRs {
		if ipNet.Contains(ip) {
			return true
		}
	}
	return false
}

func isBlockedHostname(hostname string) bool {
	hostname = strings.ToLower(strings.TrimSpace(hostname))
	return hostname == "localhost" ||
		strings.HasSuffix(hostname, ".localhost") ||
		hostname == "host.docker.internal" ||
		hostname == "gateway.docker.internal"
}

// ValidatePublicHTTPURL 校验 URL 是否可安全用于外部请求
func ValidatePublicHTTPURL(rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("URL 格式无效: %w", err)
	}
	if parsed.Scheme == "" || parsed.Host == "" {
		return errors.New("URL 必须包含协议和主机")
	}
	scheme := strings.ToLower(parsed.Scheme)
	if scheme != "http" && scheme != "https" {
		return errors.New("仅支持 http/https 协议")
	}
	if parsed.User != nil {
		return errors.New("URL 不允许包含用户信息")
	}

	hostname := parsed.Hostname()
	if hostname == "" {
		return errors.New("URL 主机无效")
	}
	if isBlockedHostname(hostname) {
		return errors.New("目标主机不被允许")
	}
	if ip := net.ParseIP(hostname); ip != nil && isPrivateOrReservedIP(ip) {
		return errors.New("目标 IP 不被允许")
	}
	return nil
}

func secureDialContext(timeout time.Duration) func(context.Context, string, string) (net.Conn, error) {
	dialer := &net.Dialer{Timeout: timeout}
	return func(ctx context.Context, network, address string) (net.Conn, error) {
		conn, err := dialer.DialContext(ctx, network, address)
		if err != nil {
			return nil, err
		}
		tcpAddr, ok := conn.RemoteAddr().(*net.TCPAddr)
		if !ok || tcpAddr == nil || isPrivateOrReservedIP(tcpAddr.IP) {
			_ = conn.Close()
			return nil, errors.New("连接目标地址不被允许")
		}
		return conn, nil
	}
}

func readBodyWithLimit(reader io.Reader, maxBytes int64) ([]byte, error) {
	body, err := io.ReadAll(io.LimitReader(reader, maxBytes+1))
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}
	if int64(len(body)) > maxBytes {
		return nil, fmt.Errorf("响应体超过限制: %d bytes", maxBytes)
	}
	return body, nil
}

// SendRequest 发送 HTTP 请求
func SendRequest(
	url, method string,
	customHeader Header,
	timeout ...time.Duration,
) ([]byte, error) {
	// 默认超时时间，如果有传入参数则使用传入的
	clientTimeout := 2 * time.Second
	if len(timeout) > 0 {
		clientTimeout = timeout[0]
	}

	// 自定义 HTTP 客户端
	client := &http.Client{
		Timeout: clientTimeout,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				MinVersion: tls.VersionTLS12,
			},
		},
	}

	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}

	// 添加自定义请求头
	if customHeader.Header != "" && customHeader.Content != "" {
		req.Header.Set(customHeader.Header, customHeader.Content)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求发送失败: %w", err)
	}
	defer func() {
		if closeErr := resp.Body.Close(); closeErr != nil {
			logUtil.Warn(
				"close response body failed",
				zap.String("module", "http_util"),
				zap.Error(closeErr),
			)
		}
	}()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	return body, nil
}

// SendSafeRequest 发送带 SSRF 防护的 HTTP 请求
func SendSafeRequest(
	url, method string,
	customHeader Header,
	timeout ...time.Duration,
) ([]byte, error) {
	if err := ValidatePublicHTTPURL(url); err != nil {
		return nil, err
	}

	clientTimeout := 2 * time.Second
	if len(timeout) > 0 {
		clientTimeout = timeout[0]
	}

	client := &http.Client{
		Timeout: clientTimeout,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				MinVersion: tls.VersionTLS12,
			},
			DialContext: secureDialContext(clientTimeout),
		},
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= maxSafeRedirects {
				return errors.New("重定向次数过多")
			}
			return ValidatePublicHTTPURL(req.URL.String())
		},
	}

	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}
	if customHeader.Header != "" && customHeader.Content != "" {
		req.Header.Set(customHeader.Header, customHeader.Content)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求发送失败: %w", err)
	}
	defer func() {
		if closeErr := resp.Body.Close(); closeErr != nil {
			logUtil.Warn(
				"close response body failed",
				zap.String("module", "http_util"),
				zap.Error(closeErr),
			)
		}
	}()

	return readBodyWithLimit(resp.Body, defaultSafeResponseBodyLimitBytes)
}

// GetMIMETypeFromFilenameOrURL 根据文件名或 URL 获取 MIME 类型
func GetMIMETypeFromFilenameOrURL(filenameOrURL string) string {
	lowerFilename := strings.ToLower(filenameOrURL)
	switch {
	case strings.HasSuffix(lowerFilename, ".jpg"), strings.HasSuffix(lowerFilename, ".jpeg"):
		return "image/jpeg"
	case strings.HasSuffix(lowerFilename, ".png"):
		return "image/png"
	case strings.HasSuffix(lowerFilename, ".gif"):
		return "image/gif"
	case strings.HasSuffix(lowerFilename, ".bmp"):
		return "image/bmp"
	case strings.HasSuffix(lowerFilename, ".webp"):
		return "image/webp"
	case strings.HasSuffix(lowerFilename, ".mp4"):
		return "video/mp4"
	case strings.HasSuffix(lowerFilename, ".mov"):
		return "video/quicktime"
	case strings.HasSuffix(lowerFilename, ".mp3"):
		return "audio/mpeg"
	case strings.HasSuffix(lowerFilename, ".wav"):
		return "audio/wav"
	case strings.HasSuffix(lowerFilename, ".ogg"):
		return "audio/ogg"
	case strings.HasSuffix(lowerFilename, ".pdf"):
		return "application/pdf"
	case strings.HasSuffix(lowerFilename, ".doc"):
		return "application/msword"
	case strings.HasSuffix(lowerFilename, ".docx"):
		return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
	case strings.HasSuffix(lowerFilename, ".xls"):
		return "application/vnd.ms-excel"
	case strings.HasSuffix(lowerFilename, ".xlsx"):
		return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	case strings.HasSuffix(lowerFilename, ".ppt"):
		return "application/vnd.ms-powerpoint"
	case strings.HasSuffix(lowerFilename, ".pptx"):
		return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
	case strings.HasSuffix(lowerFilename, ".txt"):
		return "text/plain"
	case strings.HasSuffix(lowerFilename, ".html"), strings.HasSuffix(lowerFilename, ".htm"):
		return "text/html"
	case strings.HasSuffix(lowerFilename, ".csv"):
		return "text/csv"
	default:
		return "application/octet-stream" // 默认二进制流
	}
}
