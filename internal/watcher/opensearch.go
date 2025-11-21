package watcher

import (
	"errors"
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"time"
)

type opensearch struct {
	promQL  string
	c       *api.Client
	builder *receiver.Factory
	semanticConventions
}

func NewOpenSearchWatcher(c *api.Client, builder *receiver.Factory) *opensearch {
	o := new(opensearch)
	o.promQL = "elasticsearch_cluster_nodes{elasticsearch_cluster_name=\"opensearch-cluster\"}"
	o.c = c
	o.builder = builder
	sc := NewSemanticConventions()
	o.semanticConventions = sc
	return o
}

func (o opensearch) PerformComponentIdentification() (err error) {
	metrics, err := o.checkMetrics()
	if err != nil {
		return
	}
	if metrics == nil {
		return
	}
	for _, metric := range *metrics {
		_ = o.inferComponents(metric)
		// TODO: retrieve and log error
	}
	return
}

func (o opensearch) inferComponents(metric api.MetricResult) (err error) {
	err = o.validateMetricLabels(metric.Labels)
	if err != nil {
		return
	}

	_ = o.opensearchComponent(metric.Labels)

	return
}

func (o opensearch) validateMetricLabels(labels map[string]string) (err error) {
	if _, ok := labels[o.semanticConventions.ElasticClusterName]; !ok {
		err = errors.New("Missing required fields")
	}
	if _, ok := labels[o.semanticConventions.ServiceNamespace]; !ok {
		err = errors.New("Missing required fields")
	}

	return
}

func (o opensearch) opensearchComponent(labels map[string]string) (c *receiver.Component) {
	namespace := labels[o.ServiceNamespace]
	name := "opensearch"
	id := o.semanticConventions.UrnVectorDbSystem(name)
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, name, o.semanticConventions.DBSystemForGenAI(name))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = o.semanticConventions.Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(o.semanticConventions.ServiceNamespace), namespace)
		c.AddProperty("identifier", id)
	}
	return
}

func (o opensearch) checkMetrics() (*[]api.MetricResult, error) {
	response, err := o.c.QueryMetric(o.promQL, time.Now(), "10s")
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
