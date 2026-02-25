if (!element.data.containsKey("tags")) {
    element.data.put("tags", [:])
}

if (!element.data.containsKey("properties")) {
    element.data.put("properties", [:])
}

def tags = element.data.tags

// Identity Promotion
if (tags.containsKey('suse.ai.component.name')) {
    element.data.put('name', tags['suse.ai.component.name'].toString())
} else if (tags.containsKey('service.name')) {
    element.data.put('name', tags['service.name'].toString())
}

// Identify SUSE AI Components
boolean isManaged = tags['suse.ai.managed'] == 'true' || tags['suse.ai.managed'] == true

if (isManaged) {
    tags.put('suse.ai.managed', 'true')
    
    // Use custom component type if provided
    if (tags['suse.ai.component.type']) {
        element.type.name = tags['suse.ai.component.type'].toString()
    }
} else if (tags.containsKey('gen_ai.system')) {
    // Inference Rule
    element.type.name = 'inference-engine'
    tags.put('suse.ai.managed', 'true')
}

element
