package sync

import (
	"fmt"
	"genai-observability/stackstate/receiver"
	"strings"
)

func mapSUSEAI(labels map[string]string, f *receiver.Factory) (c *receiver.Component) {
	id := UrnGenAiApp(labels[ServiceName], labels[ServiceNamespace])
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[ServiceName], CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = "OpenTelemetry VectorDB"
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(ServiceName), labels[ServiceName])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddProperty("namespaceIdentifier", UrnServiceNamespace(labels[ServiceNamespace]))
		c.AddProperty("clusterIdentifier", UrnCluster(f.Cluster))
	}
	return
}

func mapGenAiApp(labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnGenAiApp(labels[GenAiApplicationName], labels[ServiceNamespace])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[GenAiApplicationName], CTypeGenAiApp)
		c.Data.Layer = "Services"
		c.Data.Domain = Domain
		c.AddLabel("gen_ai_app")
		c.AddLabelKey(toLabelKey(ServiceName), labels[ServiceName])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddLabelKey(toLabelKey(TelemetrySdkLanguage), labels[TelemetrySdkLanguage])
		c.AddProperty("namespaceIdentifier", UrnServiceNamespace(labels[ServiceNamespace]))
		c.AddProperty("clusterIdentifier", UrnCluster(f.Cluster))
	}
	return c
}

func mapGenAiSystem(appComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnGenAiSystem(labels[GenAiSystem])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[GenAiSystem], fmt.Sprintf("genai.system.%s", strings.ToLower(labels[GenAiSystem])))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = Domain
		c.AddLabel("gen_ai_system")
		c.AddLabelKey(toLabelKey(GenAiApplicationName), labels[GenAiApplicationName])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddProperty("identifier", id)
		c.AddProperty("genai_environment", labels[GenAiEnvironment])
	}
	if !f.RelationExists(appComp.ID, c.ID) {
		f.MustNewRelation(appComp.ID, c.ID, "uses")
	}
	return c
}

func mapVectorSUSEAIDbSystem(appComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	serviceName := labels["service_name"]
	id := UrnVectorDbSystem(serviceName)
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, serviceName, fmt.Sprintf("genai.dbsystem.%s", strings.ToLower(serviceName)))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddProperty("identifier", id)
	}
	if !f.RelationExists(appComp.ID, c.ID) {
		f.MustNewRelation(appComp.ID, c.ID, "is")
	}
	return c
}

func mapVectorDbSystem(appComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnVectorDbSystem(labels[DBSystem])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[DBSystem], fmt.Sprintf("genai.dbsystem.%s", strings.ToLower(labels[DBSystem])))
		c.Data.Layer = "GenAiSystems"
		c.Data.Domain = Domain
		c.AddLabel("gen_vectordb_system")
		c.AddLabelKey(toLabelKey(GenAiApplicationName), labels[GenAiApplicationName])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	if !f.RelationExists(appComp.ID, c.ID) {
		f.MustNewRelation(appComp.ID, c.ID, "uses")
	}
	return c
}

func mapGenAiModel(sysComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnGenAiModel(labels[GenAiRequestModel], labels[GenAiSystem])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[GenAiRequestModel], "genai.model")
		c.Data.Layer = "GenAiModels"
		c.Data.Domain = Domain
		c.AddLabelKey(toLabelKey(GenAiApplicationName), labels[GenAiApplicationName])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	if !f.RelationExists(sysComp.ID, c.ID) {
		f.MustNewRelation(sysComp.ID, c.ID, "runs")
	}
	return c
}

func mapGenAiOperation(modelComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnGenAiOperation(labels[GenAiOperationName], labels[GenAiRequestModel], labels[GenAiSystem])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[GenAiOperationName], "genai.operation")
		c.Data.Layer = "GenAiOperations"
		c.Data.Domain = Domain
		c.AddLabelKey(toLabelKey(GenAiApplicationName), labels[GenAiApplicationName])
		c.AddLabelKey(toLabelKey(GenAiRequestModel), labels[GenAiRequestModel])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	if !f.RelationExists(modelComp.ID, c.ID) {
		f.MustNewRelation(modelComp.ID, c.ID, "applies")
	}
	return c
}

func mapVectorDbOperation(sysComp *receiver.Component, labels map[string]string, f *receiver.Factory) *receiver.Component {
	id := UrnVectorDbOperation(labels[DBOperation], labels[DBSystem])
	var c *receiver.Component
	if f.ComponentExists(id) {
		c = f.MustGetComponent(id)
	} else {
		c = f.MustNewComponent(id, labels[DBOperation], "genai.dboperation")
		c.Data.Layer = "GenAiOperations"
		c.Data.Domain = Domain
		c.AddLabelKey(toLabelKey(GenAiApplicationName), labels[GenAiApplicationName])
		c.AddLabelKey(toLabelKey(DBSystem), labels[DBSystem])
		c.AddLabelKey(toLabelKey(ServiceNamespace), labels[ServiceNamespace])
		c.AddLabelKey(toLabelKey(GenAiEnvironment), labels[GenAiEnvironment])
		c.AddProperty("identifier", id)
	}
	if !f.RelationExists(sysComp.ID, c.ID) {
		f.MustNewRelation(sysComp.ID, c.ID, "applies")
	}
	return c
}
