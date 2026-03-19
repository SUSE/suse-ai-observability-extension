package otel

// GenAIAppFixture returns resource attributes for a GenAI application
func GenAIAppFixture(serviceName, componentType string) map[string]string {
	return map[string]string{
		"service.name":      serviceName,
		"component.type":    componentType,
		"genai.system.name": "openai",
		"deployment.name":   "production",
		"k8s.namespace.name": "ai-services",
	}
}

// ProductFixture returns resource attributes for a product component
func ProductFixture(serviceName, componentType, componentName string) map[string]string {
	return map[string]string{
		"service.name":      serviceName,
		"component.type":    componentType,
		"component.name":    componentName,
		"deployment.name":   "production",
		"k8s.namespace.name": "ai-services",
	}
}
