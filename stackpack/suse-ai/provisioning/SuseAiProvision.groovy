import com.stackstate.stackpack.ProvisioningScript
import com.stackstate.stackpack.ProvisioningContext
import com.stackstate.stackpack.ProvisioningIO
import com.stackstate.stackpack.Version

class SuseAiProvision extends ProvisioningScript {

    SuseAiProvision(ProvisioningContext context) {
        super(context)
    }

    @Override
    ProvisioningIO<scala.Unit> install(Map<String, Object> config) {
        return context().stackPack().importSnapshot('templates/suse-ai.sty', [:])
    }

    @Override
    ProvisioningIO<scala.Unit> upgrade(Map<String, Object> config, Version current) {
        return install(config)
    }

}

