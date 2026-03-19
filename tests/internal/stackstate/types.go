package stackstate

type Component struct {
	ID          int64             `json:"id"`
	Name        string            `json:"name"`
	Type        string            `json:"type"`
	Layer       string            `json:"layer"`
	Domain      string            `json:"domain"`
	Labels      []string          `json:"labels"`
	ExternalID  string            `json:"externalId"`
	Identifiers []string          `json:"identifiers"`
	Properties  map[string]string `json:"properties"`
}

type Relation struct {
	ID       int64  `json:"id"`
	Name     string `json:"name"`
	Type     string `json:"type"`
	SourceID int64  `json:"sourceId"`
	TargetID int64  `json:"targetId"`
}

type HealthState string

const (
	HealthClear     HealthState = "CLEAR"
	HealthDeviating HealthState = "DEVIATING"
	HealthCritical  HealthState = "CRITICAL"
	HealthUnknown   HealthState = "UNKNOWN"
)

type TopologyQueryResult struct {
	Components []Component `json:"components"`
	Relations  []Relation  `json:"relations"`
}
