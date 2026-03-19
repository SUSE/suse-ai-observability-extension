package static

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"suse-ai-extension-tests/internal/parser"
	"suse-ai-extension-tests/internal/snapshot"
	"suse-ai-extension-tests/internal/testutil"
)

func TestSnapshotComponentTypes(t *testing.T) {
	nodes := loadAllNodes(t)
	componentTypes := nodesByType(nodes, "ComponentType")
	sort.Slice(componentTypes, func(i, j int) bool {
		return componentTypes[i].Name < componentTypes[j].Name
	})
	var b strings.Builder
	b.WriteString("# Component Types\n")
	b.WriteString(fmt.Sprintf("# Total: %d\n", len(componentTypes)))
	b.WriteString("#\n")
	b.WriteString("# name | identifier | has_icon\n")
	b.WriteString("#\n")
	for _, ct := range componentTypes {
		_, hasIcon := ct.Raw["iconbase64"]
		b.WriteString(fmt.Sprintf("%s | %s | %v\n", ct.Name, ct.Identifier, hasIcon))
	}
	snapshot.AssertMatchesGolden(t, "component_types.golden", b.String())
}

func TestSnapshotMetricBindings(t *testing.T) {
	nodes := loadAllNodes(t)
	bindings := nodesByType(nodes, "MetricBinding")
	sort.Slice(bindings, func(i, j int) bool {
		return bindings[i].ID < bindings[j].ID
	})
	var b strings.Builder
	b.WriteString("# Metric Bindings\n")
	b.WriteString(fmt.Sprintf("# Total: %d\n", len(bindings)))
	b.WriteString("#\n")
	b.WriteString("# id | name | identifier | scope\n")
	b.WriteString("#\n")
	for _, mb := range bindings {
		scope := mb.Scope
		if scope == "" {
			scope = "(none)"
		}
		b.WriteString(fmt.Sprintf("%d | %s | %s | %s\n", mb.ID, mb.Name, mb.Identifier, scope))
	}
	snapshot.AssertMatchesGolden(t, "metric_bindings.golden", b.String())
}

func TestSnapshotMonitors(t *testing.T) {
	nodes := loadAllNodes(t)
	monitors := nodesByType(nodes, "Monitor")
	sort.Slice(monitors, func(i, j int) bool {
		return monitors[i].ID < monitors[j].ID
	})
	var b strings.Builder
	b.WriteString("# Monitors\n")
	b.WriteString(fmt.Sprintf("# Total: %d\n", len(monitors)))
	b.WriteString("#\n")
	b.WriteString("# id | name | identifier\n")
	b.WriteString("#\n")
	for _, m := range monitors {
		b.WriteString(fmt.Sprintf("%d | %s | %s\n", m.ID, m.Name, m.Identifier))
	}
	snapshot.AssertMatchesGolden(t, "monitors.golden", b.String())
}

func TestSnapshotViews(t *testing.T) {
	nodes := loadAllNodes(t)
	var b strings.Builder

	viewTypes := nodesByType(nodes, "ViewType")
	sort.Slice(viewTypes, func(i, j int) bool {
		return viewTypes[i].ID < viewTypes[j].ID
	})
	b.WriteString("# View Types\n")
	b.WriteString(fmt.Sprintf("# Total: %d\n", len(viewTypes)))
	b.WriteString("#\n")
	b.WriteString("# id | name | identifier\n")
	b.WriteString("#\n")
	for _, vt := range viewTypes {
		b.WriteString(fmt.Sprintf("%d | %s | %s\n", vt.ID, vt.Name, vt.Identifier))
	}
	b.WriteString("\n")

	queryViews := nodesByType(nodes, "QueryView")
	sort.Slice(queryViews, func(i, j int) bool {
		return queryViews[i].ID < queryViews[j].ID
	})
	b.WriteString("# Query Views\n")
	b.WriteString(fmt.Sprintf("# Total: %d\n", len(queryViews)))
	b.WriteString("#\n")
	b.WriteString("# id | name | identifier\n")
	b.WriteString("#\n")
	for _, qv := range queryViews {
		b.WriteString(fmt.Sprintf("%d | %s | %s\n", qv.ID, qv.Name, qv.Identifier))
	}
	snapshot.AssertMatchesGolden(t, "views.golden", b.String())
}

func TestSnapshotIncludeGraph(t *testing.T) {
	masterPath := filepath.Join(testutil.TemplatesDir(), "suse-ai.sty")
	content, err := os.ReadFile(masterPath)
	if err != nil {
		t.Fatalf("Failed to read master template: %v", err)
	}
	includes := parser.ExtractIncludes(string(content))
	sort.Slice(includes, func(i, j int) bool {
		return includes[i].Path < includes[j].Path
	})
	var b strings.Builder
	b.WriteString("# Include Graph (from suse-ai.sty)\n")
	b.WriteString(fmt.Sprintf("# Total includes: %d\n", len(includes)))
	b.WriteString("#\n")
	b.WriteString("# path | format\n")
	b.WriteString("#\n")
	for _, inc := range includes {
		format := inc.Format
		if format == "" {
			format = "(default)"
		}
		b.WriteString(fmt.Sprintf("%s | %s\n", inc.Path, format))
	}
	snapshot.AssertMatchesGolden(t, "include_graph.golden", b.String())
}

func TestSnapshotGroovyProducts(t *testing.T) {
	scripts := []struct {
		name string
		file string
	}{
		{"id-extractor", "suse-ai-id-extractor.groovy"},
		{"product-id-extractor", "suse-ai-product-id-extractor.groovy"},
		{"component-mapping", "component-mapping-function.groovy"},
	}
	var b strings.Builder
	b.WriteString("# Groovy Script Switch Cases\n")
	b.WriteString("#\n")
	for _, s := range scripts {
		script, err := parser.LoadGroovyScript(
			filepath.Join(testutil.TemplatesDir(), "sync", s.file),
		)
		if err != nil {
			t.Fatalf("Failed to load %s: %v", s.file, err)
		}
		cases := script.ExtractSwitchCases()
		sort.Strings(cases)
		b.WriteString(fmt.Sprintf("# %s (%s)\n", s.name, s.file))
		b.WriteString(fmt.Sprintf("# Cases: %d\n", len(cases)))
		for _, c := range cases {
			b.WriteString(fmt.Sprintf("  %s\n", c))
		}
		b.WriteString("\n")
	}
	snapshot.AssertMatchesGolden(t, "groovy_products.golden", b.String())
}
