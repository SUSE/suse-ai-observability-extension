package snapshot

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// snapshotsDir returns the absolute path to testdata/snapshots/.
func snapshotsDir() string {
	_, filename, _, _ := runtime.Caller(0)
	// snapshot.go is at tests/internal/snapshot/snapshot.go
	testsRoot := filepath.Join(filepath.Dir(filename), "..", "..")
	return filepath.Join(testsRoot, "testdata", "snapshots")
}

// AssertMatchesGolden compares content against a golden file.
// If the golden file doesn't exist, the test fails with instructions to create it.
// If it exists but doesn't match, the test fails showing the diff.
func AssertMatchesGolden(t *testing.T, goldenName string, actual string) {
	t.Helper()

	goldenPath := filepath.Join(snapshotsDir(), goldenName)

	// Normalize line endings
	actual = strings.ReplaceAll(actual, "\r\n", "\n")
	actual = strings.TrimRight(actual, "\n") + "\n"

	expected, err := os.ReadFile(goldenPath)
	if err != nil {
		if os.IsNotExist(err) {
			t.Fatalf("Golden file %s does not exist.\n\nCreate it with the following content:\n\n%s\n\nFile path: %s",
				goldenName, actual, goldenPath)
		}
		t.Fatalf("Failed to read golden file %s: %v", goldenName, err)
	}

	expectedStr := strings.ReplaceAll(string(expected), "\r\n", "\n")
	expectedStr = strings.TrimRight(expectedStr, "\n") + "\n"

	if actual != expectedStr {
		actualLines := strings.Split(actual, "\n")
		expectedLines := strings.Split(expectedStr, "\n")

		var diff strings.Builder
		diff.WriteString(fmt.Sprintf("Golden file %s does not match.\n\n", goldenName))
		diff.WriteString(fmt.Sprintf("Expected %d lines, got %d lines.\n\n", len(expectedLines), len(actualLines)))

		shown := 0
		maxLines := len(actualLines)
		if len(expectedLines) > maxLines {
			maxLines = len(expectedLines)
		}
		for i := 0; i < maxLines && shown < 20; i++ {
			exp := ""
			act := ""
			if i < len(expectedLines) {
				exp = expectedLines[i]
			}
			if i < len(actualLines) {
				act = actualLines[i]
			}
			if exp != act {
				diff.WriteString(fmt.Sprintf("Line %d:\n  expected: %s\n  actual:   %s\n", i+1, exp, act))
				shown++
			}
		}
		if shown >= 20 {
			diff.WriteString("... (truncated)\n")
		}

		diff.WriteString(fmt.Sprintf("\nTo update, replace the contents of:\n  %s\n\nWith:\n\n%s", goldenPath, actual))
		t.Fatal(diff.String())
	}
}
