The MLS CLI is a Python-based command-line tool designed for managing application deployments and system interactions
within the MLSysOps framework. It provides functionalities for deploying and managing applications, infrastructure
components, and machine learning (ML) models, as well as for querying system status and monitoring deployments. The CLI
communicates with the Northbound API, enabling efficient interaction with the MLSysOps framework.
Ke
y functionalities provided by the MLS CLI through the NB API include service health checks (ping), application
deployment, and retrieval of system, application, and ML model statuses. This tool streamlines deployment and management
workflows, offering an intuitive interface for interacting with the agent-based framework while ensuring efficient
system operations.

The CLI is organized into distinct command groups, each responsible for managing a specific aspect of the system:
- apps: Manage application deployment, monitoring, and removal
- infra: Register and manage infrastructure components across the continuum
- ml: Handle the deployment and lifecycle of machine learning models
- manage: Perform general system operations, such as health checks and mode switching

This structured CLI design ensures that different user roles can efficiently interact with the system based on their
specific needs, further reinforcing the modular and scalable nature of the MLSysOps framework.

The table presents an overview of the CLI commands currently available. These commands are indicative and may be updated
or extended in the open-source release.


| **Group**       | **Command**               | **Description**                                        | **Parameters**                                            |
|------------------|---------------------------|--------------------------------------------------------|----------------------------------------------------------|
| **APP**         | deploy-app               | Deploy an application using a YAML file               | YAML file using path or URI                              |
|                  | list-all                | List the applications on the system                   | -                                                        |
|                  | get-app-status           | Get the status of the application                     | App_id                                                   |
|                  | get-app-details          | Get the details of an application                     | App_id                                                   |
|                  | get-app-performance      | Get the performance metric of an application          | App_id                                                   |
|                  | remove-app               | Remove an application from the system                 | App_id                                                   |
| **INFRA**       | register-infra           | Register system description                           | YAML file using path or URI                              |
|                  | list                     | List infrastructure registered                        | infra_id (Datacenter or cluster ID)                     |
|                  | unregister-infra         | Remove system description                             | infra_id                                                 |
| **Management**  | /config set-mode         | Change between ML or Heuristic-normal mode            | 0 for Heuristic, 1 for ML                                |
|                  | Set System Target        | Set infrastructure level targets                      | List of IDs and list of targets                          |
|                  | Config Trust            | Configure trust assessment                            | List of node IDs, list of indexes, and list of weights   |
|                  | Ping                     | Ping the continuum agent                              | -                                                        |
| **ML**          | deploy-ml               | Deploy an ML application using a YAML file            | YAML file using path or URI                              |
|                  | list-all                | List the ML models deployed on the system             | -                                                        |
|                  | get-status              | Get the status of the ML models                       | model_uid                                                |
|                  | remove-ml               | Remove an ML model from the system                    | model_uid                                                |
