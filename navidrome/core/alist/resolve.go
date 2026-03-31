package alist

import (
	"net/url"
	"strings"
)

type TargetType int

const (
	Unknown TargetType = iota
	InternalPath
	AlistDownloadURL
	RemoteDirectURL
)

// ClassifySTRMTarget categorizes the .strm content into one of the supported types.
func ClassifySTRMTarget(raw, alistBaseURL string) (TargetType, string) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return Unknown, ""
	}

	// 1. Internal path starts with /
	if strings.HasPrefix(s, "/") {
		return InternalPath, s
	}

	// 2. Normalize and check if it's a valid URL
	normalized := normalizeURL(s)
	u, err := url.Parse(normalized)
	if err != nil {
		return Unknown, s
	}

	// 3. Check if it belongs to current Alist instance
	if alistBaseURL != "" && sameHost(u, alistBaseURL) {
		if strings.HasPrefix(u.Path, "/d/") {
			return AlistDownloadURL, normalized
		}
		// If it's on the same host but not /d/, treat as remote but on same server
		return RemoteDirectURL, normalized
	}

	// 4. Other http/https links are remote direct URLs
	if u.Scheme == "http" || u.Scheme == "https" {
		return RemoteDirectURL, normalized
	}

	return Unknown, s
}

// sameHost checks if the target URL has the same host as the Alist base URL.
func sameHost(u *url.URL, alistBaseURL string) bool {
	base, err := url.Parse(normalizeURL(alistBaseURL))
	if err != nil {
		return false
	}
	return strings.EqualFold(base.Host, u.Host)
}

// normalizeURL ensures the URL has a scheme (http/https).
func normalizeURL(u string) string {
	if u == "" {
		return u
	}
	if strings.Contains(u, "://") {
		return u
	}
	return "http://" + u
}

// resolveRelativeURL handles absolute/relative redirect targets.
func resolveRelativeURL(baseStr, loc string) (string, error) {
	base, err := url.Parse(baseStr)
	if err != nil {
		return "", err
	}
	ref, err := url.Parse(loc)
	if err != nil {
		return "", err
	}
	return base.ResolveReference(ref).String(), nil
}

func (t TargetType) String() string {
	switch t {
	case InternalPath:
		return "InternalPath"
	case AlistDownloadURL:
		return "AlistDownloadURL"
	case RemoteDirectURL:
		return "RemoteDirectURL"
	default:
		return "Unknown"
	}
}
