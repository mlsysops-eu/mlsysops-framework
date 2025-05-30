Top level view:

* Application descriptions (official version)

** clusterPlacement
** singleNode
** components
** componentInteractions
** permittedActions
** globalSatisfaction


* Application descriptions (first open source version)

clusterPlacement
    clusterID
    instances
components
    Component
        name
        uid
    nodePlacement
        continuumLayer
        mobility
        labels
        node
    DependsOn
    sensors
        camera
        temperature
    QoS-Metrics
    hostNetwork
    runtimeClassName
    restartPolicy
    containers
        image
        resources
        imagePullPolicy
        resourceRequirements
            CPU
            RAM
            Disk
            GPU
        environmentRequirements
            nodeType
            OS
            container-runtime
        ports
        env
componentInteractions
        component1
        component2
permittedActions
globalSatisfaction

* Node descriptions (official version)

** name
** labels
** continuumLayer
** clusterID
** datacenterID
** availability
** mobility
** location
** sensors
** permittedActions
** distributedStorageService
** environment
** accelerationAPI
** hardware
** networkResources
** powerSources

* Node descriptions (first open source version)

** name
** labels
** continuumLayer
** clusterID
** datacenterID
** availability
** mobility
** location
** sensors
** permittedActions
** distributedStorageService
** environment
** accelerationAPI
** hardware
** networkResources
** powerSources

* Datacenter will not be provided in the first version

* Cluster description (official version and first open source version)
** clusterID
** nodes


* Continuum description (official version and first open source version)
** continuumID
** clusters
