package parser

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"gopkg.in/yaml.v3"
)

// IncludeDirective represents a Handlebars-style include directive.
type IncludeDirective struct {
	Path   string
	Format string
}

// STYNode represents a parsed node from an STY file.
type STYNode struct {
	Type       string                 // _type field
	ID         int                    // id field (optional)
	Identifier string                 // identifier field (optional)
	Name       string                 // name field (optional)
	Scope      string                 // scope field (optional, for MetricBindings)
	SourceFile string                 // path to the source .sty file
	Raw        map[string]interface{} // raw YAML data
}

// normalizeIndentation removes common leading whitespace from all lines.
func normalizeIndentation(content string) string {
	lines := strings.Split(content, "\n")

	// Find minimum indentation (ignoring empty lines)
	minIndent := -1
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		indent := len(line) - len(strings.TrimLeft(line, " \t"))
		if minIndent == -1 || indent < minIndent {
			minIndent = indent
		}
	}

	// Remove common indentation (if any)
	if minIndent > 0 {
		var result []string
		for _, line := range lines {
			if strings.TrimSpace(line) == "" {
				result = append(result, "")
			} else if len(line) >= minIndent {
				result = append(result, line[minIndent:])
			} else {
				result = append(result, line)
			}
		}
		return strings.Join(result, "\n")
	}

	return content
}

// ExtractIncludes extracts all {{ include "path" "format" }} directives from content.
func ExtractIncludes(content string) []IncludeDirective {
	var includes []IncludeDirective

	// Match {{ include "path" "format" }} or {{ include "path" }}
	// Using non-greedy .*? is critical because directives can contain } in quoted strings
	re := regexp.MustCompile(`\{\{\s*include\s+"([^"]+)"(?:\s+"([^"]+)")?\s*\}\}`)
	matches := re.FindAllStringSubmatch(content, -1)

	for _, match := range matches {
		path := match[1]
		format := ""
		if len(match) > 2 {
			format = match[2]
		}
		includes = append(includes, IncludeDirective{
			Path:   path,
			Format: format,
		})
	}

	return includes
}

// ParseSTYNodes parses STY content and returns all nodes.
// It strips {{ }} directives, removes "nodes:" prefix, and parses the remaining YAML.
func ParseSTYNodes(content string) ([]STYNode, error) {
	// Strip all {{ }} directives using non-greedy matching
	// This is critical because directives can contain } in quoted strings
	// like {{ get "urn:stackpack:common:monitor-function:threshold" }}
	directiveRe := regexp.MustCompile(`\{\{.*?\}\}`)
	cleaned := directiveRe.ReplaceAllString(content, "")

	// Strip "nodes:" prefix if present (preserving indentation)
	lines := strings.Split(cleaned, "\n")
	if len(lines) > 0 && strings.Contains(lines[0], "nodes:") {
		lines = lines[1:]
		cleaned = strings.Join(lines, "\n")
	}

	// Normalize indentation by removing common leading whitespace
	cleaned = normalizeIndentation(cleaned)

	// Parse YAML
	var rawNodes []map[string]interface{}
	if err := yaml.Unmarshal([]byte(cleaned), &rawNodes); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Convert to STYNode structs
	var nodes []STYNode
	for _, raw := range rawNodes {
		node := STYNode{
			Raw: raw,
		}

		// Extract _type
		if t, ok := raw["_type"].(string); ok {
			node.Type = t
		}

		// Extract id (can be negative int)
		if id, ok := raw["id"].(int); ok {
			node.ID = id
		}

		// Extract identifier
		if identifier, ok := raw["identifier"].(string); ok {
			node.Identifier = identifier
		}

		// Extract name
		if name, ok := raw["name"].(string); ok {
			node.Name = name
		}

		// Extract scope
		if scope, ok := raw["scope"].(string); ok {
			node.Scope = scope
		}

		nodes = append(nodes, node)
	}

	return nodes, nil
}

// LoadAllSTYNodes walks the directory, parses all .sty files, and returns all nodes.
// It skips suse-ai.sty (the master file) and silently skips files that fail YAML parsing.
func LoadAllSTYNodes(dir string) ([]STYNode, error) {
	var allNodes []STYNode

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Skip directories
		if info.IsDir() {
			return nil
		}

		// Only process .sty files
		if filepath.Ext(path) != ".sty" {
			return nil
		}

		// Skip the master file
		if filepath.Base(path) == "suse-ai.sty" {
			return nil
		}

		// Read file
		content, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed to read %s: %w", path, err)
		}

		// Parse nodes (silently skip files that fail)
		nodes, err := ParseSTYNodes(string(content))
		if err != nil {
			// Silently skip files that fail YAML parsing
			// (some files are primarily include containers)
			return nil
		}

		// Set SourceFile for each node
		for i := range nodes {
			nodes[i].SourceFile = path
		}

		allNodes = append(allNodes, nodes...)
		return nil
	})

	if err != nil {
		return nil, err
	}

	return allNodes, nil
}
