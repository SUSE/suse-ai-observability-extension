package static

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

// TestMasterTemplateIncludesResolve verifies that all includes in suse-ai.sty resolve to actual files.
func TestMasterTemplateIncludesResolve(t *testing.T) {
	masterPath := filepath.Join(testutil.TemplatesDir(), "suse-ai.sty")
	content, err := os.ReadFile(masterPath)
	require.NoError(t, err, "failed to read master template")

	includes := parser.ExtractIncludes(string(content))
	require.NotEmpty(t, includes, "master template should have includes")

	provisioningDir := testutil.ProvisioningDir()

	for _, inc := range includes {
		// Resolve path relative to provisioning directory
		resolvedPath := filepath.Join(provisioningDir, inc.Path)

		info, err := os.Stat(resolvedPath)
		assert.NoError(t, err, "include path should resolve: %s", inc.Path)
		if err == nil {
			assert.False(t, info.IsDir(), "include should point to a file, not directory: %s", inc.Path)
		}
	}
}

// TestAllIncludesResolveRecursively walks all .sty files and verifies all includes resolve.
func TestAllIncludesResolveRecursively(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	err := filepath.Walk(provisioningDir, func(path string, info os.FileInfo, err error) error {
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

		// Read file
		content, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("failed to read %s: %v", path, err)
			return nil
		}

		// Extract includes
		includes := parser.ExtractIncludes(string(content))

		// Verify each include resolves
		for _, inc := range includes {
			resolvedPath := filepath.Join(provisioningDir, inc.Path)

			info, err := os.Stat(resolvedPath)
			if err != nil {
				t.Errorf("include in %s does not resolve: %s (error: %v)", path, inc.Path, err)
				continue
			}

			if info.IsDir() {
				t.Errorf("include in %s points to directory, not file: %s", path, inc.Path)
			}
		}

		return nil
	})

	require.NoError(t, err, "failed to walk directory")
}

// TestNoCircularIncludes builds an include graph and detects cycles using DFS.
func TestNoCircularIncludes(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	// Build include graph: map[file][]includedFiles
	graph := make(map[string][]string)

	err := filepath.Walk(provisioningDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() || filepath.Ext(path) != ".sty" {
			return nil
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		includes := parser.ExtractIncludes(string(content))

		var includedFiles []string
		for _, inc := range includes {
			// Only track .sty includes (not .groovy)
			if filepath.Ext(inc.Path) == ".sty" {
				resolvedPath := filepath.Join(provisioningDir, inc.Path)
				includedFiles = append(includedFiles, resolvedPath)
			}
		}

		graph[path] = includedFiles
		return nil
	})

	require.NoError(t, err, "failed to build include graph")

	// DFS cycle detection
	visited := make(map[string]bool)
	recStack := make(map[string]bool)

	var hasCycle func(node string) bool
	hasCycle = func(node string) bool {
		visited[node] = true
		recStack[node] = true

		for _, neighbor := range graph[node] {
			if !visited[neighbor] {
				if hasCycle(neighbor) {
					return true
				}
			} else if recStack[neighbor] {
				t.Errorf("circular include detected: %s -> %s", node, neighbor)
				return true
			}
		}

		recStack[node] = false
		return false
	}

	// Check all nodes
	for node := range graph {
		if !visited[node] {
			if hasCycle(node) {
				t.Fatal("circular includes detected")
			}
		}
	}
}

// TestNoOrphanedTemplates verifies all .sty files are reachable from suse-ai.sty.
func TestNoOrphanedTemplates(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()
	masterPath := filepath.Join(testutil.TemplatesDir(), "suse-ai.sty")

	// Build reachable set using BFS from master template
	reachable := make(map[string]bool)
	queue := []string{masterPath}
	reachable[masterPath] = true

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		content, err := os.ReadFile(current)
		if err != nil {
			t.Errorf("failed to read %s: %v", current, err)
			continue
		}

		includes := parser.ExtractIncludes(string(content))
		for _, inc := range includes {
			// Only track .sty includes
			if filepath.Ext(inc.Path) != ".sty" {
				continue
			}

			resolvedPath := filepath.Join(provisioningDir, inc.Path)

			if !reachable[resolvedPath] {
				reachable[resolvedPath] = true
				queue = append(queue, resolvedPath)
			}
		}
	}

	// Walk directory and find all .sty files
	var allStyFiles []string
	err := filepath.Walk(provisioningDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() && filepath.Ext(path) == ".sty" {
			allStyFiles = append(allStyFiles, path)
		}

		return nil
	})

	require.NoError(t, err, "failed to walk directory")

	// Check for orphaned files
	for _, styFile := range allStyFiles {
		if !reachable[styFile] {
			t.Errorf("orphaned template (not reachable from suse-ai.sty): %s", styFile)
		}
	}
}

// TestGroovyScriptsExist verifies required Groovy scripts exist.
func TestGroovyScriptsExist(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	requiredScripts := []string{
		"SuseAiProvision.groovy",
		"templates/sync/suse-ai-id-extractor.groovy",
		"templates/sync/suse-ai-product-id-extractor.groovy",
		"templates/sync/component-mapping-function.groovy",
	}

	for _, script := range requiredScripts {
		scriptPath := filepath.Join(provisioningDir, script)
		info, err := os.Stat(scriptPath)

		assert.NoError(t, err, "Groovy script should exist: %s", script)
		if err == nil {
			assert.False(t, info.IsDir(), "path should be a file: %s", script)
		}
	}
}

// TestHandlebarsTemplatesExist verifies required Handlebars templates exist.
func TestHandlebarsTemplatesExist(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	requiredTemplates := []string{
		"templates/sync/component-template.json.handlebars",
		"templates/sync/relation-template.json.handlebars",
	}

	for _, template := range requiredTemplates {
		templatePath := filepath.Join(provisioningDir, template)
		info, err := os.Stat(templatePath)

		assert.NoError(t, err, "Handlebars template should exist: %s", template)
		if err == nil {
			assert.False(t, info.IsDir(), "path should be a file: %s", template)
		}
	}
}
