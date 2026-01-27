## The SUSE AI Observability Extension StackPack is waiting for your action, please send some topology to StackState

The synchronization has been installed.

Next, you can manually test the synchronization to ensure it is working correctly. You can use an HTTP POST request to push topology information to StackState using the [common JSON object](https://documentation.suse.com/cloudnative/suse-observability/latest/en/configure/health/send-health-data/send-health-data.html#_json).

## Example POST request

The example below will create a component in StackState with type `genai.app` and name `myGenAIApp`. 

1. Save a file named `topology.json` with the following content

```json
{
   "apiKey":"{{config.apiKey}}",
   "internalHostname":"genai-observability.srv.stackstate.com",
   "topologies":[
      {
         "start_snapshot": false,
         "stop_snapshot": false,
         "instance":{
            "type":"{{configurationConfig.instance_type}}",
            "url":"{{configurationConfig.kubernetes_cluster_name}}"
         },
         "components":[
            {
               "externalId":"myGenAIApp",
               "type":{
                  "name":"genai.app"
               },
               "data":{
                  "name": "My GenAI Application",
                  "labels":["gen_ai_app", "production"],
                  "layer": "Applications",
                  "domain": "GenAI"
               }
            },
            {
               "externalId":"myLLMSystem",
               "type":{
                  "name":"genai.system.vllm"
               },
               "data":{
                  "name": "vLLM Server",
                  "labels":["gen_ai_system", "vllm"],
                  "layer": "Services",
                  "domain": "GenAI"
               }
            }
         ],
         "relations":[
            {
               "externalId":"app-to-llm",
               "type":{
                  "name":"uses"
               },
               "sourceId":"myGenAIApp",
               "targetId":"myLLMSystem",
               "data":{}
            }
         ]
      }
   ]
}
```

2. Run this curl command to push the data to StackState:

``` bash
curl -v user:password -X POST -H "Content-Type: application/json" --data-ascii @topology.json "{{config.baseUrl}}/stsAgent/intake/?api_key={{config.apiKey}}"
```

