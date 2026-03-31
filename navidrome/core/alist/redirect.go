package alist

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/navidrome/navidrome/log"
	"github.com/navidrome/navidrome/model"
)

// TryRedirect intercepts a playback request for a .strm file and orchestrates the redirection.
func (c *Client) TryRedirect(w http.ResponseWriter, r *http.Request, mf *model.MediaFile) (bool, error) {
	if !strings.EqualFold(mf.Suffix, "strm") {
		return false, nil
	}

	ctx := r.Context()
	log.Warn(ctx, "[STRM-REDIRECT-V4] Intercepted playback request", "id", mf.ID, "path", mf.Path)

	// 1. Read
	raw, err := c.ReadSTRMFile(mf)
	if err != nil {
		log.Error(ctx, "AList-V4: Error reading .strm content", "id", mf.ID, err)
		return false, err
	}

	// 2. Classify
	typ, normalized := ClassifySTRMTarget(raw, c.URL)
	log.Debug(ctx, "AList-V4: Classified STRM target", "id", mf.ID, "type", typ.String(), "normalized", normalized)

	finalURL := ""
	finalDuration := float64(mf.Duration)

	// 3. Resolve based on type
	switch typ {
	case InternalPath:
		info, err := c.GetDirectLink(normalized, r.UserAgent())
		if err != nil {
			log.Error(ctx, "STRM-V4: Internal path resolution failed", "id", mf.ID, "raw", normalized, err)
			return false, err
		}
		finalURL = info.URL
		if info.Duration > 0 {
			finalDuration = info.Duration
		}

	case AlistDownloadURL:
		log.Debug(ctx, "STRM-V4: Resolving Alist download URL (tracking redirects)", "id", mf.ID, "url", normalized)
		lastURL, err := c.ResolveLastURL(normalized, r.UserAgent())
		if err != nil {
			log.Warn(ctx, "STRM-V4: ResolveLastURL failed, fallback to original", "id", mf.ID, "err", err)
			finalURL = normalized
		} else {
			finalURL = lastURL
		}

	case RemoteDirectURL:
		finalURL = normalized

	default:
		log.Error(ctx, "STRM-V4: Unsupported strm format", "id", mf.ID, "raw", raw)
		return false, fmt.Errorf("unsupported strm format")
	}

	finalURL = normalizeURL(finalURL)

	// 4. Output
	log.Warn(ctx, "[STRM-REDIRECT-V4] Redirecting client to direct link", "id", mf.ID, "target", finalURL, "duration", finalDuration)
	c.Write302(w, finalURL, finalDuration)
	return true, nil
}

// ReadSTRMFile reads and cleans the content of a .strm file.
func (c *Client) ReadSTRMFile(mf *model.MediaFile) (string, error) {
	filePath := mf.AbsolutePath()
	contentBytes, err := os.ReadFile(filePath)
	if err != nil {
		return "", err
	}
	raw := strings.TrimSpace(string(contentBytes))
	if raw == "" {
		return "", fmt.Errorf("empty strm content")
	}
	return raw, nil
}

// Write302 standardizes the HTTP 302 response for redirections.
func (c *Client) Write302(w http.ResponseWriter, finalURL string, duration float64) {
	if duration > 0 {
		w.Header().Set("X-Content-Duration", strconv.FormatFloat(duration, 'G', -1, 32))
	}
	w.Header().Set("Location", finalURL)
	w.Header().Set("X-ND-Redirect", "AList-V4")
	w.WriteHeader(http.StatusFound)
}
