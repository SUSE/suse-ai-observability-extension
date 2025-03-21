package sync

import (
	"fmt"
	"github.com/ravan/stackstate-client/stackstate/api"
	"github.com/ravan/stackstate-client/stackstate/receiver"
	"genai-stackpack/internal/config"
	"time"

	"log/slog"
	"strings"
)

const (
	Source               = "openlit"
	Domain               = "Open Telemetry LLM"
	TelemetrySdkLanguage = "telemetry_sdk_language"
	GenAiRequestModel    = "gen_ai_request_model"
	ServiceName          = "service_name"
	ServiceInstanceId    = "service_instance_id"
	GenAiOperationName   = "gen_ai_operation_name"
	ServiceNamespace     = "service_namespace"
	GenAiEnvironment     = "gen_ai_environment"
	GenAiSystem          = "gen_ai_system"
	GenAiApplicationName = "gen_ai_application_name"
	DBSystem             = "db_system"
	DBOperation          = "db_operation"

	GenAiRequestsTotalPromQl = "sum_over_time(gen_ai_requests_total{}[%s])"
	DbRequestsTotalPromQl    = "sum_over_time(db_requests_total{}[%s])"

	CTypeGenAiApp = "genai.app"
)

var RequiredFields = []string{TelemetrySdkLanguage, ServiceName, ServiceInstanceId, ServiceNamespace, GenAiEnvironment,
	GenAiApplicationName}
var GenAiRequiredFields = []string{GenAiSystem, GenAiOperationName, GenAiRequestModel}
var DBRequiredFields = []string{DBSystem, DBOperation}

func Sync(conf *config.Configuration) (*receiver.Factory, error) {
	factory := receiver.NewFactory(Source, Source, conf.Kubernetes.Cluster)
	client := api.NewClient(&conf.StackState)
	err := genAIMetrics2Topology(conf, client, factory)
	if err != nil {
		return nil, err
	}

	err = dbMetrics2Topology(conf, client, factory)
	if err != nil {
		return nil, err
	}

	return factory, nil
}

func genAIMetrics2Topology(conf *config.Configuration, client *api.Client, factory *receiver.Factory) error {
	query := fmt.Sprintf(GenAiRequestsTotalPromQl, conf.Kubernetes.QueryTimeInterval)
	result, err := getMetricGroups(query, client)
	if err != nil {
		return err
	}

	if result != nil && len(*result) > 0 {
		for _, r := range *result {
			if err := validateRequiredFields(r.Labels, append(RequiredFields, GenAiRequiredFields...)); err != nil {
				slog.Error("failed to validate required fields", "error", err, "labels", r.Labels)
				continue
			}
			appComp := mapGenAiApp(r.Labels, factory)
			sysComp := mapGenAiSystem(appComp, r.Labels, factory)
			modelComp := mapGenAiModel(sysComp, r.Labels, factory)
			mapGenAiOperation(modelComp, r.Labels, factory)
		}
	}
	return nil
}

func dbMetrics2Topology(conf *config.Configuration, client *api.Client, factory *receiver.Factory) error {
	query := fmt.Sprintf(DbRequestsTotalPromQl, conf.Kubernetes.QueryTimeInterval)
	result, err := getMetricGroups(query, client)
	if err != nil {
		return err
	}

	if result != nil && len(*result) > 0 {
		for _, r := range *result {
			if err := validateRequiredFields(r.Labels, append(RequiredFields, DBRequiredFields...)); err != nil {
				slog.Error("failed to validate required fields", "error", err, "labels", r.Labels)
				continue
			}

			appComp := mapGenAiApp(r.Labels, factory)
			sysComp := mapVectorDbSystem(appComp, r.Labels, factory)
			mapVectorDbOperation(sysComp, r.Labels, factory)
		}
	}
	return nil
}

func getMetricGroups(query string, client *api.Client) (*[]api.MetricResult, error) {
	resp, err := client.QueryMetric(query, time.Now(), api.DefaultTimeout)
	if err != nil {
		return nil, err
	}
	if resp.Status != "success" {
		slog.Error("query failed", "status", resp.Status, "query", query, "error", resp.Errors)
		return nil, fmt.Errorf("query failed: %s", resp.Status)
	}

	if len(resp.Data.Result) == 0 {
		slog.Info("query returned no results", "query", query)
		return nil, nil
	}
	return &resp.Data.Result, nil
}

func validateRequiredFields(labels map[string]string, requiredFields []string) error {
	for _, field := range requiredFields {
		if _, ok := labels[field]; !ok {
			return fmt.Errorf("required field %s is missing", field)
		}
	}
	return nil
}

func toLabelKey(key string) string {
	return strings.ReplaceAll(key, "_", ".")
}

func UrnGenAiApp(name, namespace string) string {
	return fmt.Sprintf("urn:opentelemetry:namespace/%s:service/%s", namespace, name)
}

func UrnGenAiSystem(name string) string {
	return fmt.Sprintf("urn:openlit:genai:system/%s", name)
}

func UrnVectorDbSystem(name string) string {
	return fmt.Sprintf("urn:openlit:vectordb:system/%s", name)
}

func UrnGenAiModel(name string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:genai:%s:model/%s", genAiSystem, name)
}

func UrnGenAiOperation(name string, genAiModel string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:genai:%s:model:%s:operation/%s", genAiSystem, genAiModel, name)
}

func UrnVectorDbOperation(name string, genAiSystem string) string {
	return fmt.Sprintf("urn:openlit:vectordb:%s:operation/%s", genAiSystem, name)
}

func UrnServiceNamespace(namespace string) string {
	return fmt.Sprintf("urn:opentelemetry:namespace/%s", namespace)
}

func UrnCluster(cluster string) string {
	return fmt.Sprintf("urn:cluster:/kubernetes:%s", cluster)
}
