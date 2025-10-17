package watcher

import (
	"errors"
	"fmt"
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"strings"
	"time"
)

type openLIT struct {
	requiredFieldsGenAI []string
	requiredFieldsVDB   []string
	genAIPromQL         string
	vdbPromQL           string
	c                   *api.Client
	builder             *receiver.Factory
	semanticConventions
}

func NewOpenLITWatcher(c *api.Client, builder *receiver.Factory, interval string) *openLIT {
	olit := new(openLIT)
	olit.genAIPromQL = fmt.Sprintf("sum_over_time(gen_ai_requests_total{}[%s])", interval)
	olit.vdbPromQL = fmt.Sprintf("sum_over_time(db_requests_total{}[%s])", interval)
	olit.c = c
	olit.builder = builder
	sc := NewSemanticConventions()
	olit.semanticConventions = sc
	olit.requiredFieldsGenAI = []string{sc.TelemetrySdkLanguage, sc.ServiceName, sc.ServiceInstanceId, sc.ServiceNamespace, sc.GenAiEnvironment, sc.GenAiApplicationName, sc.GenAiSystem, sc.GenAiOperationName, sc.GenAiRequestModel}
	olit.requiredFieldsVDB = []string{sc.TelemetrySdkLanguage, sc.ServiceName, sc.ServiceInstanceId, sc.ServiceNamespace, sc.GenAiEnvironment, sc.GenAiApplicationName, sc.DBSystem, sc.DBOperation}
	return olit
}

func (o openLIT) PerformComponentIdentification() (err error) {
	metrics, err := o.checkGenAIMetrics()
	if metrics != nil {
		for _, metric := range *metrics {
			_ = o.inferGenAIComponents(metric)
			// TODO: retrieve and log error
		}
	}
	metrics, err = o.checkVDBMetrics()
	if err != nil {
		return
	}
	if metrics == nil {
		return
	}
	for _, metric := range *metrics {
		_ = o.inferVDBComponents(metric)
		// TODO: retrieve and log error
	}
	return
}

func (o openLIT) inferGenAIComponents(metric api.MetricResult) (err error) {
	err = o.validateMetricFieldsForGenAI(metric.Labels)
	if err != nil {
		return
	}

	base := o.baseComponent(metric.Labels)

	core := o.genAISystemComponent(metric.Labels)

	if !o.builder.RelationExists(base.ID, core.ID) {
		o.builder.MustNewRelation(base.ID, core.ID, "uses")
	}

	model := o.modelComponent(metric.Labels)

	if !o.builder.RelationExists(core.ID, model.ID) {
		o.builder.MustNewRelation(core.ID, model.ID, "runs")
	}

	op := o.operationComponent(metric.Labels)

	if !o.builder.RelationExists(model.ID, op.ID) {
		o.builder.MustNewRelation(model.ID, op.ID, "applies")
	}

	return
}

func (o openLIT) inferVDBComponents(metric api.MetricResult) (err error) {
	err = o.validateMetricFieldsForVDB(metric.Labels)
	if err != nil {
		return
	}

	base := o.baseComponent(metric.Labels)

	core := o.dbSystemComponent(metric.Labels)

	if !o.builder.RelationExists(base.ID, core.ID) {
		o.builder.MustNewRelation(base.ID, core.ID, "uses")
	}

	op := o.dbOperationComponent(metric.Labels)

	if !o.builder.RelationExists(core.ID, op.ID) {
		o.builder.MustNewRelation(core.ID, op.ID, "applies")
	}

	return
}

func (o openLIT) baseComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnGenAiApp(labels[o.GenAiApplicationName], labels[o.ServiceNamespace])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.GenAiApplicationName], o.CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = o.Domain
		c.AddLabel("gen_ai_app")
		c.AddLabelKey(toLabelKey(o.ServiceName), labels[o.ServiceName])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddLabelKey(toLabelKey(o.TelemetrySdkLanguage), labels[o.TelemetrySdkLanguage])
		c.AddProperty("namespaceIdentifier", o.UrnServiceNamespace(labels[o.ServiceNamespace]))
		c.AddProperty("clusterIdentifier", o.UrnCluster(o.builder.Cluster))
	}
	return
}

func (o openLIT) genAISystemComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnGenAiSystem(labels[o.GenAiSystem])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.GenAiSystem], fmt.Sprintf("genai.system.%s", strings.ToLower(labels[o.GenAiSystem])))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = o.Domain
		c.AddLabel("gen_ai_system")
		c.AddLabelKey(toLabelKey(o.GenAiApplicationName), labels[o.GenAiApplicationName])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddProperty("identifier", id)
		c.AddProperty("genai_environment", labels[o.GenAiEnvironment])
	}
	return
}

func (o openLIT) modelComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnGenAiModel(labels[o.GenAiRequestModel], labels[o.GenAiSystem])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.GenAiRequestModel], "genai.model")
		c.Data.Layer = "GenAiModels"
		c.Data.Domain = o.Domain
		c.AddLabelKey(toLabelKey(o.GenAiApplicationName), labels[o.GenAiApplicationName])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	return
}

func (o openLIT) operationComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnGenAiOperation(labels[o.GenAiOperationName], labels[o.GenAiRequestModel], labels[o.GenAiSystem])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.GenAiOperationName], "genai.operation")
		c.Data.Layer = "GenAiOperations"
		c.Data.Domain = o.Domain
		c.AddLabelKey(toLabelKey(o.GenAiApplicationName), labels[o.GenAiApplicationName])
		c.AddLabelKey(toLabelKey(o.GenAiRequestModel), labels[o.GenAiRequestModel])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	return
}

func (o openLIT) dbSystemComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnVectorDbSystem(labels[o.DBSystem])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.DBSystem], "genai.dbsystem.milvus")
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = o.Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(o.GenAiApplicationName), labels[o.GenAiApplicationName])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	return
}

func (o openLIT) dbOperationComponent(labels map[string]string) (c *receiver.Component) {
	id := o.UrnVectorDbOperation(labels[o.DBOperation], labels[o.DBSystem])
	if o.builder.ComponentExists(id) {
		c = o.builder.MustGetComponent(id)
	} else {
		c = o.builder.MustNewComponent(id, labels[o.DBOperation], "genai.dboperation")
		c.Data.Layer = "GenAiOperations"
		c.Data.Domain = o.Domain
		c.AddLabelKey(toLabelKey(o.GenAiApplicationName), labels[o.GenAiApplicationName])
		c.AddLabelKey(toLabelKey(o.DBSystem), labels[o.DBSystem])
		c.AddLabelKey(toLabelKey(o.ServiceNamespace), labels[o.ServiceNamespace])
		c.AddLabelKey(toLabelKey(o.GenAiEnvironment), labels[o.GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	return
}

func (o openLIT) checkGenAIMetrics() (*[]api.MetricResult, error) {
	response, err := o.c.QueryMetric(o.genAIPromQL, time.Now(), "10s")
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

func (o openLIT) checkVDBMetrics() (*[]api.MetricResult, error) {
	response, err := o.c.QueryMetric(o.vdbPromQL, time.Now(), "10s")
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

func (o openLIT) validateMetricFieldsForGenAI(labels map[string]string) error {
	for _, field := range o.requiredFieldsGenAI {
		if _, ok := labels[field]; !ok {
			return fmt.Errorf("required field %s is missing", field)
		}
	}
	return nil
}

func (o openLIT) validateMetricFieldsForVDB(labels map[string]string) error {
	for _, field := range o.requiredFieldsVDB {
		if _, ok := labels[field]; !ok {
			return fmt.Errorf("required field %s is missing", field)
		}
	}
	return nil
}
