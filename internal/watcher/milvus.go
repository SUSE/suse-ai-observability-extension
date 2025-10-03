package watcher

import (
	"errors"
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"time"
)

type milvus struct{
	promQL string
	c *api.Client
	builder *receiver.Factory
	semanticConventions
}

func NewMilvusWatcher(c *api.Client, builder *receiver.Factory) (*milvus) {
	m := new(milvus)
	m.promQL = "milvus_runtime_info"
	m.c = c
	m.builder = builder
	sc := NewSemanticConventions()
	m.semanticConventions = sc
	return m
}

func (m milvus) PerformComponentIdentification() (err error) {
	metrics, err := m.checkMetrics()
	for _, metric := range(*metrics) {
		_ = m.inferComponents(metric)
		// TODO: retrieve and log error
	}
	return
}

func (m milvus) inferComponents(metric api.MetricResult) (err error) {
	serviceName, serviceNamespace, err := m.validateMetricFields(metric)
	if err != nil {
		return
	}

	base := m.baseComponent(serviceName, serviceNamespace)

	core := m.milvusComponent(serviceName, serviceNamespace)

	if !m.builder.RelationExists(base.ID, core.ID) {
		m.builder.MustNewRelation(base.ID, core.ID, "is")
	}
	return
}

func (m milvus) validateMetricFields(metric api.MetricResult) (serviceName, serviceNamespace string, err error) {
	if val, ok := metric.Labels[m.semanticConventions.ServiceName]; ok {
		serviceName = val
	}
	if val, ok := metric.Labels[m.semanticConventions.ServiceNamespace]; ok {
		serviceNamespace = val
	}

	if serviceName == "" && serviceNamespace == "" {
		err = errors.New("Required information not available")
	}

	return
}

func (m milvus) baseComponent(name, namespace string) (c *receiver.Component) {
	id := m.UrnGenAiApp(name, namespace)
	if m.builder.ComponentExists(id) {
		c = m.builder.MustGetComponent(id)
	} else {
		c = m.builder.MustNewComponent(id, name, m.semanticConventions.CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = "OpenTelemetry"
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(m.semanticConventions.ServiceName), name)
		c.AddLabelKey(toLabelKey(m.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("namespaceIdentifier", m.UrnServiceNamespace(namespace))
		c.AddProperty("clusterIdentifier", m.UrnCluster(m.builder.Cluster))
	}
	return
}

func (m milvus) milvusComponent(name, namespace string) (c *receiver.Component){
	id := m.semanticConventions.UrnVectorDbSystem(name)
	if m.builder.ComponentExists(id) {
		c = m.builder.MustGetComponent(id)
	} else {
		c = m.builder.MustNewComponent(id, name, m.semanticConventions.DBSystemForGenAI(name))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = m.semanticConventions.Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(m.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("identifier", id)
	}
	return
}

func (m milvus) checkMetrics() (*[]api.MetricResult, error) {
	response, err := m.c.QueryMetric(m.promQL, time.Now(), "10s")
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
