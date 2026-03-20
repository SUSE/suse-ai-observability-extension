package static

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/testutil"
)

func TestMonitorRemediationHintsExist(t *testing.T) {
	monitorsDir := filepath.Join(testutil.TemplatesDir(), "monitors")

	var styFiles []string
	err := filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}
		styFiles = append(styFiles, path)
		return nil
	})
	require.NoError(t, err)
	require.NotEmpty(t, styFiles, "Should find at least one .sty file in monitors directory")

	for _, styFile := range styFiles {
		content, err := os.ReadFile(styFile)
		require.NoError(t, err, "Failed to read %s", styFile)

		includes := parser.ExtractIncludes(string(content))
		for _, include := range includes {
			if !strings.HasSuffix(include.Path, ".md.hbs") {
				continue
			}
			includePath := filepath.Join(testutil.ProvisioningDir(), include.Path)
			_, err := os.Stat(includePath)
			assert.NoError(t, err,
				"Monitor file %s references remediation hint %s which should exist at %s",
				styFile, include.Path, includePath)
		}
	}
}

func TestAllRemediationHintFilesAreReferenced(t *testing.T) {
	monitorsDir := filepath.Join(testutil.TemplatesDir(), "monitors")

	var hbsFiles []string
	err := filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(path, ".md.hbs") {
			return err
		}
		hbsFiles = append(hbsFiles, path)
		return nil
	})
	require.NoError(t, err)
	require.NotEmpty(t, hbsFiles, "Should find at least one .md.hbs file in monitors directory")

	referencedPaths := make(map[string]bool)
	err = filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || filepath.Ext(path) != ".sty" {
			return err
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		for _, include := range parser.ExtractIncludes(string(content)) {
			if strings.HasSuffix(include.Path, ".md.hbs") {
				referencedPaths[filepath.Join(testutil.ProvisioningDir(), include.Path)] = true
			}
		}
		return nil
	})
	require.NoError(t, err)

	var unreferenced []string
	for _, hbsFile := range hbsFiles {
		if !referencedPaths[hbsFile] {
			relPath, err := filepath.Rel(testutil.ProvisioningDir(), hbsFile)
			if err != nil {
				relPath = hbsFile
			}
			unreferenced = append(unreferenced, relPath)
		}
	}
	assert.Empty(t, unreferenced,
		"Found unreferenced remediation hint files:\n%s",
		strings.Join(unreferenced, "\n"))
}
