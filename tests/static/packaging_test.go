package static

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

func TestMasterTemplateIncludesResolve(t *testing.T) {
	masterPath := filepath.Join(testutil.TemplatesDir(), "suse-ai.sty")
	content, err := os.ReadFile(masterPath)
	require.NoError(t, err, "failed to read master template")

	includes := parser.ExtractIncludes(string(content))
	require.NotEmpty(t, includes, "master template should have includes")

	provisioningDir := testutil.ProvisioningDir()

	for _, inc := range includes {
		resolvedPath := filepath.Join(provisioningDir, inc.Path)
		info, err := os.Stat(resolvedPath)
		if err != nil {
			t.Errorf("include path does not resolve: %s", inc.Path)
			continue
		}
		if info.IsDir() {
			t.Errorf("include should point to a file, not directory: %s", inc.Path)
		}
	}
}

func TestAllIncludesResolveRecursively(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	err := filepath.Walk(provisioningDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}

		content, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("failed to read %s: %v", path, err)
			return nil
		}

		includes := parser.ExtractIncludes(string(content))
		for _, inc := range includes {
			resolvedPath := filepath.Join(provisioningDir, inc.Path)
			info, err := os.Stat(resolvedPath)
			if err != nil {
				t.Errorf("include in %s does not resolve: %s", path, inc.Path)
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

func TestNoCircularIncludes(t *testing.T) {
	provisioningDir := testutil.ProvisioningDir()

	graph := make(map[string][]string)
	err := filepath.Walk(provisioningDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		includes := parser.ExtractIncludes(string(content))
		var includedFiles []string
		for _, inc := range includes {
			if filepath.Ext(inc.Path) == ".sty" {
				resolvedPath := filepath.Join(provisioningDir, inc.Path)
				includedFiles = append(includedFiles, resolvedPath)
			}
		}
		graph[path] = includedFiles
		return nil
	})
	require.NoError(t, err, "failed to build include graph")

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

	for node := range graph {
		if !visited[node] {
			if hasCycle(node) {
				t.Fatal("circular includes detected")
			}
		}
	}
}
