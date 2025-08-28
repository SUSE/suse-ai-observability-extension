import com.stackstate.stackpack.ProvisioningScript
import com.stackstate.stackpack.ProvisioningContext
import com.stackstate.stackpack.ProvisioningIO
import com.stackstate.stackpack.Version

class ObservabilityExtensionProvision extends ProvisioningScript {

  ObservabilityExtensionProvision(ProvisioningContext context) {
    super(context)
  }

  @Override
  ProvisioningIO<scala.Unit> install(Map<String, Object> config) {
    // Import the umbrella snapshot with all templates (bindings, views)
    return context().stackPack().importSnapshot("templates/gen-ai-observability.sty", [:])
  }

  @Override
  ProvisioningIO<scala.Unit> upgrade(Map<String, Object> config, Version current) {
    return install(config)
  }
}
