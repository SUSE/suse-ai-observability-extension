package parser

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

// GroovyScript holds the content and extracted patterns from a Groovy script.
type GroovyScript struct {
	Path    string
	Content string
}

// LoadGroovyScript reads a Groovy file.
func LoadGroovyScript(path string) (*GroovyScript, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return &GroovyScript{
		Path:    path,
		Content: string(content),
	}, nil
}

// ContainsPattern checks if the script matches a regex pattern.
func (g *GroovyScript) ContainsPattern(pattern string) bool {
	re, err := regexp.Compile(pattern)
	if err != nil {
		return false
	}
	return re.MatchString(g.Content)
}

// ExtractStringLiterals returns all double-quoted string literals.
func (g *GroovyScript) ExtractStringLiterals() []string {
	re := regexp.MustCompile(`"([^"]*)"`)
	matches := re.FindAllStringSubmatch(g.Content, -1)

	var literals []string
	for _, match := range matches {
		if len(match) > 1 {
			literals = append(literals, match[1])
		}
	}
	return literals
}

// ExtractSwitchCases returns all `case 'value'` string values from switch statements.
func (g *GroovyScript) ExtractSwitchCases() []string {
	re := regexp.MustCompile(`(?m)^\s*case\s+'([^']+)'`)
	matches := re.FindAllStringSubmatch(g.Content, -1)

	var cases []string
	for _, match := range matches {
		if len(match) > 1 {
			cases = append(cases, match[1])
		}
	}
	return cases
}

// FindMissingToString returns lines where externalId is used in assignments without .toString().
func (g *GroovyScript) FindMissingToString() []string {
	lines := strings.Split(g.Content, "\n")
	var results []string

	for i, line := range lines {
		// Skip comments
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "/*") || strings.HasPrefix(trimmed, "*") {
			continue
		}

		// Skip lines that are just reading externalId from a map (intermediate assignments)
		if regexp.MustCompile(`^\s*def\s+\w+\s*=\s*\w+\["externalId"\]`).MatchString(line) {
			continue
		}

		// Check for externalId usage without .toString() in string concatenation or Sts.createId
		if strings.Contains(line, "externalId") && !strings.Contains(line, ".toString()") {
			// Look for problematic patterns: string concatenation or function calls with externalId
			if regexp.MustCompile(`['"].*\+.*externalId|externalId.*\+.*['"]`).MatchString(line) {
				results = append(results, fmt.Sprintf("%d: %s", i+1, line))
			} else if regexp.MustCompile(`Sts\.createId\([^)]*externalId[^)]*\)`).MatchString(line) {
				// Check if externalId is passed directly to Sts.createId without .toString()
				results = append(results, fmt.Sprintf("%d: %s", i+1, line))
			}
		}
	}

	return results
}
