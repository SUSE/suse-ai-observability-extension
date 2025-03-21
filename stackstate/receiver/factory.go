package receiver

import (
	"fmt"
	"time"
)

type PropertyMap map[string]interface{}

type Factory struct {
	Cluster     string
	Lookup      map[string]interface{}
	source      string
	extIdPrefix string
	components  map[string]*Component
	relations   map[string]*Relation
	events      []*Event
	metrics     []*Metric
}

func NewFactory(source, extIdPrefix, cluster string) *Factory {
	return &Factory{
		Cluster:     cluster,
		Lookup:      make(map[string]interface{}),
		source:      source,
		extIdPrefix: extIdPrefix,
		components:  make(map[string]*Component),
		relations:   make(map[string]*Relation),
		events:      []*Event{},
		metrics:     []*Metric{},
	}
}

func (f *Factory) GetComponentsOfType(ctype string) []*Component {
	result := make([]*Component, 0)
	for _, c := range f.components {
		if c.Type.Name == ctype {
			result = append(result, c)
		}
	}
	return result
}

func (f *Factory) GetComponentCount() int {
	return len(f.components)
}

func (f *Factory) GetRelationCount() int {
	return len(f.relations)
}

func (f *Factory) GetEventCount() int {
	return len(f.events)
}

func (f *Factory) GetMetricCount() int {
	return len(f.metrics)
}

func (f *Factory) AddEvent(e *Event) {
	f.events = append(f.events, e)
}

func (f *Factory) AddMetric(m *Metric) {
	f.metrics = append(f.metrics, m)
}

func (f *Factory) ComponentExists(id string) bool {
	_, ok := f.components[id]
	return ok
}

func (f *Factory) MustGetComponent(id string) *Component {
	c, err := f.GetComponent(id)
	if err != nil {
		panic(err)
	}
	return c
}

func (f *Factory) GetComponent(id string) (*Component, error) {
	c, ok := f.components[id]
	if !ok {
		return nil, fmt.Errorf("component '%s' not found", id)
	}
	return c, nil
}

func (f *Factory) MustNewComponent(id string, name string, cType string) *Component {
	c, err := f.NewComponent(id, name, cType)
	if err != nil {
		panic(err)
	}
	return c
}

func (f *Factory) NewComponent(id string, name string, cType string) (*Component, error) {
	if _, ok := f.components[id]; ok {
		return nil, fmt.Errorf("component '%s' already exists", id)
	}
	c := &Component{
		ID:         id,
		ExternalID: f.getExtIdFor(id),
		Type: Type{
			Name: cType,
		},
		Data: Data{
			Name:             name,
			Layer:            "unknown",
			Domain:           "unknown",
			Environment:      "Production",
			Labels:           []string{},
			Identifiers:      []string{id},
			CustomProperties: make(map[string]interface{}),
			Properties:       make(map[string]interface{}),
		},
		SourceProperties: map[string]interface{}{},
	}
	f.components[id] = c
	return c, nil
}

func (f *Factory) getExtIdFor(id string) string {
	if f.extIdPrefix == "" {
		return id
	} else {
		return fmt.Sprintf("%s:%s", f.extIdPrefix, id)
	}
}

func relId(sourceId string, targetId string) string {
	return fmt.Sprintf("%s --> %s", sourceId, targetId)
}
func (f *Factory) RelationExists(sid string, tid string) bool {
	_, ok := f.relations[relId(sid, tid)]
	return ok
}

func (f *Factory) MustGetRelation(sid string, tid string) *Relation {
	r, err := f.GetRelation(sid, tid)
	if err != nil {
		panic(err)
	}
	return r
}

func (f *Factory) GetRelation(sid string, tid string) (*Relation, error) {
	rid := relId(sid, tid)
	r, ok := f.relations[rid]
	if !ok {
		return nil, fmt.Errorf("relation '%s' not found", rid)
	}
	return r, nil
}

func (f *Factory) MustNewRelation(sid string, tid string, cType string) *Relation {
	r, err := f.NewRelation(sid, tid, cType)
	if err != nil {
		panic(err)
	}
	return r
}

func (f *Factory) NewRelation(sourceId string, targetId string, cType string) (*Relation, error) {
	rid := relId(sourceId, targetId)
	if _, ok := f.relations[rid]; ok {
		return nil, fmt.Errorf("relation '%s' already exists", rid)
	}
	r := &Relation{
		ExternalID: rid,
		SourceID:   f.getExtIdFor(sourceId),
		TargetID:   f.getExtIdFor(targetId),
		Type: Type{
			Name: cType,
		},
		Data: map[string]interface{}{},
	}
	f.relations[rid] = r
	return r, nil
}

func (f *Factory) NewEvent(title string, msg string, eType string, elemIds ...string) *Event {
	e := Event{
		Context: EventContext{
			Category:           AlertsEvt,
			Data:               make(map[string]string),
			ElementIdentifiers: elemIds,
			Source:             f.source,
			SourceLinks:        []SourceLink{},
		},
		EventType:      eType,
		Title:          title,
		Text:           msg,
		SourceTypeName: f.source,
		Tags:           []string{},
		Timestamp:      time.Now().Unix(),
	}
	return &e
}

func (f *Factory) NewMetric(name string, value float32) *Metric {
	m := Metric{
		Name: name,
		Points: []Point{
			{
				Timestamp: time.Now().Unix(),
				Value:     value,
			},
		},
		Tags:           make([]string, 0),
		Host:           "internal",
		Type:           MetricGauge,
		Interval:       0,
		SourceTypeName: f.source,
	}
	return &m
}

func (f *Factory) Tag(name, value string) string {
	return fmt.Sprintf("%s:%s", name, value)
}

func (f *Factory) UrnPod(name, namespace string) string {
	return fmt.Sprintf("urn:kubernetes:/%s:%s:pod/%s", f.Cluster, namespace, name)
}

func (f *Factory) UrnNode(name string) string {
	return fmt.Sprintf("urn:kubernetes:/%s:node/%s", f.Cluster, name)

}

func (f *Factory) UrnService(name, namespace string) string {
	return fmt.Sprintf("urn:kubernetes:/%s:%s:service/%s", f.Cluster, namespace, name)
}

func (f *Factory) UrnContainer(name, podName, namespace string) string {
	return fmt.Sprintf("urn:kubernetes:/%s:%s:pod/%s:container/%s", f.Cluster, namespace, podName, name)
}

func (f *Factory) UrnNamespace(name string) string {
	return fmt.Sprintf("urn:kubernetes:/%s:namespace/%s", f.Cluster, name)
}
