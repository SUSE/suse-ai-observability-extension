package parser

import "testing"

func FuzzExtractIncludes(f *testing.F) {
	f.Add(`{{ include "templates/shared.sty" "yaml" }}`)
	f.Add(`{{ include "path.groovy" }}`)
	f.Add(`{{ get "urn:stackpack:common:monitor-function:threshold" }}`)
	f.Add(`nodes:\n{{ include "a.sty" "yaml" }}\n{{ include "b.sty" "yaml" }}`)
	f.Add(`no directives here`)
	f.Add(``)
	f.Add(`{{ }}`)
	f.Add(`{{ include }}`)
	f.Add(`{{ include "" "" }}`)
	f.Add(`{{{ nested }}}`)

	f.Fuzz(func(t *testing.T, input string) {
		result := ExtractIncludes(input)
		_ = len(result)
		for _, inc := range result {
			_ = inc.Path
			_ = inc.Format
		}
	})
}

func FuzzParseSTYNodes(f *testing.F) {
	f.Add(`- _type: ComponentType
  name: "test"
  identifier: "urn:test"`)
	f.Add(`- _type: Monitor
  id: -3000
  name: Test
  function: {{ get "urn:stackpack:common:monitor-function:threshold" }}`)
	f.Add(`nodes:
  - _type: Layer
    id: -2
    name: Models`)
	f.Add(``)
	f.Add(`not yaml at all {{{{ }}}`)
	f.Add(`- _type: ""
  id: 0`)
	f.Add(`just a string`)
	f.Add(`{{ include "x" "y" }}`)

	f.Fuzz(func(t *testing.T, input string) {
		nodes, _ := ParseSTYNodes(input)
		for _, n := range nodes {
			_ = n.Type
			_ = n.ID
			_ = n.Identifier
			_ = n.Name
		}
	})
}

func FuzzNormalizeIndentation(f *testing.F) {
	f.Add("  line1\n  line2\n")
	f.Add("\t\tindented\n\t\talso")
	f.Add("")
	f.Add("no indent")
	f.Add("  \n  \n  ")
	f.Add("\n\n\n")
	f.Add("  a\nb\n  c")

	f.Fuzz(func(t *testing.T, input string) {
		result := normalizeIndentation(input)
		_ = len(result)
	})
}

func FuzzFindMissingToString(f *testing.F) {
	f.Add(`def extIdStr = externalId.toString()`)
	f.Add(`def id = elementMap["externalId"]`)
	f.Add(`// comment with externalId`)
	f.Add(`newExternalId = 'suse-ai:' + extIdStr`)
	f.Add(`Sts.createId(externalId, ids, type)`)
	f.Add(``)
	f.Add(`no groovy here`)
	f.Add(`def x = topologyElement.externalId?.toString()`)

	f.Fuzz(func(t *testing.T, input string) {
		g := &GroovyScript{Content: input}
		results := g.FindMissingToString()
		_ = len(results)
	})
}

func FuzzExtractSwitchCases(f *testing.F) {
	f.Add(`case 'vllm':`)
	f.Add(`    case 'ollama':
        case 'milvus':`)
	f.Add(`switch(x) { }`)
	f.Add(`no cases`)
	f.Add(`case "double-quoted":`)
	f.Add(``)

	f.Fuzz(func(t *testing.T, input string) {
		g := &GroovyScript{Content: input}
		cases := g.ExtractSwitchCases()
		_ = len(cases)
	})
}
