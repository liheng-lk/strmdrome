package alist

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/navidrome/navidrome/conf"
	"github.com/navidrome/navidrome/log"
)

type Client struct {
	URL     string
	Token   string
	client  *http.Client
	tracker *http.Client // Reused client for tracking redirects
}

func New() *Client {
	url := strings.TrimSuffix(conf.Server.Alist.URL, "/")
	if url != "" {
		log.Warn("AList: Initializing resolver", "url", url)
	} else {
		log.Warn("AList: Resolver initialized with NO URL. Redirection will only work for direct HTTP links.")
	}
	return &Client{
		URL:   url,
		Token: conf.Server.Alist.Token,
		client: &http.Client{
			Timeout: 15 * time.Second,
		},
		tracker: &http.Client{
			Timeout: 10 * time.Second, // Shorter timeout for individual probes
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				// Don't follow automatically, we want to follow manually and log each step
				return http.ErrUseLastResponse
			},
		},
	}
}

type LinkInfo struct {
	URL      string
	Size     int64
	Duration float64 // Seconds
}

type alistResponse struct {
	Code int    `json:"code"`
	Msg  string `json:"message"`
	Data struct {
		RawURL   string            `json:"raw_url"`
		Size     int64             `json:"size"`
		Metadata map[string]string `json:"metadata"`
	} `json:"data"`
}

// GetDirectLink fetches direct link information from Alist API.
func (c *Client) GetDirectLink(path string, ua string) (*LinkInfo, error) {
	if c.URL == "" {
		return nil, fmt.Errorf("AList URL is not configured (ND_ALIST_URL)")
	}

	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}

	log.Debug("AList: Resolving path", "path", path)

	payload := map[string]interface{}{
		"path":     path,
		"password": "",
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", c.URL+"/api/fs/get", bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	if ua != "" {
		req.Header.Set("User-Agent", ua)
	}
	if c.Token != "" {
		req.Header.Set("Authorization", c.Token)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("AList HTTP error: %s, body=%s", resp.Status, strings.TrimSpace(string(raw)))
	}

	var result alistResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	if result.Code != 200 {
		return nil, fmt.Errorf("AList error (%d): %s", result.Code, result.Msg)
	}

	if result.Data.RawURL == "" {
		return nil, fmt.Errorf("AList returned empty raw_url for %s", path)
	}

	info := &LinkInfo{
		URL:  result.Data.RawURL,
		Size: result.Data.Size,
	}

	if durStr, ok := result.Data.Metadata["duration"]; ok {
		var d float64
		if _, err := fmt.Sscanf(durStr, "%f", &d); err == nil {
			info.Duration = d
		}
	}

	log.Debug("AList: Successfully resolved path", "path", path, "url", info.URL, "duration", info.Duration)
	return info, nil
}

// ResolveLastURL follows redirects to find the ultimate direct link.
// It reuses the tracker client to avoid leaking sockets/connections.
func (c *Client) ResolveLastURL(raw string, ua string) (string, error) {
	current := normalizeURL(strings.TrimSpace(raw))
	if current == "" {
		return "", fmt.Errorf("empty url")
	}

	for i := 0; i < 10; i++ {
		req, err := http.NewRequest("GET", current, nil)
		if err != nil {
			return "", err
		}
		if ua != "" {
			req.Header.Set("User-Agent", ua)
		}
		// Lightweight probe using Range header
		req.Header.Set("Range", "bytes=0-0")

		resp, err := c.tracker.Do(req)
		if err != nil {
			return "", err
		}
		resp.Body.Close()

		if resp.StatusCode >= 300 && resp.StatusCode < 400 {
			loc := resp.Header.Get("Location")
			if loc == "" {
				return current, nil
			}
			next, err := resolveRelativeURL(current, loc)
			if err != nil {
				return "", err
			}
			log.Debug("AList: Follow redirect", "from", current, "to", next, "status", resp.StatusCode, "hop", i+1)
			current = next
			continue
		}

		// Found final URL
		return current, nil
	}

	log.Warn("AList: Redirect recursion limit reached (10 hops)", "url", current)
	return current, nil
}
