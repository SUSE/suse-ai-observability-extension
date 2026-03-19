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

func TestMonitorsHaveRequiredFields(t *testing.T) {
	nodes := loadAllNodes(t)
	monitors := nodesByType(nodes, "Monitor")
	require.NotEmpty(t, monitors, "Should find at least one Monitor")

	for _, monitor := range monitors {
		// Check name
		assert.NotEmpty(t, monitor.Name,
			"Monitor (identifier: %s, file: %s) should have a name",
			monitor.Identifier, monitor.SourceFile)

		// Check identifier
		assert.NotEmpty(t, monitor.Identifier,
			"Monitor %q (file: %s) should have an identifier",
			monitor.Name, monitor.SourceFile)

		// Check ID is non-zero
		assert.NotZero(t, monitor.ID,
			"Monitor %q (identifier: %s, file: %s) should have a non-zero ID",
			monitor.Name, monitor.Identifier, monitor.SourceFile)

		// Check arguments field exists in Raw
		arguments, hasArguments := monitor.Raw["arguments"]
		assert.True(t, hasArguments,
			"Monitor %q (identifier: %s, file: %s) should have arguments field",
			monitor.Name, monitor.Identifier, monitor.SourceFile)

		if hasArguments {
			assert.NotNil(t, arguments,
				"Monitor %q (identifier: %s, file: %s) arguments field should not be nil",
				monitor.Name, monitor.Identifier, monitor.SourceFile)
		}
	}
}

func TestMonitorIDsAreInExpectedRange(t *testing.T) {
	nodes := loadAllNodes(t)
	monitors := nodesByType(nodes, "Monitor")
	require.NotEmpty(t, monitors, "Should find at least one Monitor")

	for _, monitor := range monitors {
		assert.LessOrEqual(t, monitor.ID, -3000,
			"Monitor %q (identifier: %s, file: %s) ID should be <= -3000, got %d",
			monitor.Name, monitor.Identifier, monitor.SourceFile, monitor.ID)
	}
}

func TestMonitorIdentifiersFollowPattern(t *testing.T) {
	nodes := loadAllNodes(t)
	monitors := nodesByType(nodes, "Monitor")
	require.NotEmpty(t, monitors, "Should find at least one Monitor")

	expectedPrefix := "urn:stackpack:suse-ai:shared:monitor:"

	for _, monitor := range monitors {
		assert.True(t,
			strings.HasPrefix(monitor.Identifier, expectedPrefix),
			"Monitor %q (file: %s) identifier %q should start with %q",
			monitor.Name, monitor.SourceFile, monitor.Identifier, expectedPrefix)
	}
}

func TestMonitorRemediationHintsExist(t *testing.T) {
	monitorsDir := filepath.Join(testutil.TemplatesDir(), "monitors")

	// Walk all .sty files under templates/monitors/
	var styFiles []string
	err := filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && filepath.Ext(path) == ".sty" {
			styFiles = append(styFiles, path)
		}
		return nil
	})
	require.NoError(t, err)
	require.NotEmpty(t, styFiles, "Should find at least one .sty file in monitors directory")

	// For each .sty file, extract includes and verify referenced files exist
	for _, styFile := range styFiles {
		content, err := os.ReadFile(styFile)
		require.NoError(t, err, "Failed to read %s", styFile)

		includes := parser.ExtractIncludes(string(content))

		for _, include := range includes {
			// Only check .md.hbs files (remediation hints)
			if !strings.HasSuffix(include.Path, ".md.hbs") {
				continue
			}

			// Resolve the absolute path
			// The include path is relative to the provisioning directory
			includePath := filepath.Join(testutil.ProvisioningDir(), include.Path)

			// Check if the file exists
			_, err := os.Stat(includePath)
			assert.NoError(t, err,
				"Monitor file %s references remediation hint %s which should exist at %s",
				styFile, include.Path, includePath)
		}
	}
}

func TestAllRemediationHintFilesAreReferenced(t *testing.T) {
	monitorsDir := filepath.Join(testutil.TemplatesDir(), "monitors")

	// Collect all .md.hbs files
	var hbsFiles []string
	err := filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && strings.HasSuffix(path, ".md.hbs") {
			hbsFiles = append(hbsFiles, path)
		}
		return nil
	})
	require.NoError(t, err)
	require.NotEmpty(t, hbsFiles, "Should find at least one .md.hbs file in monitors directory")

	// Collect all includes from all .sty files
	referencedPaths := make(map[string]bool)
	err = filepath.Walk(monitorsDir, func(path string, info os.FileInfo, err error) error {
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
		for _, include := range includes {
			if strings.HasSuffix(include.Path, ".md.hbs") {
				// Store the absolute path for comparison
				includePath := filepath.Join(testutil.ProvisioningDir(), include.Path)
				referencedPaths[includePath] = true
			}
		}
		return nil
	})
	require.NoError(t, err)

	// Verify each .md.hbs file is referenced
	var unreferenced []string
	for _, hbsFile := range hbsFiles {
		if !referencedPaths[hbsFile] {
			// Get a relative path for better error messages
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
