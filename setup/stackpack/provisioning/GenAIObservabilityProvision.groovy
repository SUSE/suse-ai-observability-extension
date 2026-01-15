import com.stackstate.stackpack.ProvisioningScript
import com.stackstate.stackpack.ProvisioningContext
import com.stackstate.stackpack.ProvisioningIO
import com.stackstate.stackpack.Version

class GenAIObservabilityProvision extends ProvisioningScript {

  GenAIObservabilityProvision(ProvisioningContext context) {
    super(context)
  }

  @Override
  ProvisioningIO<scala.Unit> install(Map<String, Object> config) {
    def templateArguments = [
      'topicName': topicName(config),
      'integrationType': config.instance_type,
      'integrationUrl': config.kubernetes_cluster_name,
      'instanceId': context().instance().id()
    ]
    templateArguments.putAll(config)

    return context().sts().install("open-telemetry", [:]) >>
           context().sts().install("kubernetes-v2", ['kubernetes_cluster_name': config.kubernetes_cluster_name]) >>
           context().stackPack().importSnapshot("templates/genai-observability.sty", [:]) >>
           context().instance().importSnapshot("templates/genai-observability-instance-template.sty", templateArguments)
  }

  @Override
  ProvisioningIO<scala.Unit> upgrade(Map<String, Object> config, Version current) {
    return install(config)
  }

  @Override
  void waitingForData(Map<String, Object> config) {
    context().sts().onDataReceived(topicName(config), {
      context().sts().provisioningComplete()
    })
  }

  private def topicName(Map<String, Object> config) {
    def clusterName = config.kubernetes_cluster_name
    def type = config.instance_type
    return context().sts().createTopologyTopicName(type, clusterName)
  }
}
