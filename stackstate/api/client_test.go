package api

import (
	"encoding/json"
	"fmt"
	"github.com/joho/godotenv"
	sts "genai-observability/stackstate"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"
)

var opts = &slog.HandlerOptions{Level: slog.LevelDebug}
var handler = slog.NewJSONHandler(os.Stdout, opts)
var logger = slog.New(handler)

func init() { slog.SetDefault(logger) }

func loadRespFile(w http.ResponseWriter, path string) {
	path = fmt.Sprintf("../../testdata/%s", path)
	_, err := os.Stat(path)
	if err == nil {
		file, err := os.ReadFile(path)
		if err == nil {
			_, err := w.Write(file)
			if err == nil {
				return
			}
		}
	}
	slog.Info("file not found", "path", path)
	w.WriteHeader(http.StatusNotFound)
}

func getMockServer(conf *sts.StackState, hf http.HandlerFunc) *httptest.Server {
	server := httptest.NewServer(hf)
	conf.ApiUrl = server.URL
	return server
}

func getClient(t *testing.T, hf http.HandlerFunc) (*Client, *httptest.Server) {
	conf := getConfig(t)
	server := getMockServer(conf, hf)
	client, _ := NewClient(conf)
	return client, server
}

func TestTraceQuery(t *testing.T) {
	client, server := getClient(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/traces/query", r.URL.Path)
		assert.NotEmpty(t, r.URL.Query().Get("start"))
		assert.NotEmpty(t, r.URL.Query().Get("end"))
		assert.NotEmpty(t, r.URL.Query().Get("page"))
		assert.NotEmpty(t, r.URL.Query().Get("pageSize"))
		loadRespFile(w, "api/traces/query/response.json")
	})
	defer server.Close()
	req := &TraceQueryRequest{
		TraceQuery: TraceQuery{
			SpanFilter: SpanFilter{
				Attributes: map[string][]string{
					"service.name": {"PirateJoker"},
				},
			},
			SortBy: []SortBy{
				{
					Field:     SpanSortSpanParentType,
					Direction: SortDirectionAscending,
				},
			},
		},
		Start:    time.Now().Add(-5 * time.Minute),
		End:      time.Now(),
		Page:     0,
		PageSize: 10,
	}
	response, err := client.QueryTraces(req)
	require.NoError(t, err)
	assert.Equal(t, 2, len(response.Traces))
}

func TestGetTrace(t *testing.T) {
	client, server := getClient(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/traces/xxx", r.URL.Path)
		loadRespFile(w, "api/traces/response.json")
	})
	defer server.Close()
	response, err := client.GetTrace("xxx")
	require.NoError(t, err)
	assert.Equal(t, 21, len(response.Spans))
}

func TestViewSnapshot(t *testing.T) {
	query := "type = 'pod' and label = 'namespace:virtual-cluster'"
	client, server := getClient(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/snapshot", r.URL.Path)
		queryReq := ViewSnapshotRequest{}
		err := json.NewDecoder(r.Body).Decode(&queryReq)
		require.NoError(t, err)
		assert.Equal(t, query, queryReq.Query)
		loadRespFile(w, "api/snapshot/response.json")
	})
	defer server.Close()
	// Comment out mock above and uncomment below to test on a live server and debug requests.
	//DumpHttpRequest = true
	//client := NewClient(getConfig(t))
	response, err := client.SnapShotTopologyQuery(query)
	require.NoError(t, err)
	assert.Equal(t, 3, len(response))
}

func TestQuery(t *testing.T) {
	client, server := getClient(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/metrics/query", r.URL.Path)
		assert.NotEmpty(t, r.URL.Query().Get("time"))
		assert.NotEmpty(t, r.URL.Query().Get("query"))
		assert.Equal(t, r.URL.Query().Get("timeout"), DefaultTimeout)
		loadRespFile(w, "api/metrics/query/response.json")
	})
	defer server.Close()
	query := `round(sum by (cluster_name, namespace, pod_name)(container_cpu_usage / 1000000000) / sum by (cluster_name, namespace, pod_name) (kubernetes_cpu_requests), 0.001)`
	now := time.Now()
	response, err := client.QueryMetric(query, now, DefaultTimeout)
	require.NoError(t, err)
	assert.Equal(t, "success", response.Status)
}

func TestQueryRange(t *testing.T) {
	client, server := getClient(t, func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/metrics/query_range", r.URL.Path)
		assert.NotEmpty(t, r.URL.Query().Get("start"))
		assert.NotEmpty(t, r.URL.Query().Get("end"))
		assert.NotEmpty(t, r.URL.Query().Get("query"))
		assert.NotEmpty(t, r.URL.Query().Get("step"))
		assert.Equal(t, r.URL.Query().Get("timeout"), DefaultTimeout)
		loadRespFile(w, "api/metrics/query_range/response.json")
	})
	defer server.Close()
	query := `sum by (cluster_name) (max_over_time(kubernetes_state_node_count{cluster_name="susecon-frb-cluster-0"}[${__interval}]))`
	now := time.Now()
	begin := now.Add(-5 * time.Minute)
	response, err := client.QueryRangeMetric(query, begin, now, "1m", DefaultTimeout)
	require.NoError(t, err)
	assert.Equal(t, "success", response.Status)
}

func TestClientConnection(t *testing.T) {
	conf := getConfig(t)
	client, _ := NewClient(conf)
	status, err := client.Status()
	require.NoError(t, err, `Not expecting err %v`, err)
	assert.Equal(t, status.Version.Major, 6)
}

func TestTopologyQuery(t *testing.T) {
	conf := getConfig(t)
	client, _ := NewClient(conf)
	res, err := client.TopologyQuery("type = 'service' and label in ('namespace:kube-system')", "", false)
	require.NoError(t, err)
	require.True(t, res.Success, `Expected to be successful but was %s`, toJson(res))
	assert.True(t, len(res.Data) > 0)
	fmt.Println(toJson(res))
}

func TestTopologyStreamQuery(t *testing.T) {
	conf := getConfig(t)
	client, _ := NewClient(conf)
	res, err := client.TopologyStreamQuery("type = 'service' and label in ('namespace:kube-system')", "", true)
	require.NoError(t, err)
	require.True(t, res.Success, `Expected to be successful but was %s`, toJson(res))
	assert.True(t, len(res.Data) > 0)
	fmt.Println(toJson(res))
}

func toJson(a any) string {
	marshal, err := json.Marshal(a)
	if err != nil {
		fmt.Printf("Failed to marshall json. %v", err)
	}
	return string(marshal)
}

func getConfig(t *testing.T) *sts.StackState {
	require.NoError(t, godotenv.Load("../../.env"))
	return &sts.StackState{
		ApiUrl:   os.Getenv("STS_URL"),
		ApiKey:   os.Getenv("STS_API_KEY"),
		ApiToken: os.Getenv("STS_TOKEN"),
	}
}
