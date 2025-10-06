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
	v.promQL = "vllm_healthy_pods_total"
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
		// TODO: infer level2 components (aka models). I may need to change the promQL or do a second operation for this
		// TODO: retrieve and log error
	}
	return
}

func (v vllm) inferComponents(metric api.MetricResult) (err error) {
	serviceName, serviceNamespace, err := v.validateMetricFields(metric)
	if err != nil {
		return
	}

	base := v.baseComponent(serviceName, serviceNamespace)

	core := v.vllmComponent(serviceName, serviceNamespace)

	if !v.builder.RelationExists(base.ID, core.ID) {
		v.builder.MustNewRelation(base.ID, core.ID, "is")
	}
	return
}

func (v vllm) validateMetricFields(metric api.MetricResult) (serviceName, serviceNamespace string, err error) {
	if val, ok := metric.Labels[v.semanticConventions.ServiceName]; ok {
		serviceName = val
	}
	if val, ok := metric.Labels[v.semanticConventions.ServiceNamespace]; ok {
		serviceNamespace = val
	}

	if serviceName == "" && serviceNamespace == "" {
		err = errors.New("Required information not available")
	}

	return
}

func (v vllm) baseComponent(name, namespace string) (c *receiver.Component) {
	id := v.UrnGenAiApp(name, namespace)
	if v.builder.ComponentExists(id) {
		c = v.builder.MustGetComponent(id)
	} else {
		c = v.builder.MustNewComponent(id, name, v.semanticConventions.CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = "OpenTelemetry"
		c.AddLabel("gen_ai_system")
		c.AddLabelKey(toLabelKey(v.semanticConventions.ServiceName), name)
		c.AddLabelKey(toLabelKey(v.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("namespaceIdentifier", v.UrnServiceNamespace(namespace))
		c.AddProperty("clusterIdentifier", v.UrnCluster(v.builder.Cluster))
	}
	return
}

func (v vllm) vllmComponent(name, namespace string) (c *receiver.Component) {
	id := v.semanticConventions.UrnVectorDbSystem(name)
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
