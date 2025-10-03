package identifier

import (
	"genai-observability/stackstate/api"
	"genai-observability/stackstate/receiver"
	"genai-observability/internal/config"
	"genai-observability/internal/watcher"
)

type Watcher interface{
	PerformComponentIdentification() (error)
}

type componentIdentifier struct{
	config *config.Configuration
	client *api.Client
	watchers []Watcher
	builder *receiver.Factory
}

func (c *componentIdentifier) registerWatcher(w Watcher) {
	c.watchers = append(c.watchers, w)
}

type ComponentIdentifierFactory struct{}

func (c ComponentIdentifierFactory) Build(conf *config.Configuration) (compId *componentIdentifier, err error) {
	compId = new(componentIdentifier)
	compId.client, err = api.NewClient(&conf.StackState)
	if err != nil {
		return
	}

	compId.builder = receiver.NewFactory("openlit", "openlit", conf.Kubernetes.Cluster)


	if conf.Preferences.EnableOpenLIT {
		compId.registerWatcher(watcher.NewOpenLITWatcher(compId.client, compId.builder))
	}
	compId.registerWatcher(watcher.NewMilvusWatcher(compId.client, compId.builder))
	compId.registerWatcher(watcher.NewVLLMWatcher(compId.client, compId.builder))

	return

}

func (c componentIdentifier) Sync() {
	for _, w := range(c.watchers){
		w.PerformComponentIdentification() // TODO: make it async by adding a mutex to builder
	}
}

func (c componentIdentifier) GetBuilder() *receiver.Factory {
	return c.builder
}
