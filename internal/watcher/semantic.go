package watcher

import (
	"fmt"
	"strings"
)

type semanticConventions struct{
	Source               string
	Domain               string
	TelemetrySdkLanguage string
	GenAiRequestModel    string
	ServiceName          string
	ServiceInstanceId    string
	GenAiOperationName   string
	ServiceNamespace     string
	GenAiEnvironment     string
	GenAiSystem          string
	GenAiApplicationName string
	DBSystem             string
	DBOperation          string
	VLLMQuery string
	CTypeGenAiApp string
	CTypeOTELService string
}

func NewSemanticConventions() semanticConventions {
	return semanticConventions{
		Source               : "openlit",
		Domain               : "Open Telemetry LLM",
		TelemetrySdkLanguage : "telemetry_sdk_language",
		GenAiRequestModel    : "gen_ai_request_model",
		ServiceName          : "service_name",
		ServiceInstanceId    : "service_instance_id",
		GenAiOperationName   : "gen_ai_operation_name",
		ServiceNamespace     : "service_namespace",
		GenAiEnvironment     : "gen_ai_environment",
		GenAiSystem          : "gen_ai_system",
		GenAiApplicationName : "gen_ai_application_name",
		DBSystem             : "db_system",
		DBOperation          : "db_operation",
		VLLMQuery : "vllm_healthy_pods_total",
		CTypeGenAiApp : "genai.app",
		CTypeOTELService : "otel service",
	}
}

func (s semanticConventions) UrnGenAiApp(name, namespace string) string {
	return fmt.Sprintf("urn:opentelemetry:namespace/%s:service/%s", namespace, name)
}

func (s semanticConventions) UrnGenAiSystem(name string) string {
	return fmt.Sprintf("urn:openlit:genai:system/%s", name)
}

func (s semanticConventions) UrnVectorDbSystem(name string) string {
	return fmt.Sprintf("urn:openlit:vectordb:system/%s", name)
}

func (s semanticConventions) UrnGenAiModel(name string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:genai:%s:model/%s", genAiSystem, name)
}

func (s semanticConventions) UrnGenAiOperation(name string, genAiModel string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:genai:%s:model:%s:operation/%s", genAiSystem, genAiModel, name)
}

func (s semanticConventions) UrnVectorDbOperation(name string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:vectordb:%s:operation/%s", genAiSystem, name)
}

func (s semanticConventions) UrnServiceNamespace(namespace string) string {
	return fmt.Sprintf("urn:opentelemetry:namespace/%s", namespace)
}

func (s semanticConventions) UrnCluster(cluster string) string {
	return fmt.Sprintf("urn:cluster:/kubernetes:%s", cluster)
}

func (s semanticConventions) DBSystemForGenAI(sys string) string {
	return fmt.Sprintf("genai.dbsystem.%s", strings.ToLower(sys))
}


func toLabelKey(key string) string {
	return strings.ReplaceAll(key, "_", ".")
}
