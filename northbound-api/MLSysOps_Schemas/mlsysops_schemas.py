node_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MLSysOpsNode Schema",
    "type": "object",
    "properties": {
        "MLSysOpsNode": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the node."
                },
                "labels": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "The required labels for filtering."
                },
                "continuumLayer": {
                    "type": "string",
                    "enum": [
                        "Cloud",
                        "EdgeInfrastructure",
                        "Edge",
                        "FarEdge"
                    ]
                },
                "clusterID": {
                    "type": "string",
                    "description": "The unique cluster identifier that the node resides."
                },
                "datacenterID": {
                    "type": "string",
                    "description": "The unique datacenter identifier that the node belongs to (if any). If no datacenterID is provided, the node is considered as standalone and will be characterized using its location (geocoordinates)."
                },
                "availability": {
                    "type": "string",
                    "enum": [
                        "transient",
                        "stable"
                    ],
                    "description": "Depicts the level of a node's availability. It is not related to addition/removal to/from a cluster. However, it relates to possible status transitions, for example due to energy outage (e.g. a node using a battery)."
                },
                "mobility": {
                    "type": "boolean",
                    "description": "Specify if the node is mobile or stationary."
                },
                "location": {
                    "type": "array",
                    "description": "This is used for fixed nodes. We assume that mobile node's location is telemetry data which is not captured via these descriptions. We can also assume that for mobile nodes this refers to base station's coordinates (lon, lat).",
                    "items": {
                        "type": "number"
                    }
                },
                "sensors": {
                    "type": "array",
                    "description": "Available sensors on a node are presented as services provided by MLSysOps. Thus, each sensor has several methods that can be transparently accessed by application components without requiring extra effort from the developer to directly communicate with the device from within the container and enabling easy component relocation while abstracting out the node peculiarities following a FaaS approach.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "camera": {
                                "type": "object",
                                "properties": {
                                    "instances": {
                                        "type": "integer",
                                        "description": "Define the number of identical models (for multi-camera nodes)."
                                    },
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "description": "The list of camera service methods.",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string",
                                                    "enum": [
                                                        "CaptureImage",
                                                        "CaptureImagePeriodic",
                                                        "CaptureVideo",
                                                        "ListImages",
                                                        "GetImageInfo",
                                                        "RetrieveImage",
                                                        "GetCameraInfo"
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string",
                                        "enum": [
                                            "D455",
                                            "IMX477",
                                            "picamera-v2"
                                        ],
                                        "description": "The model name of the camera sensor."
                                    },
                                    "cameraType": {
                                        "type": "string",
                                        "description": "The camera sensor type."
                                    },
                                    "framerate": {
                                        "type": "integer"
                                    },
                                    "resolution": {
                                        "type": "string",
                                        "enum": [
                                            "1024x768",
                                            "4056x3040"
                                        ]
                                    }
                                },
                                "required": [
                                    "methods"
                                ]
                            },
                            "temperature": {
                                "type": "object",
                                "properties": {
                                    "instances": {
                                        "type": "integer",
                                        "description": "Define the number of identical models."
                                    },
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "description": "The list of temperature service methods.",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string",
                                                    "enum": [
                                                        "GetTemperature"
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string",
                                        "enum": [
                                            "SDC30",
                                            "DS18B20"
                                        ],
                                        "description": "The model name of the temperature sensor"
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string",
                                        "enum": [
                                            "Celsius",
                                            "Fahrenheit"
                                        ]
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "number"
                                    }
                                },
                                "required": [
                                    "methods"
                                ]
                            },
                            "accelerometer": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "description": "The list of accelerometer service methods.",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string",
                                                    "enum": [
                                                        "GetAcceleration"
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string",
                                        "enum": [
                                            "3038-SMT"
                                        ]
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string",
                                        "enum": [
                                            "m/s^2"
                                        ]
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "number"
                                    }
                                },
                                "required": [
                                    "methods"
                                ]
                            },
                            "humidity": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string"
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string"
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "object",
                                        "properties": {
                                            "min": {
                                                "type": "number"
                                            },
                                            "max": {
                                                "type": "number"
                                            }
                                        }
                                    }
                                }
                            },
                            "sound": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string"
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string"
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "object",
                                        "properties": {
                                            "min": {
                                                "type": "number"
                                            },
                                            "max": {
                                                "type": "number"
                                            }
                                        }
                                    }
                                }
                            },
                            "CO2": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string"
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string"
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "object",
                                        "properties": {
                                            "min": {
                                                "type": "number"
                                            },
                                            "max": {
                                                "type": "number"
                                            }
                                        }
                                    }
                                }
                            },
                            "barometer": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "description": "The list of barometer service methods.",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string",
                                                    "enum": [
                                                        "GetAtmosphericPressure"
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string",
                                        "enum": [
                                            "SB-100"
                                        ]
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string",
                                        "enum": [
                                            "Pa"
                                        ]
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "number"
                                    }
                                },
                                "required": [
                                    "methods"
                                ]
                            },
                            "airQuality": {
                                "type": "object",
                                "properties": {
                                    "methods": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "description": "The list of airQuality service methods.",
                                            "properties": {
                                                "methodName": {
                                                    "type": "string",
                                                    "enum": [
                                                        "DetectAirContaminants"
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "model": {
                                        "type": "string",
                                        "enum": [
                                            "MQ-135"
                                        ]
                                    },
                                    "measurementMin": {
                                        "type": "number"
                                    },
                                    "measurementMax": {
                                        "type": "number"
                                    },
                                    "measurementUnit": {
                                        "type": "string",
                                        "enum": [
                                            "m^3"
                                        ]
                                    },
                                    "accuracy": {
                                        "type": "number"
                                    },
                                    "samplingFrequency": {
                                        "type": "number"
                                    }
                                },
                                "required": [
                                    "methods"
                                ]
                            }
                        }
                    }
                },
                "distributedStorageService": {
                    "type": "object",
                    "properties": {
                        "member": {
                            "type": "boolean"
                        },
                        "availableSpace": {
                            "type": "number",
                            "description": "Available space to be used by the storage service in GB."
                        }
                    },
                    "description": "This property specifies whether the node is part of the distributed storage service or not."
                },
                "environment": {
                    "type": "object",
                    "properties": {
                        "nodeType": {
                            "type": "string",
                            "enum": [
                                "Virtualized",
                                "Native",
                                "BareMetal"
                            ]
                        },
                        "OS": {
                            "type": "string",
                            "enum": [
                                "Ubuntu",
                                "Kali",
                                "Zephyr"
                            ]
                        },
                        "container-runtime": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "containerd",
                                    "Docker",
                                    "embServe"
                                ]
                            }
                        }
                    }
                },
                "accelerationAPI": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "callName": {
                                "type": "string",
                                "enum": [
                                    "CalcOpticalFlow",
                                    "ImageInference"
                                ],
                                "description": "The (unique) API call name."
                            },
                            "supportedPlatforms": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "enum": [
                                                "CPU",
                                                "GPU",
                                                "FPGA",
                                                "TPU"
                                            ]
                                        },
                                        "suportedFrameworks": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "enum": [
                                                    "PyTorch",
                                                    "TensorFlow",
                                                    "OpenCL"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "required": [
                            "callName",
                            "supportedPlatforms"
                        ]
                    }
                },
                "hardware": {
                    "type": "object",
                    "properties": {
                        "CPU": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "description": "CPU model name."
                                },
                                "architecture": {
                                    "type": "string",
                                    "enum": [
                                        "x86",
                                        "arm64"
                                    ]
                                },
                                "cores": {
                                    "type": "integer"
                                },
                                "frequency": {
                                    "type": "array",
                                    "description": "All the possible CPU frequency values.",
                                    "items": {
                                        "type": "number"
                                    }
                                },
                                "performanceIndicator": {
                                    "type": "number",
                                    "description": "Quantifies the processing capabilities of the platform."
                                }
                            }
                        },
                        "MCU": {
                            "type": "object",
                            "properties": {
                                "architecture": {
                                    "type": "string",
                                    "enum": [
                                        "arm-M4"
                                    ]
                                },
                                "Flash": {
                                    "type": "string",
                                    "description": "Flash memory size (related to far edge devices)"
                                },
                                "cores": {
                                    "type": "integer"
                                },
                                "frequency": {
                                    "type": "number"
                                },
                                "performanceIndicator": {
                                    "type": "number",
                                    "description": "Quantifies the processing capabilities of the platform."
                                }
                            }
                        },
                        "RAM": {
                            "type": "string",
                            "description": "RAM size (in GB)."
                        },
                        "Disk": {
                            "type": "string",
                            "description": "Disk space in GB (local storage)."
                        },
                        "GPU": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "enum": [
                                        "NVIDIA",
                                        "K80",
                                        "K40"
                                    ]
                                },
                                "memory": {
                                    "type": "string"
                                },
                                "instances": {
                                    "type": "number"
                                },
                                "performanceIndicator": {
                                    "type": "number",
                                    "description": "Quantifies the processing capabilities of the platform."
                                }
                            }
                        },
                        "FPGA": {
                            "type": "object",
                            "properties": {
                                "model": {
                                    "type": "string",
                                    "enum": [
                                        "ZCU102"
                                    ]
                                },
                                "memory": {
                                    "type": "string"
                                },
                                "performanceIndicator": {
                                    "type": "number",
                                    "description": "Quantifies the processing capabilities of the platform."
                                }
                            }
                        }
                    }
                },
                "networkResources": {
                    "type": "object",
                    "properties": {
                        "BasicInterface": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "enum": [
                                        "4G",
                                        "5G",
                                        "WiFi",
                                        "Bluetooth",
                                        "LoRa",
                                        "ZigBee",
                                        "Ethernet"
                                    ],
                                    "description": "It is the (only) interface used for control traffic. Also, it is the default interface for application-level traffic."
                                },
                                "range": {
                                    "type": "number",
                                    "description": "The communication range if the given interface is wireless."
                                },
                                "interfaceName": {
                                    "type": "string"
                                }
                            }
                        },
                        "redirectionInterface": {
                            "type": "array",
                            "description": "The redirection only refers to application traffic.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "connectionType": {
                                        "type": "string",
                                        "enum": [
                                            "4G",
                                            "5G",
                                            "WiFi",
                                            "Bluetooth",
                                            "LoRa",
                                            "ZigBee",
                                            "Ethernet"
                                        ],
                                        "description": "The networking interface technology"
                                    },
                                    "range": {
                                        "type": "number",
                                        "description": "The communication range if the given interface is wireless."
                                    },
                                    "interfaceName": {
                                        "type": "string"
                                    },
                                    "mode": {
                                        "type": "string",
                                        "enum": [
                                            "infrastructure",
                                            "adhoc"
                                        ],
                                        "description": "The connectivity."
                                    },
                                    "hardwareAddress": {
                                        "type": "string"
                                    },
                                    "pairingInfo": {
                                        "type": "object",
                                        "properties": {
                                            "ipAddress": {
                                                "type": "string"
                                            },
                                            "networkSSID": {
                                                "type": "string",
                                                "description": "The network id (SSID or PAN ID)"
                                            },
                                            "netKey": {
                                                "type": "string",
                                                "description": "The network connection password"
                                            }
                                        }
                                    }
                                },
                                "required": [
                                    "connectionType"
                                ]
                            }
                        }
                    }
                },
                "powerSources": {
                    "type": "object",
                    "properties": {
                        "grid": {
                            "type": "boolean"
                        },
                        "renewable": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "enum": [
                                            "solarPanel"
                                        ],
                                        "Production": {
                                            "type": "object",
                                            "properties": {
                                                "value": {
                                                    "type": "number"
                                                },
                                                "measurementUnit": {
                                                    "type": "string",
                                                    "enum": [
                                                        "mAh",
                                                        "Wh"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "battery": {
                            "type": "object",
                            "properties": {
                                "capacity": {
                                    "type": "object",
                                    "properties": {
                                        "value": {
                                            "type": "number"
                                        },
                                        "measurementUnit": {
                                            "type": "string",
                                            "enum": [
                                                "mAh",
                                                "Wh"
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }, "required": ["MLSysOpsNode"]
}
cluster_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MLSysOpsCluster Schema",
    "type": "object",
    "properties": {
        "MLSysOpsCluster": {
            "type": "object",
            "properties": {
                "clusterID": {"type": "string",
                              "description": " str"},
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "string"
                    }
                },
            }, "required": ["clusterID", "nodes"]
        }
    }, "required": ["MLSysOpsCluster"]
}
continuum_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MLSysOpsContinuum Schema",
    "type": "object",
    "properties": {
        "MLSysOpsContinuum": {
            "type": "object",
            "properties": {
                "continuumID": {"type": "string",
                                "description": " str"},
                "clusters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "string"
                    }
                },
            }, "required": ["continuumID", "clusters"]
        }
    }, "required": ["MLSysOpsContinuum"]
}
datacenter_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MLSysOpsDatacenter Schema",
    "type": "object",
    "properties": {
        "MLSysOpsDatacenter": {
            "type": "object",
            "description": "string",
            "properties": {
                "datacenterID": {
                    "type": "string",
                    "description": "The unique datacenter identifier."
                },
                "clusterID": {
                    "type": "string",
                    "description": "The clusterID that the given datacenter is a member."
                },
                "continuum": {
                    "type": "string",
                    "description": "The continuum layer that the datacenter belongs to.",
                    "enum": ["Cloud", "EdgeInfrastructure", "Edge", "FarEdge"]
                },
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "The set of registered nodes."
                },
                "continent": {
                    "type": "string",
                    "description": "The desired continent (optional).",
                    "enum": ["Europe", "Asia", "Africa", "Australia", "North America", "South America", "Antarctica"]
                },
                "country": {
                    "type": "string",
                    "description": "The desired country (optional).",
                    "enum": ["GR", "IT", "FRA", "ENG", "POR"]
                },
                "city": {
                    "type": "string",
                    "description": "The desired city (optional).",
                    "enum": ["Volos", "Milan", "Paris", "London", "Lisbon"]
                },
                "location": {
                    "type": "array",
                    "description": "The location of the datacenter.",
                    "items": {
                        "type": "number"
                    }
                },
                "cloudProvider": {
                    "type": "string",
                    "description": "The cloud provider (optional)."
                }
            }, "required": ["clusterID", "datacenterID", "continuum", "nodes"]

        }

    }, "required": ["MLSysOpsDatacenter"]
}
app_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MLSysOpsApplication Schema",
    "type": "object",
    "properties": {
            "MLSysOpsApplication": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "mlsysops-id": {
                        "type": "string"
                    },
                    "clusterPlacement": {
                        "type": "object",
                        "properties": {
                            "clusterID": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Array of clusters that can host the application."
                            },
                            "instances": {
                                "type": "integer",
                                "description": "The desired number of replicas (e.g. deploy 2 instances of a given app)."
                            },
                            "location": {
                                "type": "object",
                                "properties": {
                                    "continent": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "Europe",
                                                "Asia"
                                            ],
                                            "description": "The required continent (optional)"
                                        }
                                    },
                                    "country": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "EL",
                                                "IT",
                                                "FR",
                                                "NL",
                                                "IE",
                                                "PT",
                                                "DK",
                                                "IL"
                                            ]
                                        },
                                        "description": "The required country (optional)"
                                    },
                                    "city": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "enum": [
                                                "Volos",
                                                "Athens",
                                                "Rende",
                                                "Milan",
                                                "Lille",
                                                "Delft",
                                                "Dublin",
                                                "Aveiro",
                                                "Porto",
                                                "Aarhus",
                                                "Jerusalem"
                                            ],
                                            "description": "The required city (optional)"
                                        }
                                    }
                                }
                            },
                            "cloudProvider": {
                                "type": "string",
                                "enum": [
                                    "private",
                                    "AWS",
                                    "MicrosoftAzure",
                                    "GCP"
                                ]
                            },
                            "accelerators": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "GPU",
                                        "FPGA",
                                        "TPU"
                                    ]
                                },
                                "description": "The candidate clusters should have nodes containing at least one instance of the specified accelerators."
                            },
                            "nodeTypes": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "Cloud",
                                        "FarEdge",
                                        "EdgeInfrastructure",
                                        "Edge"
                                    ],
                                    "description": "The required"
                                },
                                "description": "The candidate clusters should contain at least one node of each specified type."
                            }
                        }
                    },
                    "singleNode": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "description": "The application deployment should occur within a single node with the required characteristics. If the involved components have multiple instances, the framework will do the same for all the replicas. This field will override nodePlacement information (if specified) for any of the components.",
                            "properties": {
                                "components": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "The array of components to be deployed on the same Node."
                                },
                                "continuumLayer": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": [
                                            "Cloud",
                                            "FarEdge",
                                            "EdgeInfrastructure",
                                            "Edge",
                                            "*"
                                        ],
                                        "description": "The required component placement on the continuum. \"*\" symbol means \"anywhere on the continuum\"."
                                    }
                                },
                                "Scaling": {
                                    "type": "object",
                                    "properties": {
                                        "scalingMode": {
                                            "type": "string",
                                            "enum": [
                                                "manual",
                                                "auto"
                                            ]
                                        },
                                        "instances": {
                                            "type": "integer",
                                            "description": "In case of manual scaling of the component, specify the number of instances."
                                        },
                                        "scalingCriteria": {
                                            "type": "string",
                                            "enum": [
                                                "MinCPUutilization",
                                                "MaxCPUutilization",
                                                "MinMemoryPercent",
                                                "MaxMemoryPercent",
                                                "MinRequestsPerSec",
                                                "MaxRequestPerSec",
                                                "MinNumberOfInstances",
                                                "MaxNumberOfInstances"
                                            ],
                                            "description": "Scaling criteria for the component, related to the \"auto\" scaling type."
                                        }
                                    },
                                    "description": "The component scaling information."
                                },
                                "mobility": {
                                    "type": "boolean",
                                    "description": "Specify if the component needs to be deployed on a mobile node (optional)"
                                },
                                "labels": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "The required labels for filtering."
                                },
                                "node": {
                                    "type": "string",
                                    "description": "The required node name to be the host of the component (optional)."
                                }
                            }
                        }
                    },
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "Component": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "The unique name of the component"
                                        },
                                        "uid": {
                                            "type": "string",
                                            "description": "The unique identifier of the component (not given by app provider)."
                                        }
                                    }
                                },
                                "nodePlacement": {
                                    "type": "object",
                                    "properties": {
                                        "continuumLayer": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "enum": [
                                                    "Cloud",
                                                    "FarEdge",
                                                    "EdgeInfrastructure",
                                                    "Edge",
                                                    "*"
                                                ],
                                                "description": "The required component placement on the continuum. \"*\" symbol means \"anywhere on the continuum\"."
                                            }
                                        },
                                        "Scaling": {
                                            "type": "object",
                                            "properties": {
                                                "scalingMode": {
                                                    "type": "string",
                                                    "enum": [
                                                        "manual",
                                                        "auto"
                                                    ]
                                                },
                                                "instances": {
                                                    "type": "integer",
                                                    "description": "In case of manual scaling of the component, specify the number of instances."
                                                },
                                                "scalingCriteria": {
                                                    "type": "string",
                                                    "enum": [
                                                        "MinCPUutilization",
                                                        "MaxCPUutilization",
                                                        "MinMemoryPercent",
                                                        "MaxMemoryPercent",
                                                        "MinRequestsPerSec",
                                                        "MaxRequestPerSec",
                                                        "MinNumberOfInstances",
                                                        "MaxNumberOfInstances"
                                                    ],
                                                    "description": "Scaling criteria for the component, related to the \"auto\" scaling type."
                                                }
                                            },
                                            "description": "The component scaling information."
                                        },
                                        "mobility": {
                                            "type": "boolean",
                                            "description": "Specify if the component needs to be deployed on a mobile node (optional)"
                                        },
                                        "labels": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "description": "The required labels for filtering."
                                        },
                                        "node": {
                                            "type": "string",
                                            "description": "The required node name to be the host of the component (optional)."
                                        }
                                    }
                                },
                                "DependsOn": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "description": "The name of the related components."
                                    },
                                    "description": "The given component should be deployed after all the components specified in the Components list have already started running."
                                },
                                "runtimeConfiguration": {
                                    "type": "object",
                                    "description": "Enables runtime (node-level) configuration for app components.",
                                    "properties": {
                                        "configSpecificationFile": {
                                            "type": "string",
                                            "description": "The actual specification file describing the available runtime configuration knobs (expected in json format). This file is provided by the app developer."
                                        },
                                        "configFilePath": {
                                            "type": "string",
                                            "description": "The absolute path inside the container where the application code expects to find the configSpecificationFile."
                                        }
                                    }
                                },
                                "sensors": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "camera": {
                                                "type": "object",
                                                "properties": {
                                                    "methods": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "description": "The list of camera service methods.",
                                                            "properties": {
                                                                "methodName": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "CaptureImage",
                                                                        "CaptureImagePeriodic",
                                                                        "CaptureVideo",
                                                                        "ListImages",
                                                                        "GetImageInfo",
                                                                        "RetrieveImage",
                                                                        "GetCameraInfo"
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "model": {
                                                        "type": "string",
                                                        "enum": [
                                                            "D455",
                                                            "IMX477",
                                                            "picamera-v2"
                                                        ],
                                                        "description": "The model name of the camera sensor"
                                                    },
                                                    "cameraType": {
                                                        "type": "string",
                                                        "enum": [
                                                            "RGB",
                                                            "NIR",
                                                            "Thermal",
                                                            "Monocular"
                                                        ],
                                                        "description": "The camera sensor type."
                                                    },
                                                    "minimumFramerate": {
                                                        "type": "integer"
                                                    },
                                                    "resolutions": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string",
                                                            "enum": [
                                                                "1024x768",
                                                                "4056x3040"
                                                            ]
                                                        }
                                                    }
                                                }
                                            },
                                            "temperature": {
                                                "type": "object",
                                                "properties": {
                                                    "methods": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "description": "The list of temperature service methods.",
                                                            "properties": {
                                                                "methodName": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "GetTemperature"
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "model": {
                                                        "type": "string",
                                                        "enum": [
                                                            "SDC30",
                                                            "DS18B20"
                                                        ],
                                                        "description": "The model name of the temperature sensor"
                                                    },
                                                    "measurementMin": {
                                                        "type": "number"
                                                    },
                                                    "measurementMax": {
                                                        "type": "number"
                                                    },
                                                    "measurementUnit": {
                                                        "type": "string",
                                                        "enum": [
                                                            "Celsius",
                                                            "Fahrenheit"
                                                        ]
                                                    },
                                                    "accuracy": {
                                                        "type": "number"
                                                    },
                                                    "samplingFrequency": {
                                                        "type": "number"
                                                    }
                                                }
                                            },
                                            "accelerometer": {
                                                "type": "object",
                                                "properties": {
                                                    "methods": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "description": "The list of accelerometer service methods.",
                                                            "properties": {
                                                                "methodName": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "GetAcceleration"
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "model": {
                                                        "type": "string",
                                                        "enum": [
                                                            "3038-SMT"
                                                        ]
                                                    },
                                                    "measurementMin": {
                                                        "type": "number"
                                                    },
                                                    "measurementMax": {
                                                        "type": "number"
                                                    },
                                                    "measurementUnit": {
                                                        "type": "string",
                                                        "enum": [
                                                            "m/s^2"
                                                        ]
                                                    },
                                                    "accuracy": {
                                                        "type": "number"
                                                    },
                                                    "samplingFrequency": {
                                                        "type": "number"
                                                    }
                                                }
                                            },
                                            "barometer": {
                                                "type": "object",
                                                "properties": {
                                                    "methods": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "description": "The list of barometer service methods.",
                                                            "properties": {
                                                                "methodName": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "GetAtmosphericPressure"
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "model": {
                                                        "type": "string",
                                                        "enum": [
                                                            "SB-100"
                                                        ]
                                                    },
                                                    "measurementMin": {
                                                        "type": "number"
                                                    },
                                                    "measurementMax": {
                                                        "type": "number"
                                                    },
                                                    "measurementUnit": {
                                                        "type": "string",
                                                        "enum": [
                                                            "Pa"
                                                        ]
                                                    },
                                                    "accuracy": {
                                                        "type": "number"
                                                    },
                                                    "samplingFrequency": {
                                                        "type": "number"
                                                    }
                                                }
                                            },
                                            "airQuality": {
                                                "type": "object",
                                                "properties": {
                                                    "methods": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "description": "The list of airQuality service methods.",
                                                            "properties": {
                                                                "methodName": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "DetectAirContaminants"
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    },
                                                    "model": {
                                                        "type": "string",
                                                        "enum": [
                                                            "MQ-135"
                                                        ]
                                                    },
                                                    "measurementMin": {
                                                        "type": "number"
                                                    },
                                                    "measurementMax": {
                                                        "type": "number"
                                                    },
                                                    "measurementUnit": {
                                                        "type": "string",
                                                        "enum": [
                                                            "μg/m^3"
                                                        ]
                                                    },
                                                    "accuracy": {
                                                        "type": "number"
                                                    },
                                                    "samplingFrequency": {
                                                        "type": "number"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                "QoS-Metrics": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "ApplicationMetricID": {
                                                "type": "string",
                                                "description": "This is an indicative list of metrics. It can be extended as needed."
                                            },
                                            "target": {
                                                "type": "number"
                                            },
                                            "relation": {
                                                "type": "string",
                                                "enum": [
                                                    "LowerOrEqual",
                                                    "GreaterOrEqual",
                                                    "Equal",
                                                    "LowerThan",
                                                    "GreaterThan"
                                                ]
                                            },
                                            "systemMetricsHints": {
                                                "type": "array",
                                                "description": "System-level metrics affecting the application metric.",
                                                "items": {
                                                    "type": "string",
                                                    "enum": [
                                                        "CPUFrequency"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                },
                                "storage": {
                                    "type": "object",
                                    "properties": {
                                        "buckets": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "bucketID": {
                                                        "type": "string",
                                                        "description": "The bucket's unique identifier."
                                                    },
                                                    "policyUpdateToken": {
                                                        "type": "string",
                                                        "description": "The required token for the MLSysOps to update the bucket's policy at runtime."
                                                    },
                                                    "locationRestrictions": {
                                                        "type": "object",
                                                        "description": "These restrictions are used to exclude storage locations that host data of the application.",
                                                        "properties": {
                                                            "GDPR": {
                                                                "type": "boolean",
                                                                "description": "For EU citizens only GDPR-compliant storage locations can legally be used."
                                                            }
                                                        }
                                                    },
                                                    "reduncancy": {
                                                        "type": "string",
                                                        "enum": [
                                                            "High",
                                                            "One",
                                                            "None"
                                                        ]
                                                    },
                                                    "maxLatency": {
                                                        "type": "number"
                                                    },
                                                    "minDownloadSpeed": {
                                                        "type": "number"
                                                    },
                                                    "serverSideEncryption": {
                                                        "type": "string",
                                                        "enum": [
                                                            "ON",
                                                            "OFF"
                                                        ]
                                                    }
                                                },
                                                "required": [
                                                    "bucketID"
                                                ]
                                            }
                                        }
                                    }
                                },
                                "dataSensitivity": {
                                    "type": "boolean",
                                    "description": "The indication to specify whether a component has sensitive data or not (useful for the data storage)."
                                },
                                "dataCriticality": {
                                    "type": "string",
                                    "enum": [
                                        "Low",
                                        "Medium",
                                        "High"
                                    ],
                                    "description": "Used to provide information referring to the trust aspect for a given component."
                                },
                                "externalComponent": {
                                    "type": "boolean",
                                    "description": "This property indicates whether the component can be managed by MLSysOps or not. If not the MLSysOps platform merely deploys the component(s), based on the provided instances, and subsequently deletes it whenever the application needs to be removed."
                                },
                                "externalAccess": {
                                    "type": "boolean",
                                    "description": "This property indicates whether the component can be accessed outside of its cluster."
                                },
                                "hostNetwork": {
                                    "type": "boolean",
                                    "description": "Host networking requested for this component. Use the host's network namespace. If this option is set, the ports that will be used must be specified. Default to false."
                                },
                                "runtimeClassName": {
                                    "type": "string",
                                    "enum": [
                                        "nvidia"
                                    ]                                },
                                "restartPolicy": {
                                    "type": "string",
                                    "enum": [
                                        "Always",
                                        "OnFailure",
                                        "Never"
                                    ],
                                    "description": "Restart policy for the container. Default to Always."
                                },
                                "containers": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "image": {
                                                "type": "string",
                                                "description": "The name of the container image."
                                            },
                                            "resources": {
                                                "type": "object",
                                                "properties": {
                                                "requests": {
                                                    "type": "object",
                                                    "properties": {
                                                        "cpu": {
                                                            "type": "string"
                                                        },
                                                        "memory": {
                                                            "type": "string"
                                                        },
                                                        "nvidia.com/gpu": {
                                                            "type": "integer"
                                                        }
                                                    }
                                                },
                                                "limits": {
                                                    "type": "object",
                                                    "properties": {
                                                        "cpu": {
                                                            "type": "string"
                                                        },
                                                        "memory": {
                                                            "type": "string"
                                                        },
                                                        "nvidia.com/gpu": {
                                                            "type": "integer"
                                                        }
                                                    }
                                                }
                                                }
                                            },
                                            "securityContext": {
                                                "type": "object",
                                                "properties": {
                                                "allowPrivilegeEscalation": {
                                                    "type": "boolean"
                                                }
                                                },
                                                "description": "SecurityContext defines the security options the container should be run with."
                                            },
                                            "command": {
                                                "type": "array",
                                                "items": {
                                                    "type": "string"
                                                }
                                            },
                                            "imagePullPolicy": {
                                                "type": "string",
                                                "enum": [
                                                    "Always",
                                                    "Never",
                                                    "IfNotPresent"
                                                ],
                                                "description": "Image pull policy. Defaults to Always if :latest tag is specified, or IfNotPresent otherwise."
                                            },
                                            "accelerationAPI": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "callName": {
                                                            "type": "string",
                                                            "description": "The (unique) API call name.",
                                                            "enum": [
                                                                "CalcOpticalFlow",
                                                                "ImageInference"
                                                            ]
                                                        },
                                                        "requiredFramework": {
                                                            "type": "string",
                                                            "description": "Asterisk means any of the available frameworks.",
                                                            "enum": [
                                                                "PyTorch",
                                                                "TensorFlow",
                                                                "OpenCL",
                                                                "*"
                                                            ]
                                                        }
                                                    },
                                                    "required": [
                                                        "callName"
                                                    ]
                                                }
                                            },
                                            "resourceRequirements": {
                                                "type": "object",
                                                "description": "The resource requirements of the container.",
                                                "properties": {
                                                    "CPU": {
                                                        "type": "object",
                                                        "properties": {
                                                            "architecture": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "x86",
                                                                        "arm64"
                                                                    ]
                                                                }
                                                            },
                                                            "cores": {
                                                                "type": "integer",
                                                                "description": "required cores"
                                                            },
                                                            "frequency": {
                                                                "type": "number",
                                                                "description": "required frequency in GHz."
                                                            }
                                                        }
                                                    },
                                                    "MCU": {
                                                        "type": "object",
                                                        "properties": {
                                                            "architecture": {
                                                                "type": "array",
                                                                "items": {
                                                                    "type": "string",
                                                                    "enum": [
                                                                        "arm-M4"
                                                                    ]
                                                                }
                                                            },
                                                            "Flash": {
                                                                "type": "string",
                                                                "description": "Flash memory size (related to far edge devices)"
                                                            },
                                                            "cores": {
                                                                "type": "integer",
                                                                "description": "required cores"
                                                            },
                                                            "frequency": {
                                                                "type": "number",
                                                                "description": "required frequency in GHz."
                                                            }
                                                        }
                                                    },
                                                    "RAM": {
                                                        "type": "string",
                                                        "description": "required RAM (in GB)."
                                                    },
                                                    "Disk": {
                                                        "type": "string",
                                                        "description": "required Disk space (in GB)."
                                                    },
                                                    "GPU": {
                                                        "type": "object",
                                                        "properties": {
                                                            "model": {
                                                                "type": "string",
                                                                "enum": [
                                                                    "K80",
                                                                    "K40"
                                                                ]
                                                            },
                                                            "memory": {
                                                                "type": "string"
                                                            },
                                                            "utilizationRequest": {
                                                                "type": "string",
                                                                "description": "Percentage of expected utilization."
                                                            }
                                                        }
                                                    },
                                                    "FPGA": {
                                                        "type": "object",
                                                        "properties": {
                                                            "model": {
                                                                "type": "string",
                                                                "enum": [
                                                                    "ZCU102"
                                                                ]
                                                            },
                                                            "memory": {
                                                                "type": "string"
                                                            },
                                                            "utilizationRequest": {
                                                                "type": "string",
                                                                "description": "Percentage of expected utilization."
                                                            }
                                                        }
                                                    },
                                                    "performanceIndicator": {
                                                        "type": "number",
                                                        "description": "This field assists MLSysOps with an initial hint in order to filter out nodes based on their performance capabilities."
                                                    }
                                                }
                                            },
                                            "environmentRequirements": {
                                                "type": "object",
                                                "properties": {
                                                    "nodeType": {
                                                        "type": "string",
                                                        "enum": [
                                                            "Virtualized",
                                                            "Native",
                                                            "BareMetal"
                                                        ]
                                                    },
                                                    "OS": {
                                                        "type": "string",
                                                        "enum": [
                                                            "Ubuntu",
                                                            "Kali",
                                                            "Zephyr"
                                                        ]
                                                    },
                                                    "container-runtime": {
                                                        "type": "string",
                                                        "enum": [
                                                            "containerd",
                                                            "Docker",
                                                            "embServe"
                                                        ]
                                                    }
                                                }
                                            },
                                            "ports": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "containerPort": {
                                                            "type": "integer",
                                                            "description": "Number of port to expose on the component's IP address. This must be a valid port number, 0 < x < 65536."
                                                        },
                                                        "hostIP": {
                                                            "type": "string",
                                                            "description": "What host IP to bind the external port to."
                                                        },
                                                        "hostPort": {
                                                            "type": "integer",
                                                            "description": "Number of port to expose on the host. If specified, this must be a valid port number, 0 < x < 65536. If HostNetwork is specified, this must match ContainerPort."
                                                        },
                                                        "name": {
                                                            "type": "string",
                                                            "description": "Each named port in a component must have a unique name. Name for the port that can be referred to by services."
                                                        },
                                                        "protocol": {
                                                            "type": "string",
                                                            "enum": [
                                                                "UDP",
                                                                "TCP",
                                                                "SCTP"
                                                            ],
                                                            "description": "Protocol for port. Defaults to \"TCP\"."
                                                        }
                                                    }
                                                },
                                                "description": "Environment variables for the container."
                                            },
                                            "env": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {
                                                            "type": "string",
                                                            "description": "Name of the environment variable."
                                                        },
                                                        "valueFrom": {
                                                            "type": "object",
                                                            "properties": {
                                                                "fieldRef": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "fieldPath": {
                                                                            "type": "string"
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        },
                                                        "value": {
                                                            "type": "string",
                                                            "description": "Value of the environment variable."
                                                        }
                                                    }
                                                },
                                                "description": "Environment variables for the container."
                                            }
                                        }
                                    }
                                }
                            },
                            "required": [
                                "Component"
                            ]
                        }
                    },
                    "componentInteractions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "componentName1": {
                                    "type": "string",
                                    "description": "The \"source\" component."
                                },
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "ingress",
                                        "egress"
                                    ]
                                },
                                "componentName2": {
                                    "type": "string",
                                    "description": "The \"destination\" component."
                                },
                                "interactionCriticality": {
                                    "type": "string",
                                    "enum": [
                                        "Low",
                                        "Medium",
                                        "High"
                                    ],
                                    "description": "Used to provide information referring to the trust aspect for a given interaction."
                                },
                                "interactionMetrics": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "SystemMetricID": {
                                                "type": "string",
                                                "enum": [
                                                    "Latency",
                                                    "Bandwidth",
                                                    "End2EndInvocationDelay"
                                                ],
                                                "description": "The unique identifier of the system-level metric related to this interaction."
                                            },
                                            "target": {
                                                "type": "number"
                                            },
                                            "measurementUnit": {
                                                "type": "string",
                                                "enum": [
                                                    "milliseconds",
                                                    "Mbps",
                                                    "seconds"
                                                ]
                                            },
                                            "relation": {
                                                "type": "string",
                                                "enum": [
                                                    "LowerOrEqual",
                                                    "GreaterOrEqual",
                                                    "Equal",
                                                    "LowerThan",
                                                    "GreaterThan"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "globalSatisfaction": {
                        "type": "object",
                        "properties": {
                            "threshold": {
                                "type": "number",
                                "description": "Happiness minimum required value (range (0-1])"
                            },
                            "relation": {
                                "type": "string",
                                "enum": [
                                    "GreaterOrEqual",
                                    "Equal",
                                    "GreaterThan"
                                ]
                            },
                            "achievementWeights": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "metricID": {
                                            "type": "string"
                                        },
                                        "weight": {
                                            "type": "number"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "required": [
                    "components"
                ]
            }
        
    }, "required": ["MLSysOpsApplication"]
}
