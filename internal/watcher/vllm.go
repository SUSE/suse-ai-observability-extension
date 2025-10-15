package watcher

import (
	"errors"
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"time"
)

type vllm struct {
	promQL  string
	c       *api.Client
	builder *receiver.Factory
	semanticConventions
}

func NewVLLMWatcher(c *api.Client, builder *receiver.Factory) *vllm {
	v := new(vllm)
	v.promQL = "vllm_prompt_tokens_total"
	v.c = c
	v.builder = builder
	sc := NewSemanticConventions()
	v.semanticConventions = sc
	return v
}

func (v vllm) PerformComponentIdentification() (err error) {
	metrics, err := v.checkMetrics()
	if err != nil {
		return
	}
	if metrics == nil {
		return
	}
	for _, metric := range *metrics {
		_ = v.inferComponents(metric)
		// TODO: retrieve and log error
	}
	return
}

func (v vllm) inferComponents(metric api.MetricResult) (err error) {
	err = v.validateMetricLabels(metric.Labels)
	if err != nil {
		return
	}

	base := v.baseComponent(metric.Labels)

	core := v.vllmComponent(metric.Labels)

	if !v.builder.RelationExists(base.ID, core.ID) {
		v.builder.MustNewRelation(base.ID, core.ID, "is")
	}

	model := v.modelComponent(metric.Labels)

	if !v.builder.RelationExists(core.ID, model.ID) {
		v.builder.MustNewRelation(core.ID, model.ID, "runs")
	}

	return
}

func (v vllm) validateMetricLabels(labels map[string]string) (err error) {
	if _, ok := labels[v.semanticConventions.ServiceName]; !ok {
		err = errors.New("Missing required fields")
	}
	if _, ok := labels[v.semanticConventions.ServiceNamespace]; !ok {
		err = errors.New("Missing required fields")
	}

	if _, ok := labels[v.semanticConventions.ServiceNamespace]; !ok {
		err = errors.New("Missing required fields")
	}

	return
}

func (v vllm) baseComponent(labels map[string]string) (c *receiver.Component) {
	name, namespace := labels[v.ServiceName], labels[v.ServiceNamespace]
	id := v.UrnGenAiApp(name, namespace)
	if v.builder.ComponentExists(id) {
		c = v.builder.MustGetComponent(id)
	} else {
		c = v.builder.MustNewComponent(id, name, v.CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = "OpenTelemetry"
		c.AddLabel("gen_ai_system")
		c.AddLabelKey(toLabelKey(v.ServiceName), name)
		c.AddLabelKey(toLabelKey(v.ServiceNamespace), namespace)
		c.AddProperty("namespaceIdentifier", v.UrnServiceNamespace(namespace))
		c.AddProperty("clusterIdentifier", v.UrnCluster(v.builder.Cluster))
	}
	return
}

func (v vllm) vllmComponent(labels map[string]string) (c *receiver.Component) {
	name, namespace := labels[v.ServiceName], labels[v.ServiceNamespace]
	id := v.semanticConventions.UrnGenAiSystem(name)
	if v.builder.ComponentExists(id) {
		c = v.builder.MustGetComponent(id)
	} else {
		c = v.builder.MustNewComponent(id, name, "genai.system.vllm")
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = v.semanticConventions.Domain
		c.AddLabel("gen_ai_system")
		c.AddLabelKey(toLabelKey(v.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("identifier", id)
	}
	return
}

func (v vllm) modelComponent(labels map[string]string) (c *receiver.Component) {
	id := v.UrnGenAiModel(labels[v.VLLMRequestModel], labels[v.ServiceName])
	if v.builder.ComponentExists(id) {
		c = v.builder.MustGetComponent(id)
	} else {
		c = v.builder.MustNewComponent(id, labels[v.VLLMRequestModel], "genai.model")
		c.Data.Layer = "GenAiModels"
		c.Data.Domain = v.Domain
		c.AddLabelKey(toLabelKey(v.GenAiApplicationName), labels[v.ServiceName])
		c.AddLabelKey(toLabelKey(v.ServiceNamespace), labels[v.ServiceNamespace])
		c.AddProperty("identifier", id)
	}
	c.AddLabel("vllm_metrics_available")
	return
}

func (v vllm) checkMetrics() (*[]api.MetricResult, error) {
	response, err := v.c.QueryMetric(v.promQL, time.Now(), "10s")
	if err != nil {
		return nil, err
	}
	if response.Status != "success" {
		return nil, errors.New("Query Failed")
	}

	if len(response.Data.Result) == 0 {
		return nil, nil
	}
	return &response.Data.Result, nil
}
