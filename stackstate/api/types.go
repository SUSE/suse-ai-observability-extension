package api

import (
	"encoding/json"
	"strconv"
	"strings"
	"time"
)

// StackState Server Api DTOs

type ServerInfo struct {
	Version struct {
		Major  int    `json:"major"`
		Patch  int    `json:"patch"`
		Diff   string `json:"diff"`
		Commit string `json:"commit"`
		IsDev  bool   `json:"isDev"`
	} `json:"version"`
	DeploymentMode string `json:"deploymentMode"`
}

type SyncComponent struct {
	Id                  int                    `json:"id"`
	Identifiers         []string               `json:"identifiers"`
	Labels              []Label                `json:"labels"`
	Environments        []int                  `json:"environments"`
	Domain              int                    `json:"domain"`
	LastUpdateTimestamp int                    `json:"lastUpdateTimestamp"`
	Layer               int                    `json:"layer"`
	Name                string                 `json:"name"`
	Properties          map[string]interface{} `json:"properties"`
	State               map[string]interface{} `json:"state"`
	SyncedElems         []SyncElem             `json:"synced"`
	SyncedData          map[string][]SyncData  `json:"synchronizationData"`

	Tags []string `json:"tags"`
}

// SyncData returned in a TopologyStream Query
type SyncData struct {
	Data             map[string]interface{} `json:"data"`
	SourceProperties map[string]interface{} `json:"sourceProperties"`
}

// SyncElem return in a Topology Query with full component
type SyncElem struct {
	Type               string             `json:"_type"`
	ExtTopologyElement ExtTopologyElement `json:"extTopologyElement"`
}

type ExtTopologyElement struct {
	ElementTypeTag   string                 `json:"elementTypeTag"`
	ExternalId       string                 `json:"externalId"`
	Id               int64                  `json:"id"`
	Identifiers      []string               `json:"identifiers"`
	Data             map[string]interface{} `json:"data"`
	Tags             map[string]interface{} `json:"tags"`
	SourceProperties map[string]interface{} `json:"sourceProperties"`
}
type Label string

func (t *Label) UnmarshalJSON(data []byte) error {
	if string(data) == "null" || string(data) == `""` {
		return nil
	}

	var label map[string]string
	if err := json.Unmarshal(data, &label); err != nil {
		return err
	}

	*t = Label(label["name"])
	return nil
}

type MetricQueryResponse struct {
	Status string      `json:"status"`
	Errors []*ErrorMsg `json:"errors"`
	Data   MetricData  `json:"data"`
}

type MetricData struct {
	ResultType string         `json:"resultType"`
	Result     []MetricResult `json:"result"`
}

func (m *MetricData) UnmarshalJSON(data []byte) error {
	mapFromArray := func(m *MetricPoint, data []any) error {
		// Assign array values to the struct fields
		var err error
		m.Timestamp = int64(data[0].(float64))
		m.Value, err = strconv.ParseFloat(strings.TrimSpace(data[1].(string)), 64)
		if err != nil {
			return err
		}
		return nil
	}

	var dataMap map[string]any
	if err := json.Unmarshal(data, &dataMap); err != nil {
		return err
	}
	m.ResultType = dataMap["resultType"].(string)

	resultList := dataMap["result"].([]any)
	if m.ResultType == "scalar" || m.ResultType == "string" {
		mr := MetricResult{
			Labels: make(map[string]string),
			Points: make([]MetricPoint, 0, 1),
		}
		mr.Points = append(mr.Points, MetricPoint{})
		err := mapFromArray(&mr.Points[0], resultList)
		if err != nil {
			return err
		}
		m.Result = []MetricResult{mr}
		return nil
	}

	valueKey := "value"
	if m.ResultType == "matrix" {
		valueKey = "values"
	}
	m.Result = make([]MetricResult, 0, len(resultList))
	for _, item := range resultList {
		resultMap := item.(map[string]any)
		labels := resultMap["metric"].(map[string]any)
		mr := MetricResult{
			Labels: make(map[string]string, len(labels)),
			Points: make([]MetricPoint, 0, len(resultMap[valueKey].([]any))),
		}

		for k, v := range labels {
			mr.Labels[k] = v.(string)
		}

		if m.ResultType == "matrix" {
			for x, point := range resultMap["values"].([]any) {
				mr.Points = append(mr.Points, MetricPoint{})
				err := mapFromArray(&mr.Points[x], point.([]any))
				if err != nil {
					return err
				}
			}
		} else {
			mr.Points = append(mr.Points, MetricPoint{})
			err := mapFromArray(&mr.Points[0], resultMap["value"].([]any))
			if err != nil {
				return err
			}
		}
		m.Result = append(m.Result, mr)
	}

	return nil
}

type MetricResult struct {
	Labels map[string]string `json:"metric"`
	Points []MetricPoint     `json:"values"`
}

type MetricPoint struct {
	Timestamp int64   `json:"timestamp"`
	Value     float64 `json:"value"`
}

type TopoQueryResponse struct {
	Success bool            `json:"success"`
	Errors  []*ErrorMsg     `json:"errors"`
	Data    []SyncComponent `json:"data"`
}

type ErrorResp struct {
	Errors []*ErrorMsg `json:"errors"`
}

type SuccessResp struct {
	Result []SyncComponent `json:"result"`
}

type ErrorMsg struct {
	Message   string `json:"message"`
	ErrorCode int    `json:"errorCode"`
}

type scriptRequest struct {
	ReqType string `json:"_type"`
	Body    string `json:"body"`
}

type querySnapshotResult struct {
	ViewSnapshotResponse ViewSnapshotResponse `json:"viewSnapshotResponse"`
}

type ViewSnapshotResponse struct {
	Success    bool `json:"success"`
	Components []ViewComponent
	Errors     []*ErrorMsg `json:"errors"`
}

type ViewComponent struct {
	ID                  int64   `json:"id"`
	Name                string  `json:"name"`
	Description         string  `json:"description"`
	LastUpdateTimestamp int64   `json:"lastUpdateTimestamp"`
	Type                int64   `json:"type"`
	Layer               int     `json:"layer"`
	Domain              int     `json:"domain"`
	Environments        []int64 `json:"environments"`
	State               struct {
		ID                    int64  `json:"id"`
		LastUpdateTimestamp   int64  `json:"lastUpdateTimestamp"`
		HealthState           string `json:"healthState"`
		PropagatedHealthState string `json:"propagatedHealthState"`
		Type                  string `json:"_type"`
	} `json:"state"`
	OutgoingRelations []int64           `json:"outgoingRelations"`
	IncomingRelations []int64           `json:"incomingRelations"`
	Synchronized      bool              `json:"synchronized"`
	FailingChecks     []any             `json:"failingChecks"`
	RetrievalSource   string            `json:"retrievalSource"`
	Identifiers       []string          `json:"identifiers"`
	Tags              []string          `json:"tags"`
	Properties        map[string]string `json:"properties"`
	InternalType      string            `json:"_type"`
}

type ViewSnapshotRequest struct {
	Type         string               `json:"_type"`
	Metadata     ViewSnapshotMetadata `json:"metadata"`
	Query        string               `json:"query"`
	QueryVersion string               `json:"queryVersion"`
}

type ViewSnapshotMetadata struct {
	Type                  string `json:"_type"`
	ShowFullComponent     bool   `json:"showFullComponent"`
	GroupingEnabled       bool   `json:"groupingEnabled"`
	ShowIndirectRelations bool   `json:"showIndirectRelations"`
	MinGroupSize          int    `json:"minGroupSize"`
	GroupedByLayer        bool   `json:"groupedByLayer"`
	GroupedByDomain       bool   `json:"groupedByDomain"`
	GroupedByRelation     bool   `json:"groupedByRelation"`
	ShowCause             string `json:"showCause"`
	AutoGrouping          bool   `json:"autoGrouping"`
	ConnectedComponents   bool   `json:"connectedComponents"`
	NeighboringComponents bool   `json:"neighboringComponents"`
	QueryTime             int64  `json:"queryTime,omitempty"`
}

func NewViewSnapshotRequest(query string) *ViewSnapshotRequest {
	return &ViewSnapshotRequest{
		Type: "ViewSnapshotRequest",
		Metadata: ViewSnapshotMetadata{
			Type:         "QueryMetadata",
			MinGroupSize: 2,
			ShowCause:    "NONE",
		},
		Query:        query,
		QueryVersion: "0.0.1",
	}
}

type NodeType struct {
	TypeName            string `json:"typeName"`
	ID                  int64  `json:"id"`
	LastUpdateTimestamp int64  `json:"lastUpdateTimestamp"`
	Identifier          string `json:"identifier"`
	Name                string `json:"name"`
	Description         string `json:"description"`
	OwnedBy             string `json:"ownedBy"`
	Manual              bool   `json:"manual"`
	IsSettingsNode      bool   `json:"isSettingsNode"`
	Type                string `json:"_type"`
}

type TraceQueryRequest struct {
	TraceQuery TraceQuery `json:"traceQuery"`
	Start      time.Time  `json:"start"`
	End        time.Time  `json:"end"`
	Page       int        `json:"page"`
	PageSize   int        `json:"pageSize"`
}

type TraceQuery struct {
	SpanFilter      SpanFilter `json:"spanFilter"`
	Filter          SpanFilter `json:"filter"` // deprecated. Used with legacy API
	SortBy          []SortBy   `json:"sortBy"`
	TraceAttributes Attributes `json:"traceAttributes"`
}

type Attributes map[string]string
type FilterAttributes map[string][]string

type SortBy struct {
	Field     SortField     `json:"field"`     // see sort fields constants
	Direction SortDirection `json:"direction"` // see sort direction constants
}

type SpanFilter struct {
	SpanParentType    []SpanParentType `json:"spanParentTyp,omitempty"`
	ServiceName       []string         `json:"serviceName,omitempty"`
	SpanName          []string         `json:"spanName,omitempty"`
	Attributes        FilterAttributes `json:"attributes,omitempty"`
	SpanKind          []SpanKind       `json:"spanKind,omitempty"` // see span kind constants
	DurationFromNanos int64            `json:"durationFromNanos,omitempty"`
	DurationToNanos   int64            `json:"durationToNanos,omitempty"`
	StatusCode        []StatusCode     `json:"statusCode,omitempty"` // see status code constants
	TraceId           []string         `json:"traceId,omitempty"`
	SpanId            []string         `json:"spanId,omitempty"`
	ScopeName         []string         `json:"scopeName,omitempty"`
	ScopeVersion      []string         `json:"scopeVersion,omitempty"`
}

type SpanParentType string
type SpanKind string
type StatusCode string
type SortDirection string
type SortField string

const (
	//SpanParentType Span Parent Types
	SpanParentTypeExternal SpanParentType = "External"
	SpanParentTypeRoot     SpanParentType = "Root"

	// SpanKind Span Kinds
	SpanKindClient      SpanKind = "SPAN_KIND_CLIENT"
	SpanKindServer      SpanKind = "SPAN_KIND_SERVER"
	SpanKindProducer    SpanKind = "SPAN_KIND_PRODUCER"
	SpanKindConsumer    SpanKind = "SPAN_KIND_CONSUMER"
	SpanKindInternal    SpanKind = "SPAN_KIND_INTERNAL"
	SpanKindUnspecified SpanKind = "SPAN_KIND_UNSPECIFIED"

	// StatusCode Status Codes
	StatusOk    StatusCode = "ok"
	StatusError StatusCode = "error"
	StatusUnset StatusCode = "unset"

	// SortField Sort fields
	SpanSortStartTime      SortField = "StartTime"
	SpanSortServiceName    SortField = "ServiceName"
	SpanSortSpanName       SortField = "SpanName"
	SpanSortSpanKind       SortField = "SpanKind"
	SpanSortSpanParentType SortField = "SpanParentType"
	SpanSortDurationNanos  SortField = "DurationNanos"
	SpanSortStatusCode     SortField = "StatusCode"
	SpanSortTraceId        SortField = "TraceId"
	SpanSortSpanId         SortField = "SpanId"
	SpanSortScopeName      SortField = "ScopeName"
	SpanSortScopeVersion   SortField = "ScopeVersion"

	// SortDirection Sort directions
	SortDirectionAscending  SortDirection = "Ascending"
	SortDirectionDescending SortDirection = "Descending"
)

type TraceQueryResponse struct {
	Traces       []TraceRef `json:"traces"`
	PageSize     int        `json:"pageSize"`
	Page         int        `json:"page"`
	MatchesTotal int        `json:"matchesTotal"`
}

// Legacy Api for Trace Query
type SpansQueryResponse struct {
	Spans        []TraceRef `json:"spans"`
	PageSize     int        `json:"pageSize"`
	Page         int        `json:"page"`
	MatchesTotal int        `json:"matchesTotal"`
}

type TraceRef struct {
	TraceID string `json:"traceId"`
	SpanID  string `json:"spanId"`
}

type Trace struct {
	TraceID string `json:"traceId"`
	Spans   []Span `json:"spans"`
}

type SpanTime struct {
	Timestamp   int64 `json:"timestamp"`
	OffsetNanos int   `json:"offsetNanos"`
}

type Span struct {
	StartTime          SpanTime    `json:"startTime"`
	EndTime            SpanTime    `json:"endTime"`
	DurationNanos      int         `json:"durationNanos"`
	TraceID            string      `json:"traceId"`
	SpanID             string      `json:"spanId"`
	ParentSpanID       string      `json:"parentSpanId"`
	SpanName           string      `json:"spanName"`
	ServiceName        string      `json:"serviceName"`
	SpanKind           string      `json:"spanKind"`
	SpanParentType     string      `json:"spanParentType"`
	ResourceAttributes Attributes  `json:"resourceAttributes"`
	SpanAttributes     Attributes  `json:"spanAttributes"`
	StatusCode         string      `json:"statusCode"`
	ScopeName          string      `json:"scopeName"`
	Events             []SpanEvent `json:"events"`
	Links              []any       `json:"links"`
}

type SpanEvent struct {
	Timestamp  SpanTime   `json:"timestamp"`
	Name       string     `json:"name"`
	Attributes Attributes `json:"attributes"`
}
