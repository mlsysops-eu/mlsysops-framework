The Northbound API (NB API) serves as the main interface for external systems—such as user interfaces and automation
tools—to interact with the MLSysOps agent-based orchestration framework. Designed as an HTTP-based RESTful service, it
enables users to send commands, retrieve information, and monitor overall system status.
The NB API operates on a predefined IP and port, supporting secure, asynchronous communication with the Continuum Agent.
This design allows for a modular and scalable control layer, effectively abstracting the internal complexity of the
multi-agent system. As a result, it offers a clean, service-oriented interface for seamless integration with external
management tools.

To ensure clarity and maintainability, the NB API is structured into four main categories, each aligned with a specific
operational domain of the system. This modular organization reflects the core responsibilities and lifecycle stages of
the MLSysOps framework, facilitating consistent and intuitive interaction for all users and systems.

**Applications**: Manage the lifecycle of deployed applications—from deployment to monitoring and removal.

| **Method** | **Endpoint**                     | **Description**                                                                      |
|------------|-----------------------------------|--------------------------------------------------------------------------------------|
| POST       | /apps/deploy                     | Deploy an application. Requires app description in request body.                    |
| GET        | /apps/list_all/                  | Retrieve a list of all deployed applications in the framework.                      |
| GET        | /apps/status/{app_id}            | Get the current status of a specific application.                                   |
| GET        | /apps/apps/details/{app_id}      | Fetch detailed metadata of an application.                                          |
| GET        | /apps/performance/{app_id}       | Access performance metrics of a deployed application.                               |
| DELETE     | /apps/remove/{app_id}            | Remove (undeploy) a specific application.                                           |

ML Models: Control the deployment and lifecycle of machine learning models integrated into the system.

| **Method** | **Endpoint**                  | **Description**                                              |
|------------|-------------------------------|--------------------------------------------------------------|
| POST       | /ml/deploy_ml                 | Deploy a machine learning model to the infrastructure.       |
| GET        | /ml/list_all/                 | List all currently deployed ML models.                      |
| GET        | /ml/status/{model_uid}        | Check the status of deployment of an ML model.              |
| DELETE     | /ml/remove/{model_uid}        | Remove an ML model from the system.                         |

**Infrastructure**: Register, list, and manage edge, cluster, and datacenter components that make up the continuum.

| **Method** | **Endpoint**                        | **Description**                                               |
|------------|-------------------------------------|---------------------------------------------------------------|
| POST       | /infra/register                     | Register infrastructure components (edge node, cluster, etc.). |
| GET        | /infra/list/                        | List all registered infrastructure components.                |
| DELETE     | /infra/unregister/{infra_id}        | Unregister and remove an infrastructure component.           |

**Management**: System-level controls for health checks and operational mode switching.

| **Method** | **Endpoint**                  | **Description**                                               |
|------------|-------------------------------|---------------------------------------------------------------|
| GET        | /manage/ping                  | Check continuum agent status (ping the continuum agent).       |
| PUT        | /manage/mode/{mode}           | Change operational mode of the Agent (Heuristic or ML).       |).

