package watcher

import (
	"errors"
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"time"
)

type qdrant struct {
	promQL  string
	c       *api.Client
	builder *receiver.Factory
	semanticConventions
}

func NewQdrantWatcher(c *api.Client, builder *receiver.Factory) *qdrant {
	q := new(qdrant)
	q.promQL = "collections_total"
	q.c = c
	q.builder = builder
	sc := NewSemanticConventions()
	q.semanticConventions = sc
	return q
}

func (q qdrant) PerformComponentIdentification() (err error) {
	metrics, err := q.checkMetrics()
	if err != nil {
		return
	}
	if metrics == nil {
		return
	}
	for _, metric := range *metrics {
		_ = q.inferComponents(metric)
		// TODO: retrieve and log error
	}
	return
}

func (q qdrant) inferComponents(metric api.MetricResult) (err error) {
	err = q.validateMetricLabels(metric.Labels)
	if err != nil {
		return
	}

	_ = q.qdrantComponent(metric.Labels)

	return
}

func (q qdrant) validateMetricLabels(labels map[string]string) (err error) {
	if _, ok := labels[q.semanticConventions.ServiceNamespace]; !ok {
		err = errors.New("Missing required fields")
	}

	return
}

func (q qdrant) qdrantComponent(labels map[string]string) (c *receiver.Component) {
	namespace := labels[q.ServiceNamespace]
	name := "qdrant"
	id := q.semanticConventions.UrnVectorDbSystem(name)
	if q.builder.ComponentExists(id) {
		c = q.builder.MustGetComponent(id)
	} else {
		c = q.builder.MustNewComponent(id, name, q.semanticConventions.DBSystemForGenAI(name))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = q.semanticConventions.Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(q.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("identifier", id)
	}
	return
}

func (q qdrant) checkMetrics() (*[]api.MetricResult, error) {
	response, err := q.c.QueryMetric(q.promQL, time.Now(), "10s")
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
