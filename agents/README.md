# MLSysOps Framework

## XMPP Service Configuration

This project uses the **XMPP (Extensible Messaging and Presence Protocol)** service for communication between agents. The XMPP service is powered by an **ejabberd** container, which we have set up for easy deployment and automatic configuration.

kubectl create configmap ejaberd-config --from-file=ejabberd.yml -n mlsysops-framework

### Prerequisites

Before running the XMPP service, ensure you have the following installed on your system:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### How It Works

The XMPP service is managed through a Docker container running **ejabberd**. We've provided an automatic configuration process that simplifies setup on any host machine.

### Setup Instructions

To set up and run the XMPP service, follow these steps:
1. **Ensures that you have all the necessary packages installed**

    Install the libraries of the requirements.txt file

    ```
    pip install -r requirements.txt
    ```

2. **Set the IP Address of the Host**

   - Open the [.env](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Xmpp/.env) file in the root directory.
   - Set the `IP_SEL` environment variable to the IP address of the host machine where the service will run.
   
   Example `.env` file:

   IP_SEL=10.96.82.195


3. **Configure ejabberd**

    - After setting the IP address in the `.env` file, run the [configuration script](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Xmpp/config_script.py) to update the [ejabberd.yml](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Xmpp/ejabberd.yml) file with the IP address provided in the `.env` file.
    - This script will automatically configure the XMPP service for you.

    Command to run the script:
    ```
    python config_script.py
    ```
4. **Run the XMPP Service**

    Once the configuration is complete, you can start the XMPP service using Docker Compose.

    Run the following command to start up the service:

    ```
    docker-compose up -d
    ```
   During the setup process, an admin user will be automatically registered with a default password. If the process completes successfully, the console output should show the following confirmation message:

    ```
    User admin@10.96.82.195 successfully registered
    ```
    This confirms that the admin user has been correctly registered in the XMPP service.

5. **Agent connection test**

   This repository contains a simple example to test the connection between an agent and an XMPP service using a DummyAgent. The goal is to ensure that the agent can successfully authenticate and communicate with the XMPP server.

    - Ensure that the host machine running the test script has network connectivity to the XMPP server. You can check this by pinging the server:
    - Configure the agent using the following Python code snippet. Please double check that you are using the admin user and the IP address previously configured. 

        ```
        dummy = DummyAgent("admin@10.96.82.195", "1234")
        ```
    - Run the script, If the connection succeeds, you will see the following message printed in the console:
        ```
        Hello World! I'm agent admin@10.96.82.195
        ```

6. **Agent registration**
    
    To register the agents that will be supported by the XMPP service, you can use the [user_reg.py](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Xmpp/user_reg.py) script. This script reads usernames and passwords from the [users.txt](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Xmpp/users.txt) file and registers the users on the XMPP service.

    Once the XMPP service is up and running, simply execute the script to create and register the JIDs (Jabber IDs) that the agents will use for communication.

    The format of the users.txt needs to be as follows:
     ```
        agentid1,password1
        agentid2,password2
    ```

Following the previous steps, an agent can be instantiated to communicate with any other agent in the framework through the XMPP service

---

# Node Agent

In this use case, the node agent is responsible for gathering telemetry data from the application running on the node. This includes monitoring the application's behavior as well as collecting CPU and memory metrics from the node itself. Using this information, the agent performs a machine learning (ML) model inference to predict the application's future behavior. The prediction results are then sent to the cluster agent, which uses this data to make decisions.

The node agent uses OpenTelemetry (OTEL) to collect performance data from both the node and the application. Additionally, the agent uses OTEL to share the inference results with the cluster agent for further processing.

Configuring the Node Agent
Install OpenTelemetry:
First, install the OTEL library, which is required for telemetry collection and data exchange.

```
        pip install -r requirements.txt
``` 


Set Up OTEL Variables:
You need to configure the necessary OTEL environment variables as follows:

```
        TELEMETRY_ENDPOINT="172.25.27.228:4317" to push
        LOCAL_OTEL_ENDPOINT="http://172.25.27.228:9999/metrics"
``` 

Configure Agent Information, providing the following information in the environment configuration:

```
    NODE_NAME=node                   
    NODE_PASSWORD=1234
    CLUSTER_NAME=cluster                        
    EJABBERD_DOMAIN=10.96.82.195        
                      
``` 

- Node agent name: The name of the agent running on the node.
- Agent password: The password of the node agent.
- Cluster agent name: The cluster agent to which the node agent will be subscribed.
- XMPP domain: The domain of the XMPP service used for communication.
- Note: is worth to say that the jids need to be previously registered as in the previous steps.


Once the environment is set up, you can run the node agent to start collecting telemetry and performing ML inferences.


[N_agent.service](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/blob/main/Node_agent/N_agent.service)  file is also provide to run the agent script as a daemon in linux systems.



## Project status
Testing phase.

---
<!-- 

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/ee/gitlab-basics/add-file.html#add-a-file-using-the-command-line) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

- [ ] [Set up project integrations](https://mlsysops-gitlab.e-ce.uth.gr/agent/augmenta_demo/-/settings/integrations)

## Collaborate with your team

- [ ] [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
- [ ] [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
- [ ] [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
- [ ] [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [ ] [Automatically merge when pipeline succeeds](https://docs.gitlab.com/ee/user/project/merge_requests/merge_when_pipeline_succeeds.html)

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/index.html)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing(SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***
