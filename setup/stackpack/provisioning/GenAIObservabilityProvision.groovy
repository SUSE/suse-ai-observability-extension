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
      'integrationType': config.instance_type ?: 'opentelemetry',
      'integrationUrl': config.kubernetes_cluster_name ?: "local",
      'instanceId': context().instance().id()
    ]
    templateArguments.putAll(config)

    // We assume open-telemetry and kubernetes-v2 are already installed as per user's environment
    return context().stackPack().importSnapshot("templates/genai-observability.sty", [:]) >>
           context().instance().importSnapshot("templates/genai-observability-instance-template.sty", templateArguments)
  }

  @Override
  ProvisioningIO<scala.Unit> upgrade(Map<String, Object> config, Version current) {
    return install(config)
  }

  @Override
  void waitingForData(Map<String, Object> config) {
    // We use the OTel collector topic which should always have data
    context().sts().onDataReceived(topicName(config), {
      context().sts().provisioningComplete()
    })
  }

  private def topicName(Map<String, Object> config) {
    return "sts_topo_opentelemetry_collector"
  }
}
