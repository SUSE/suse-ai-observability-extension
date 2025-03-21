package receiver

import (
	"encoding/json"
	"fmt"
	"slices"
	"strconv"
)

// StackState Agent Api DTOs

type MetricType string
type EvtCategory string

const (
	MetricGauge    MetricType  = "gauge"
	MetricCount    MetricType  = "count"
	MetricRate     MetricType  = "rate"
	AlertsEvt      EvtCategory = "Alerts"
	ActivitiesEvt  EvtCategory = "Activities"
	ChangesEvt     EvtCategory = "Changes"
	DeploymentsEvt EvtCategory = "Deployments"
	OtherEvt       EvtCategory = "Other"
)

var (
	MetricTypes = [8]MetricType{MetricGauge, MetricCount, MetricRate}
)

type Events map[string][]*Event

type Event struct {
	Context        EventContext `json:"context"`
	EventType      string       `json:"event_type"`
	Title          string       `json:"msg_title"`
	Text           string       `json:"msg_text"`
	SourceTypeName string       `json:"source_type_name"`
	Tags           []string     `json:"tags"`
	Timestamp      int64        `json:"timestamp"`
}

type EventContext struct {
	Category           EvtCategory       `json:"category"`            // The event category. Can be Activities, Alerts, Anomalies, Changes or Others.
	Data               map[string]string `json:"data"`                // Optional. A list of key/value details about the event, for example a configuration version.
	ElementIdentifiers []string          `json:"element_identifiers"` // The identifiers for the topology element(s) the event relates to. These are used to bind the event to a topology element or elements.
	Source             string            `json:"source"`              // The name of the system from which the event originates, for example AWS, Kubernetes or JIRA.
	SourceLinks        []SourceLink      `json:"source_links"`
}

type SourceLink struct {
	Title string `json:"title"`
	URL   string `json:"url"`
}

type Type struct {
	Name string `json:"name"`
}

type Topology struct {
	StartSnapshot bool         `json:"start_snapshot"`
	StopSnapshot  bool         `json:"stop_snapshot"`
	Instance      Instance     `json:"instance"`
	Components    []*Component `json:"components"`
	Relations     []*Relation  `json:"relations"`
	DeleteIDs     []string     `json:"delete_ids"`
}

func NewEmptyTopology() *Topology {
	return &Topology{
		Instance:   Instance{},
		Components: []*Component{},
		Relations:  []*Relation{},
		DeleteIDs:  []string{},
	}
}

type Instance struct {
	Type string `json:"type" validate:"required"`
	URL  string `json:"url" validate:"required"`
}

type Relation struct {
	ExternalID string                 `json:"externalId"`
	SourceID   string                 `json:"sourceId"`
	TargetID   string                 `json:"targetId"`
	Type       Type                   `json:"type"`
	Data       map[string]interface{} `json:"data"`
}

type Data struct {
	Name             string                 `json:"name"`
	Layer            string                 `json:"layer"`
	Domain           string                 `json:"domain"`
	Environment      string                 `json:"environment"`
	Labels           []string               `json:"labels"`
	Identifiers      []string               `json:"identifiers"`
	CustomProperties map[string]interface{} `json:"custom_properties"`
	Properties       map[string]interface{} `json:"properties"`
}

type Component struct {
	ID               string                 `json:"-"`
	ExternalID       string                 `json:"externalId"`
	Type             Type                   `json:"type"`
	Data             Data                   `json:"data"`
	SourceProperties map[string]interface{} `json:"sourceProperties"`
}

func (c *Component) GetType() string {
	return c.Type.Name
}

func (c *Component) AddLabel(label string) {
	if !slices.Contains(c.Data.Labels, label) {
		c.Data.Labels = append(c.Data.Labels, label)
	}
}

func (c *Component) AddLabelKey(key string, value string) {
	c.AddLabel(fmt.Sprintf("%s:%s", key, value))
}

func (c *Component) AddIdentifier(id string) {
	if !slices.Contains(c.Data.Identifiers, id) {
		c.Data.Identifiers = append(c.Data.Identifiers, id)
	}
}

func (c *Component) AddCustomProperty(name string, value interface{}) {
	c.Data.CustomProperties[name] = value
}

func (c *Component) GetCustomProperty(name string) interface{} {
	return c.Data.CustomProperties[name]
}

func (c *Component) AddCustomPropertyMap(name string, value *PropertyMap) {
	c.Data.CustomProperties[name] = value
}

func (c *Component) GetCustomPropertyMap(name string) *PropertyMap {
	return c.Data.CustomProperties[name].(*PropertyMap)
}

func (c *Component) AddProperty(name string, value interface{}) {
	c.Data.Properties[name] = value
}

func (c *Component) MustGetIntProperty(name string) int {
	i, err := strconv.Atoi(c.Data.Properties[name].(string))
	if err != nil {
		panic(i)
	}
	return i
}

func (c *Component) AddSourceProperty(name string, value interface{}) {
	c.SourceProperties[name] = value
}

type StackstatePayload struct {
	CollectionTimestamp int64           `json:"collection_timestamp"` // Epoch timestamp in seconds
	InternalHostname    string          `json:"internalHostname"`     // The hostname sending the data
	Events              Events          `json:"events"`               // The events to send to StackState
	Metrics             []metrics       `json:"metrics"`              // Required present, but can be empty
	ServiceChecks       []serviceChecks `json:"service_checks"`       // Required present, but can be empty
	Health              []health        `json:"health"`               // Required present, but can be empty
	Topologies          []Topology      `json:"topologies"`           // Required present, but can be empty
}

type metrics struct{}

type serviceChecks struct{}

type health struct{}

func NewEmptyStackStatePayload() *StackstatePayload {
	return &StackstatePayload{
		Topologies:    []Topology{},
		Events:        Events{},
		Metrics:       []metrics{},
		ServiceChecks: []serviceChecks{},
		Health:        []health{},
	}
}

type MetricSeries struct {
	Series []*Metric `json:"series"`
}

type Metric struct {
	Name           string     `json:"metric"`
	Points         []Point    `json:"points"`
	Tags           []string   `json:"tags"`
	Host           string     `json:"host"`
	Type           MetricType `json:"type"`
	Interval       int        `json:"interval"`
	SourceTypeName string     `json:"source_type_name"`
}

type Point struct {
	Timestamp int64
	Value     float32
}

func (t *Point) MarshalJSON() ([]byte, error) {
	return json.Marshal(&[]interface{}{
		t.Timestamp,
		t.Value,
	})
}
