package parser

import (
	"fmt"
	"strings"

	"github.com/gurkankaymak/hocon"
)

// StackPackConf represents the parsed stackpack.conf file.
type StackPackConf struct {
	Name                string
	Version             string
	DisplayName         string
	Categories          []string
	Provision           string
	OverviewURL         string
	DetailedOverviewURL string
	ReleaseNotes        string
	LogoURL             string
	ConfigurationURLs   map[string]string // state -> url
	Dependencies        map[string]string // name -> version
}

// trimQuotes removes surrounding quotes from a string.
func trimQuotes(s string) string {
	return strings.Trim(s, `"`)
}

// ParseStackPackConf parses a HOCON stackpack.conf file.
func ParseStackPackConf(path string) (*StackPackConf, error) {
	cfg, err := hocon.ParseResource(path)
	if err != nil {
		return nil, fmt.Errorf("failed to parse HOCON file: %w", err)
	}

	conf := &StackPackConf{
		ConfigurationURLs: make(map[string]string),
		Dependencies:      make(map[string]string),
	}

	// Parse simple string fields
	conf.Name = trimQuotes(cfg.GetString("name"))
	conf.Version = trimQuotes(cfg.GetString("version"))
	conf.DisplayName = trimQuotes(cfg.GetString("displayName"))
	conf.Provision = trimQuotes(cfg.GetString("provision"))
	conf.OverviewURL = trimQuotes(cfg.GetString("overviewUrl"))
	conf.DetailedOverviewURL = trimQuotes(cfg.GetString("detailedOverviewUrl"))
	conf.ReleaseNotes = trimQuotes(cfg.GetString("releaseNotes"))
	conf.LogoURL = trimQuotes(cfg.GetString("logoUrl"))

	// Parse categories array
	conf.Categories = cfg.GetStringSlice("categories")

	// Parse configurationUrls object
	if configUrls := cfg.GetStringMapString("configurationUrls"); configUrls != nil {
		for k, v := range configUrls {
			conf.ConfigurationURLs[k] = trimQuotes(v)
		}
	}

	// Parse dependencies object
	if deps := cfg.GetStringMapString("dependencies"); deps != nil {
		for k, v := range deps {
			conf.Dependencies[k] = trimQuotes(v)
		}
	}

	return conf, nil
}
